import json
import time
from pathlib import Path

from Utils.Database import Database
from Utils.Logging import logger

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.json"


def read_config():
    """config.json as a dict (never raises: a broken file must not stop logins)."""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


class Account:
    """OOP representation of a player account backed by SQLite.

    Accounts are keyed by ``(high_id, low_id)`` — the pair the client echoes
    back in ``LoginMessage`` as ``accountId = high_id << 32 | low_id`` — so
    several devices can keep separate farms in the same database.
    """

    def __init__(self, db=None, high_id=0, low_id=1, name="Forman",
                 pass_token="hayday", diamonds=9999999, cash=9999999,
                 exp_level=1, exp_points=0, tutorial_completed=False,
                 stats=None):
        # Always the shared connection: a fresh Database() per account would
        # open another SQLite handle (and re-run migrations) for every player.
        self.db = db or Database.instance()
        self.high_id = int(high_id)
        self.low_id = int(low_id)
        self.name = name
        self.pass_token = pass_token
        self.diamonds = int(diamonds or 0)
        self.cash = int(cash or 0)
        self.exp_level = int(exp_level or 1)
        self.exp_points = int(exp_points or 0)
        self.tutorial_completed = bool(tutorial_completed)
        self.stats = stats if isinstance(stats, dict) else {}
        # Set by from_row(); a value of 0 means "created on first save".
        self.created_at = 0

    # -- identity ----------------------------------------------------------- #
    @property
    def account_id(self):
        """64-bit id exactly as it travels in the login packet."""
        return (self.high_id << 32) | (self.low_id & 0xFFFFFFFF)

    @property
    def key(self):
        """Hashable identity used to key the GameState registry."""
        return (self.high_id, self.low_id)

    def __repr__(self):
        return "<Account {}:{} {!r}>".format(
            self.high_id, self.low_id, self.name)

    # -- persistence -------------------------------------------------------- #
    @classmethod
    def from_row(cls, row, db=None):
        stats = row.get("stats") or "{}"
        if not isinstance(stats, str):
            stats = "{}"
        try:
            stats = json.loads(stats) if stats else {}
        except ValueError:
            stats = {}
        account = cls(
            db=db,
            high_id=row["high_id"],
            low_id=row["low_id"],
            name=row.get("name") or "Forman",
            pass_token=row.get("pass_token") or "",
            diamonds=row.get("diamonds") or 0,
            cash=row.get("cash") or 0,
            exp_level=row.get("exp_level") or 1,
            exp_points=row.get("exp_points") or 0,
            tutorial_completed=bool(row.get("tutorial_completed", 0)),
            stats=stats,
        )
        account.created_at = int(row.get("created_at") or 0)
        return account

    @classmethod
    def load(cls, db=None, high_id=None, low_id=None):
        """Load the configured account, creating it on the very first run."""
        db = db or Database.instance()
        conf = read_config()
        if high_id is None:
            high_id = conf.get("AccountHighID", 0)
        if low_id is None:
            low_id = conf.get("AccountLowID", 1)
        row = db.get_account(high_id, low_id)
        if row:
            return cls.from_row(row, db=db)
        # First run: seed from config and persist so later logins find it.
        acct = cls(db=db, high_id=high_id, low_id=low_id, **_seed_from(conf))
        acct.save()
        return acct

    @classmethod
    def get_or_create(cls, high_id, low_id, pass_token=None, db=None):
        """Resolve ``(high_id, low_id)``, seeding a missing row from config.

        A client that still remembers an id for a row we no longer have (a
        restored backup, a wiped database) gets a fresh farm instead of a
        login failure.
        """
        db = db or Database.instance()
        row = db.get_account(high_id, low_id)
        if row:
            return cls.from_row(row, db=db)
        seed = _seed_from(read_config())
        if pass_token:
            seed["pass_token"] = pass_token
        acct = cls(db=db, high_id=high_id, low_id=low_id, **seed)
        acct.save()
        logger.info("[DB] created account {}:{}".format(high_id, low_id))
        return acct

    @classmethod
    def allocate(cls, db=None, pass_token=None):
        """Create a brand new account for a device that has no id yet."""
        db = db or Database.instance()
        conf = read_config()
        high_id = conf.get("AccountHighID", 0)
        low_id = db.next_account_id(high_id)
        return cls.get_or_create(high_id, low_id, pass_token=pass_token, db=db)

    def save(self):
        """Write this row to SQLite.

        Only ``Account.load/get_or_create`` (first-run seeding) and
        ``GameState.flush()`` should call this.  Gameplay code must use the
        ``GameState.account_*`` helpers so the write is batched with the farm
        blob and the dirty flags stay accurate.
        """
        now = int(time.time())
        if not self.created_at:
            self.created_at = now
        self.db.upsert_account(
            self.high_id, self.low_id,
            name=self.name,
            pass_token=self.pass_token,
            diamonds=self.diamonds,
            cash=self.cash,
            exp_level=self.exp_level,
            exp_points=self.exp_points,
            tutorial_completed=1 if self.tutorial_completed else 0,
            stats=self.stats,
            created_at=self.created_at,
            last_seen=now,
        )

    # -- helpers ------------------------------------------------------------ #
    def to_config(self):
        """The account fields every reader of config.json expects to see."""
        return {
            "AccountHighID": self.high_id,
            "AccountLowID": self.low_id,
            "PassToken": self.pass_token,
            "Name": self.name,
            "Diamonds": self.diamonds,
            "Cash": self.cash,
            "ExpLevel": self.exp_level,
            "ExpPoints": self.exp_points,
            "TutorialCompleted": self.tutorial_completed,
            "Stats": self.stats,
        }

    def increment_stat(self, key, amount=1):
        self.stats[key] = self.stats.get(key, 0) + amount
        return self.stats[key]

    def set_stat(self, key, value):
        self.stats[key] = value
        return value


def _seed_from(conf):
    """Starting values for a brand new account, taken from config.json."""
    return {
        "name": conf.get("Name", "Forman"),
        "pass_token": conf.get("PassToken", "hayday"),
        "diamonds": conf.get("Diamonds", 9999999),
        "cash": conf.get("Cash", 9999999),
        "exp_level": conf.get("ExpLevel", 1),
        "exp_points": conf.get("ExpPoints", 0),
        "tutorial_completed": bool(conf.get("TutorialCompleted", False)),
        "stats": {},
    }
