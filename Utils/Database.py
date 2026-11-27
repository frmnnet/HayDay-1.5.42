"""SQLite player data store.

Why this looks the way it does
------------------------------
* **One connection per process.** ``sqlite3`` connections are not safe for
  concurrent use, and every client is served by its own thread (``ClientThread``
  / ``ThreadingHTTPServer``).  All access therefore goes through
  ``Database.instance()`` and is serialized by a re-entrant lock.
* **WAL + busy_timeout.**  Writes never block reads (and vice versa), and a
  competing writer waits instead of failing with ``database is locked``.
* **Versioned migrations.**  ``schema_version`` records how far the file has
  been upgraded, so old databases are brought forward instead of being
  patched with ad-hoc ``ALTER TABLE`` guesses at startup.
* **Whitelisted upserts.**  ``upsert_account(**fields)`` builds the column
  list from :data:`ACCOUNT_COLUMNS`, so no caller can smuggle SQL through a
  field name, and an empty field set is a no-op instead of broken SQL.
* **Normalized, queryable state.**  ``home_states`` keeps a rollback-safe
  blob while ``home_objects``, ``home_inventory`` and ``home_sections`` are
  written in the same transaction.  Reads prefer those normalized rows, so
  object coordinates and inventory are inspectable and editable in SQLite.
  ``JSON/home_state.json`` is only an export.

Usage::

    from Utils.Database import Database
    db = Database.instance()
    row = db.get_account(0, 1)
    with db.transaction():
        db.upsert_account(0, 1, cash=100)
"""
import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from Utils.Logging import logger

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "hayday.db"
BACKUP_DIR = BASE_DIR / "backups"

# Account columns a caller may write.  Anything else in **fields is rejected.
ACCOUNT_COLUMNS = (
    "name", "pass_token", "diamonds", "cash", "exp_level", "exp_points",
    "tutorial_completed", "stats", "created_at", "last_seen",
)

# Home blob columns a caller may write.
HOME_COLUMNS = ("data", "updated_at")

_ACCOUNT_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS accounts (
        high_id            INTEGER NOT NULL,
        low_id             INTEGER NOT NULL,
        name               TEXT    NOT NULL DEFAULT 'Forman',
        pass_token         TEXT    NOT NULL DEFAULT '',
        diamonds           INTEGER NOT NULL DEFAULT 0,
        cash               INTEGER NOT NULL DEFAULT 0,
        exp_level          INTEGER NOT NULL DEFAULT 1,
        exp_points         INTEGER NOT NULL DEFAULT 0,
        tutorial_completed INTEGER NOT NULL DEFAULT 0,
        stats              TEXT    NOT NULL DEFAULT '{}',
        created_at         INTEGER NOT NULL DEFAULT 0,
        last_seen          INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (high_id, low_id)
    )
"""

_HOME_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS home_states (
        high_id    INTEGER NOT NULL,
        low_id     INTEGER NOT NULL,
        data       TEXT    NOT NULL,
        updated_at INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (high_id, low_id)
    )
"""

_HOME_OBJECTS_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS home_objects (
        high_id      INTEGER NOT NULL,
        low_id       INTEGER NOT NULL,
        object_index INTEGER NOT NULL,
        runtime_id   INTEGER NOT NULL,
        data_id      INTEGER NOT NULL,
        x            INTEGER NOT NULL DEFAULT 0,
        y            INTEGER NOT NULL DEFAULT 0,
        accurate_x   INTEGER NOT NULL DEFAULT 0,
        accurate_y   INTEGER NOT NULL DEFAULT 0,
        mirrored     INTEGER NOT NULL DEFAULT 0,
        data         TEXT    NOT NULL DEFAULT '{}',
        PRIMARY KEY (high_id, low_id, object_index),
        FOREIGN KEY (high_id, low_id)
            REFERENCES home_states(high_id, low_id) ON DELETE CASCADE
    )
"""

_HOME_INVENTORY_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS home_inventory (
        high_id  INTEGER NOT NULL,
        low_id   INTEGER NOT NULL,
        item_id  TEXT    NOT NULL,
        amount   INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (high_id, low_id, item_id),
        FOREIGN KEY (high_id, low_id)
            REFERENCES home_states(high_id, low_id) ON DELETE CASCADE
    )
"""

_HOME_SECTIONS_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS home_sections (
        high_id  INTEGER NOT NULL,
        low_id   INTEGER NOT NULL,
        section  TEXT    NOT NULL,
        data     TEXT    NOT NULL,
        PRIMARY KEY (high_id, low_id, section),
        FOREIGN KEY (high_id, low_id)
            REFERENCES home_states(high_id, low_id) ON DELETE CASCADE
    )
"""


def _sync_home_projection(conn, high_id, low_id, data):
    """Replace the queryable projection for one player's home state."""
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (TypeError, ValueError):
            return
    if not isinstance(data, dict):
        return

    conn.execute(
        "DELETE FROM home_objects WHERE high_id=? AND low_id=?",
        (high_id, low_id))
    conn.execute(
        "DELETE FROM home_inventory WHERE high_id=? AND low_id=?",
        (high_id, low_id))
    conn.execute(
        "DELETE FROM home_sections WHERE high_id=? AND low_id=?",
        (high_id, low_id))

    ordinals = {}
    object_rows = []
    for index, entry in enumerate(data.get("Objects", []) or []):
        if not isinstance(entry, dict):
            continue
        try:
            data_id = int(entry.get("ID"))
            data_type = data_id // 100000
            ordinal = ordinals.get(data_type, 0)
            ordinals[data_type] = ordinal + 1
            runtime_id = int(entry.get(
                "_ClientRuntimeID", data_type * 100000 + ordinal))
            x = int(entry.get("X") or 0)
            y = int(entry.get("Y") or 0)
            accurate_x = int(entry.get("_AccurateX", x * 512))
            accurate_y = int(entry.get("_AccurateY", y * 512))
        except (TypeError, ValueError):
            continue
        object_rows.append((
            high_id, low_id, index, runtime_id, data_id, x, y,
            accurate_x, accurate_y,
            1 if entry.get("Mirrored") else 0,
            json.dumps(entry, ensure_ascii=False, separators=(",", ":")),
        ))
    if object_rows:
        conn.executemany(
            "INSERT INTO home_objects "
            "(high_id, low_id, object_index, runtime_id, data_id, x, y, "
            "accurate_x, accurate_y, mirrored, data) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            object_rows)

    inventory_rows = []
    inventory = data.get("Inventory", {})
    if isinstance(inventory, dict):
        for item_id, raw_amount in inventory.items():
            try:
                amount = int(raw_amount)
            except (TypeError, ValueError):
                continue
            inventory_rows.append((high_id, low_id, str(item_id), amount))
    if inventory_rows:
        conn.executemany(
            "INSERT INTO home_inventory "
            "(high_id, low_id, item_id, amount) VALUES (?, ?, ?, ?)",
            inventory_rows)

    section_rows = []
    for section, value in data.items():
        if section in ("Objects", "Inventory"):
            continue
        section_rows.append((
            high_id, low_id, str(section),
            json.dumps(value, ensure_ascii=False, separators=(",", ":")),
        ))
    if section_rows:
        conn.executemany(
            "INSERT INTO home_sections "
            "(high_id, low_id, section, data) VALUES (?, ?, ?, ?)",
            section_rows)


# --------------------------------------------------------------------------- #
# migrations
# --------------------------------------------------------------------------- #
def _add_column(conn, table, column, ddl):
    """``ALTER TABLE`` that is safe to re-run."""
    cols = [r[1] for r in conn.execute("PRAGMA table_info(%s)" % table)]
    if column not in cols:
        conn.execute("ALTER TABLE {t} ADD COLUMN {c} {d}".format(
            t=table, c=column, d=ddl))


def _migration_1_baseline(conn):
    """Create the schema every install has had since the start."""
    conn.execute(_ACCOUNT_TABLE_SQL)
    conn.execute(_HOME_TABLE_SQL)


def _migration_2_timestamps(conn):
    """Add bookkeeping columns (and backfill rows written before them)."""
    _add_column(conn, "accounts", "created_at", "INTEGER NOT NULL DEFAULT 0")
    _add_column(conn, "accounts", "last_seen", "INTEGER NOT NULL DEFAULT 0")
    _add_column(conn, "home_states", "updated_at", "INTEGER NOT NULL DEFAULT 0")
    now = int(time.time())
    conn.execute("UPDATE accounts SET created_at=? WHERE created_at=0", (now,))
    conn.execute("UPDATE accounts SET last_seen=? WHERE last_seen=0", (now,))
    conn.execute("UPDATE home_states SET updated_at=? WHERE updated_at=0",
                 (now,))


def _migration_3_indexes(conn):
    """Indexes used by the account picker (name / pass token lookups)."""
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_accounts_name ON accounts(name)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_accounts_token ON accounts(pass_token)")


def _migration_4_normalized_home(conn):
    """Expose object positions and other home state as queryable tables."""
    conn.execute(_HOME_OBJECTS_TABLE_SQL)
    conn.execute(_HOME_INVENTORY_TABLE_SQL)
    conn.execute(_HOME_SECTIONS_TABLE_SQL)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_home_objects_runtime "
        "ON home_objects(high_id, low_id, runtime_id)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_home_objects_data "
        "ON home_objects(high_id, low_id, data_id)")
    for row in conn.execute(
            "SELECT high_id, low_id, data FROM home_states").fetchall():
        _sync_home_projection(conn, row[0], row[1], row[2])


def _migration_5_accurate_coordinates(conn):
    """Preserve the Mach-O's 1/512-tile accurate coordinate remainder."""
    _add_column(conn, "home_objects", "accurate_x",
                "INTEGER NOT NULL DEFAULT 0")
    _add_column(conn, "home_objects", "accurate_y",
                "INTEGER NOT NULL DEFAULT 0")
    conn.execute(
        "UPDATE home_objects SET accurate_x=x*512, accurate_y=y*512 "
        "WHERE accurate_x=0 AND accurate_y=0")


# Order matters: the index in this tuple is the schema version.
MIGRATIONS = (
    _migration_1_baseline,
    _migration_2_timestamps,
    _migration_3_indexes,
    _migration_4_normalized_home,
    _migration_5_accurate_coordinates,
)


# --------------------------------------------------------------------------- #
# Database
# --------------------------------------------------------------------------- #
class Database:
    """Thread-safe SQLite store for accounts and their farm blobs."""

    _instance = None
    _instance_lock = threading.Lock()

    @classmethod
    def instance(cls, path=None):
        """Process-wide shared connection (created on first use)."""
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls(path)
            return cls._instance

    @classmethod
    def reset_instance(cls):
        """Drop the shared handle (tests / switching databases)."""
        with cls._instance_lock:
            if cls._instance is not None:
                try:
                    cls._instance.close()
                except Exception:
                    pass
                cls._instance = None

    def __init__(self, path=None):
        self.path = Path(path) if path else DB_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        # isolation_level=None -> we own transactions (BEGIN/COMMIT), which
        # keeps SQLite from opening one implicitly behind our back.
        self.conn = sqlite3.connect(
            str(self.path), check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self._local = threading.local()
        self._closed = False
        self._configure()
        self._migrate()
        self._check_integrity()

    # -- connection setup --------------------------------------------------- #
    def _configure(self):
        cur = self.conn.cursor()
        # WAL keeps readers (state inspection, backups) off the writer's back.
        try:
            cur.execute("PRAGMA journal_mode=WAL")
        except sqlite3.Error as exc:
            logger.warning("[DB] WAL unavailable: {}".format(exc))
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA busy_timeout=5000")     # ms, not the default 0
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA temp_store=MEMORY")

    def _current_version(self):
        try:
            row = self.conn.execute(
                "SELECT version FROM schema_version").fetchone()
        except sqlite3.Error:
            return 0
        return int(row[0]) if row else 0

    def _migrate(self):
        with self._lock:
            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_version "
                "(version INTEGER NOT NULL)")
            version = self._current_version()
            if version >= len(MIGRATIONS):
                return
            try:
                self.conn.execute("BEGIN")
                for i in range(version, len(MIGRATIONS)):
                    MIGRATIONS[i](self.conn)
                    self.conn.execute("DELETE FROM schema_version")
                    self.conn.execute(
                        "INSERT INTO schema_version (version) VALUES (?)",
                        (i + 1,))
                    logger.info("[DB] migration {} applied to {}".format(
                        i + 1, self.path.name))
                self.conn.execute("COMMIT")
            except Exception:
                self.conn.execute("ROLLBACK")
                raise
            logger.info("[DB] schema version {} for {}".format(
                len(MIGRATIONS), self.path.name))

    def _check_integrity(self):
        try:
            rows = self.conn.execute("PRAGMA quick_check").fetchall()
        except sqlite3.Error as exc:
            logger.error("[DB] quick_check failed: {}".format(exc))
            return
        result = "; ".join(str(r[0]) for r in rows)
        if result != "ok":
            logger.error("[DB] integrity problem in {}: {}".format(
                self.path, result))
        # Rolling backup of a healthy file, never of an empty brand-new one.
        if self._has_rows("accounts") or self._has_rows("home_states"):
            self.backup()

    def _has_rows(self, table):
        try:
            return self.conn.execute(
                "SELECT 1 FROM {} LIMIT 1".format(table)).fetchone() is not None
        except sqlite3.Error:
            return False

    # -- primitives --------------------------------------------------------- #
    def execute(self, sql, params=()):
        """Run a statement under the connection lock and commit it."""
        with self._lock:
            cur = self.conn.execute(sql, params)
            if not self._in_transaction():
                self.conn.commit()
            return cur

    def query_one(self, sql, params=()):
        with self._lock:
            row = self.conn.execute(sql, params).fetchone()
        return dict(row) if row is not None else None

    def query_all(self, sql, params=()):
        with self._lock:
            rows = self.conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def _in_transaction(self):
        return getattr(self._local, "depth", 0) > 0

    @contextmanager
    def transaction(self):
        """Serialize a group of writes: ``BEGIN IMMEDIATE`` / ``COMMIT``.

        Nested use becomes a SAVEPOINT, so helpers can safely call each other
        while a caller already opened a transaction.
        """
        self._lock.acquire()
        depth = getattr(self._local, "depth", 0)
        name = "sp{}".format(depth + 1)
        try:
            if depth == 0:
                self.conn.execute("BEGIN IMMEDIATE")
            else:
                self.conn.execute("SAVEPOINT " + name)
            self._local.depth = depth + 1
            try:
                yield self.conn
            except BaseException:
                self._local.depth = depth
                if depth == 0:
                    self.conn.execute("ROLLBACK")
                else:
                    self.conn.execute("ROLLBACK TO " + name)
                    self.conn.execute("RELEASE " + name)
                raise
            else:
                self._local.depth = depth
                if depth == 0:
                    self.conn.execute("COMMIT")
                else:
                    self.conn.execute("RELEASE " + name)
        finally:
            self._lock.release()

    # -- accounts ----------------------------------------------------------- #
    def get_account(self, high_id, low_id):
        return self.query_one(
            "SELECT * FROM accounts WHERE high_id=? AND low_id=?",
            (high_id, low_id))

    def list_accounts(self):
        return self.query_all(
            "SELECT * FROM accounts ORDER BY high_id, low_id")

    def accounts_with_token(self, pass_token):
        return self.query_all(
            "SELECT * FROM accounts WHERE pass_token=? "
            "ORDER BY high_id, low_id", (pass_token,))

    def next_account_id(self, high_id):
        """Unused ``low_id`` for ``high_id`` (fresh device logging in)."""
        row = self.query_one(
            "SELECT COALESCE(MAX(low_id), 0) AS m FROM accounts "
            "WHERE high_id=?", (high_id,))
        return int((row or {}).get("m") or 0) + 1

    def upsert_account(self, high_id, low_id, **fields):
        """Insert or update one account.  Unknown columns raise ValueError."""
        unknown = [k for k in fields if k not in ACCOUNT_COLUMNS]
        if unknown:
            raise ValueError("unknown account column(s): {}".format(
                ", ".join(sorted(unknown))))
        if not fields:
            return
        # JSON-encode a dict for the stats column so callers stay type safe.
        if isinstance(fields.get("stats"), (dict, list, tuple)):
            try:
                fields["stats"] = json.dumps(fields["stats"])
            except (TypeError, ValueError):
                fields["stats"] = "{}"
        cols = ["high_id", "low_id"] + sorted(fields)
        placeholders = ", ".join("?" * len(cols))
        updates = ", ".join("{c}=excluded.{c}".format(c=c)
                            for c in sorted(fields))
        sql = ("INSERT INTO accounts ({cols}) VALUES ({ph}) "
               "ON CONFLICT(high_id, low_id) DO UPDATE SET {up}").format(
                   cols=", ".join(cols), ph=placeholders, up=updates)
        self.execute(sql, [high_id, low_id] + [fields[k] for k in sorted(fields)])

    def delete_account(self, high_id, low_id):
        """Remove an account together with its farm blob."""
        with self.transaction():
            self.execute("DELETE FROM accounts WHERE high_id=? AND low_id=?",
                          (high_id, low_id))
            self.execute("DELETE FROM home_states WHERE high_id=? AND low_id=?",
                          (high_id, low_id))
        logger.info("[DB] deleted account {}:{}".format(high_id, low_id))

    # -- home state --------------------------------------------------------- #
    def get_home(self, high_id, low_id):
        """Load home state, preferring the normalized SQLite projection."""
        state = self.query_one(
            "SELECT data FROM home_states WHERE high_id=? AND low_id=?",
            (high_id, low_id))
        if not state:
            return None

        sections = self.query_all(
            "SELECT section, data FROM home_sections "
            "WHERE high_id=? AND low_id=? ORDER BY section",
            (high_id, low_id))
        objects = self.query_all(
            "SELECT object_index, data_id, x, y, accurate_x, accurate_y, "
            "mirrored, data "
            "FROM home_objects WHERE high_id=? AND low_id=? "
            "ORDER BY object_index",
            (high_id, low_id))
        inventory = self.query_all(
            "SELECT item_id, amount FROM home_inventory "
            "WHERE high_id=? AND low_id=? ORDER BY item_id",
            (high_id, low_id))
        if not sections and not objects and not inventory:
            return state["data"]

        data = {}
        for row in sections:
            try:
                data[row["section"]] = json.loads(row["data"])
            except (TypeError, ValueError):
                data[row["section"]] = row["data"]

        rebuilt_objects = []
        for row in objects:
            try:
                entry = json.loads(row["data"])
            except (TypeError, ValueError):
                entry = {}
            entry["ID"] = int(row["data_id"])
            entry["X"] = int(row["x"])
            entry["Y"] = int(row["y"])
            entry["_AccurateX"] = int(row["accurate_x"])
            entry["_AccurateY"] = int(row["accurate_y"])
            if row["mirrored"]:
                entry["Mirrored"] = True
            else:
                entry.pop("Mirrored", None)
            rebuilt_objects.append(entry)
        data["Objects"] = rebuilt_objects
        data["Inventory"] = {
            str(row["item_id"]): int(row["amount"])
            for row in inventory
        }
        return json.dumps(data, ensure_ascii=False)

    def upsert_home(self, high_id, low_id, data, **fields):
        """Store the farm blob and its normalized SQLite projection."""
        if not isinstance(data, str):
            data = json.dumps(data)
        values = {"data": data, "updated_at": int(time.time())}
        values.update(fields)
        unknown = [k for k in values if k not in HOME_COLUMNS]
        if unknown:
            raise ValueError("unknown home column(s): {}".format(
                ", ".join(sorted(unknown))))
        cols = ["high_id", "low_id"] + sorted(values)
        placeholders = ", ".join("?" * len(cols))
        updates = ", ".join("{c}=excluded.{c}".format(c=c)
                            for c in sorted(values))
        sql = ("INSERT INTO home_states ({cols}) VALUES ({ph}) "
               "ON CONFLICT(high_id, low_id) DO UPDATE SET {up}").format(
                   cols=", ".join(cols), ph=placeholders, up=updates)
        with self.transaction():
            self.execute(
                sql, [high_id, low_id] + [values[k] for k in sorted(values)])
            _sync_home_projection(self.conn, high_id, low_id, data)

    # -- maintenance -------------------------------------------------------- #
    def backup(self, keep=None):
        """Copy the live database into ``backups/`` (oldest dropped)."""
        if keep is None:
            keep = _config_int("DbBackups", 3)
        if keep <= 0:
            return None
        try:
            target_dir = Path(BACKUP_DIR)
            target_dir.mkdir(parents=True, exist_ok=True)
            stamp = time.strftime("%Y%m%d-%H%M%S")
            target = target_dir / "hayday-{}.db".format(stamp)
            with self._lock:
                dest = sqlite3.connect(str(target))
                try:
                    self.conn.backup(dest)
                finally:
                    dest.close()
            kept = sorted(target_dir.glob("hayday-*.db"))
            for old in kept[:-keep]:
                old.unlink()
            logger.info("[DB] backup written to {}".format(target))
            return target
        except Exception as exc:
            logger.warning("[DB] backup failed: {}".format(exc))
            return None

    def vacuum(self):
        with self._lock:
            self.conn.execute("VACUUM")

    def checkpoint(self):
        """Fold the WAL back into the main file (clean shutdown)."""
        if self._closed:
            return
        try:
            with self._lock:
                self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except sqlite3.Error as exc:
            logger.warning("[DB] checkpoint failed: {}".format(exc))

    def close(self):
        with self._lock:
            if self._closed:
                return
            self.checkpoint()
            self.conn.close()
            self._closed = True


def _config_int(key, default):
    """Read an int out of config.json without importing Utils.Storage
    (Storage imports Account, which imports Database -> circular)."""
    try:
        with open(BASE_DIR / "config.json", "r", encoding="utf-8") as fh:
            value = json.load(fh).get(key, default)
        return int(value)
    except Exception:
        return default


def atomic_write_text(path, text):
    """Write ``text`` to ``path`` without ever leaving a truncated file.

    A partial write (crash, power loss, killed server) used to corrupt
    ``home_state.json``, which the client then refuses to load.  The payload
    goes to a temp file next to the target and is swapped in atomically.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        # os.replace() is atomic on the same volume: readers see either the
        # old file or the complete new one, never a half-written save.
        os.replace(str(tmp), str(path))
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise
