"""Per-account game state and the persistence policy around it.

Layout
------
Clients are served by threads, and one player's turn must never be mixed
into another player's farm.  States are therefore cached per
``(high_id, low_id)``: two connections logged in as the same account share
one object (guarded by ``state.lock``), different accounts never see each
other's data.

Write policy
------------
``save()`` only marks the state dirty — a single command turn calls it many
times, and each call used to serialize the whole farm and commit two
transactions.  ``flush()`` persists account + farm blob in one transaction and
is invoked by ``Main`` after every packet, on disconnect and at exit, so the
cost per turn drops to exactly one write.

Account resources (diamonds, cash, level, exp) must go through
:meth:`GameState.account_set`, ``account_delta`` or ``account_spend``: they
mark the account dirty and never write to SQLite mid-turn.  Dirty flags are
cleared only after a successful commit, so a failed write is retried instead
of silently losing progress.
"""
import atexit
import json
import threading
from pathlib import Path

from Logic.Account import Account, read_config
from Logic.Home import Home, STATE_PATH
from Utils.Database import Database, atomic_write_text
from Utils.Logging import logger

BASE_DIR = Path(__file__).resolve().parent.parent


def home_path_for(high_id, low_id):
    """Export file for an account.

    The account configured in config.json keeps using ``JSON/home_state.json``
    (backwards compatible with existing installs); every other player gets its
    own file instead of silently sharing that one.
    """
    conf = read_config()
    if (conf.get("AccountHighID", 0) == high_id
            and conf.get("AccountLowID", 1) == low_id):
        return STATE_PATH
    return STATE_PATH.parent / "home_state_{}_{}.json".format(high_id, low_id)


class GameState:
    """Account + farm state for one ``(high_id, low_id)`` pair."""

    _states = {}
    _registry_lock = threading.RLock()

    # -- registry ----------------------------------------------------------- #
    @classmethod
    def for_account(cls, high_id, low_id, account=None):
        """Return (creating if needed) the state of one account."""
        high_id, low_id = int(high_id), int(low_id)
        with cls._registry_lock:
            state = cls._states.get((high_id, low_id))
            if state is None:
                state = cls(high_id, low_id, account=account)
                cls._states[(high_id, low_id)] = state
            elif account is not None:
                state.account = account
            return state

    @classmethod
    def for_device(cls, device):
        """State of the account the device logged in with."""
        high_id = getattr(device, "high_id", None)
        low_id = getattr(device, "low_id", None)
        if high_id is None or low_id is None:
            # Not logged in yet: fall back to the configured account so a
            # mis-sequenced packet can never write into another player's farm.
            conf = read_config()
            high_id = conf.get("AccountHighID", 0)
            low_id = conf.get("AccountLowID", 1)
        return cls.for_account(high_id, low_id)

    @classmethod
    def instance(cls):
        """Configured account state (kept for callers without a device)."""
        conf = read_config()
        return cls.for_account(conf.get("AccountHighID", 0),
                               conf.get("AccountLowID", 1))

    @classmethod
    def drop(cls, high_id, low_id):
        with cls._registry_lock:
            return cls._states.pop((int(high_id), int(low_id)), None)

    # -- flushing ----------------------------------------------------------- #
    @classmethod
    def flush_device(cls, device):
        try:
            return cls.for_device(device).flush()
        except Exception:
            logger.exception("[DB] flush failed")
            return False

    @classmethod
    def flush_all(cls):
        with cls._registry_lock:
            states = list(cls._states.values())
        flushed = 0
        for state in states:
            try:
                if state.flush():
                    flushed += 1
            except Exception:
                logger.exception("[DB] flush failed for {}".format(state.key))
        return flushed

    @classmethod
    def shutdown(cls):
        """Last chance to persist before the process goes away."""
        try:
            cls.flush_all()
        except Exception:
            logger.exception("[DB] shutdown flush failed")
        try:
            Database.instance().checkpoint()
        except Exception:
            pass

    # -- construction ------------------------------------------------------- #
    def __init__(self, high_id, low_id, account=None, db=None):
        self.db = db or Database.instance()
        self.high_id = int(high_id)
        self.low_id = int(low_id)
        self.account = account or Account.load(
            db=self.db, high_id=self.high_id, low_id=self.low_id)
        self.home = Home(path=home_path_for(self.high_id, self.low_id))
        # Guards everything that mutates this account (turns come in on
        # different threads for a reconnecting player).
        self.lock = threading.RLock()
        self._home_dirty = False
        self._account_dirty = False
        # Read once: this is touched on every flush.
        self.export_json = bool(read_config().get("ExportHomeJson", True))
        self._load()

    # -- loading ------------------------------------------------------------ #
    def _load(self):
        """DB blob wins; the JSON file is only a fallback for old installs."""
        try:
            saved = self.db.get_home(self.high_id, self.low_id)
            if saved:
                data = json.loads(saved)
                if isinstance(data, dict):
                    before = json.loads(json.dumps(data))
                    with self.lock:
                        self.home.data = data
                        self.home.apply_defaults(reset_runtime=True)
                        from Logic import Achievements
                        Achievements.normalize(self)
                        # Loading also repairs legacy ids and malformed
                        # tutorial records.  Persist those repairs even when
                        # the client performs no further gameplay action.
                        if self.home.data != before:
                            self._home_dirty = True
                return
        except Exception:
            logger.exception("[DB] could not read farm blob {}:{}".format(
                self.high_id, self.low_id))
        # No blob yet: keep whatever the JSON layer produced (first run or a
        # database that predates home_states), then persist it.
        with self.lock:
            self.home.apply_defaults(reset_runtime=True)
            from Logic import Achievements
            Achievements.normalize(self)
        self._home_dirty = True
        self._account_dirty = True

    def reload(self):
        """Re-read both halves from the database."""
        with self.lock:
            self._home_dirty = False
            self._account_dirty = False
            self.account = Account.load(
                db=self.db, high_id=self.high_id, low_id=self.low_id)
            self._load()

    # -- saving ------------------------------------------------------------- #
    @property
    def key(self):
        return (self.high_id, self.low_id)

    @property
    def dirty(self):
        """True when either half of the state needs to be written."""
        return self._home_dirty or self._account_dirty

    def save(self, immediate=False):
        """Mark the farm dirty (cheap; see module docstring)."""
        with self.lock:
            self._home_dirty = True
        if immediate:
            self.flush()

    # -- account resources -------------------------------------------------- #
    # Whitelist mirrors the columns in Utils.Database.ACCOUNT_COLUMNS: never
    # let a packet write an arbitrary attribute into the player row.
    ACCOUNT_FIELDS = ("diamonds", "cash", "exp_level", "exp_points",
                      "name", "pass_token", "tutorial_completed")
    NUMERIC_FIELDS = ("diamonds", "cash", "exp_level", "exp_points")

    def account_set(self, **values):
        """Set whitelisted account fields and mark them dirty."""
        with self.lock:
            for key, value in values.items():
                if key not in self.ACCOUNT_FIELDS:
                    raise ValueError("unknown account field: {}".format(key))
                if key in self.NUMERIC_FIELDS:
                    value = max(0, int(value or 0))
                setattr(self.account, key, value)
            self._account_dirty = True

    def account_delta(self, **deltas):
        """Add (or subtract) numeric fields, clamping them at zero."""
        with self.lock:
            for key, delta in deltas.items():
                if key not in self.NUMERIC_FIELDS:
                    raise ValueError("non numeric account field: {}".format(key))
                current = int(getattr(self.account, key) or 0)
                setattr(self.account, key, max(0, current + int(delta or 0)))
            self._account_dirty = True

    def account_spend(self, key, amount):
        """Spend a numeric resource atomically; False when insufficient."""
        amount = int(amount or 0)
        if amount <= 0:
            return True
        if key not in self.NUMERIC_FIELDS:
            raise ValueError("non numeric account field: {}".format(key))
        with self.lock:
            if int(getattr(self.account, key) or 0) < amount:
                return False
            setattr(self.account, key,
                    int(getattr(self.account, key)) - amount)
            self._account_dirty = True
            return True

    def account_stat(self, key, amount=1):
        """Increment a player stat (persisted in the same account row)."""
        with self.lock:
            self.account.increment_stat(key, amount)
            self._account_dirty = True

    def flush(self):
        """Persist the changed halves in one transaction.  Returns True if written."""
        with self.lock:
            if not self.dirty:
                return False
            # Serialize inside the lock: a concurrent turn must not mutate the
            # farm halfway through json.dumps().  Account-only changes (most
            # reward commands) do not pay for a farm serialization at all.
            # Persist hidden fixed-point coordinates in SQLite, but the JSON
            # export and client home packet strip them in Home.to_json().
            blob = self.home.to_json(include_internal=True) \
                if self._home_dirty else None
            try:
                with self.db.transaction():
                    if self._account_dirty:
                        self.account.save()
                    if blob is not None:
                        self.db.upsert_home(self.high_id, self.low_id, blob)
            except Exception:
                # Keep both flags set so the next packet retries the write.
                logger.exception("[DB] flush failed for {}:{}".format(
                    self.high_id, self.low_id))
                return False
            self._account_dirty = False
            if blob is not None:
                self._home_dirty = False
            # Keep the optional export ordered with state writes.  Releasing
            # the lock first lets a newer flush write the JSON and an older
            # thread overwrite it with stale data.
            if blob is not None and self.export_json:
                try:
                    atomic_write_text(
                        self.home.path, self.home.to_json(include_internal=False))
                except OSError as exc:
                    logger.warning("[DB] home export failed: {}".format(exc))
        return True


# Persist whatever is pending when the interpreter goes down (Ctrl-C, SIGTERM
# handlers that exit, ...).
atexit.register(GameState.shutdown)
