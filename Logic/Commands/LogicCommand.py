from Utils.Logging import logger
import json
import os
from Utils.Reader import Reader
from Logic.GameData import game_data
from Logic.GameTime import now_seconds

# Payload layouts recovered from the client binary by tools/decode_macho.py
# (ByteStream::readXxx calls in each Logic*Command::createAndDecode).
FORMATS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "command_formats.json")
try:
    with open(FORMATS_PATH, "r", encoding="utf-8") as _fh:
        COMMAND_FORMATS = json.load(_fh)
except (OSError, ValueError):
    COMMAND_FORMATS = {}


class LogicCommand:
    """Base class for all Logic*Command handlers.

    Subclasses set ``NAME`` and ``TYPE`` (the real id, from the game
    binary) and override ``execute``. Payload layout per command is
    discovered at runtime: ``decode`` reads every field listed in the
    class ``FIELDS`` tuple (from ``command_formats.json``) with
    ``read_field``; the trailing ``tick`` field is stored as ``self.tick``.
    """

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # The binary layout is authoritative: overwrite any guessed FIELDS
        # / TYPE left in the handler files (a wrong length desyncs the whole
        # EndClientTurn command stream).
        fmt = COMMAND_FORMATS.get(cls.NAME)
        if fmt:
            if fmt.get("fields"):
                cls.FIELDS = list(fmt["fields"])
            if fmt.get("type") is not None:
                cls.TYPE = fmt["type"]
        if "execute" in cls.__dict__:
            _orig = cls.__dict__["execute"]
            def _wrapped(self, state):
                result = _orig(self, state)
                try:
                    if result:
                        state.account_stat(cls.NAME, 1)
                        # Generic ACTION handlers mutate home data and rely on
                        # this wrapper to flag it (see Logic.Actions).
                        state.save()
                except Exception:
                    pass
                return result
            cls.execute = _wrapped


    TYPE = None  # numeric command id (from command_formats.json)
    NAME = "LogicCommand"
    FIELDS = []
    ACTION = None  # generic action category (see Logic/Actions.py)

    def __init__(self, payload=b""):
        if payload is None:
            payload = b""
        self.payload = payload
        self.args = []
        self.raw = payload.hex() if isinstance(payload, (bytes, bytearray)) else ""
        # Default decoded fields so handlers never hit missing-attribute errors
        # when given an empty/partial payload.
        for i in range(len(getattr(self, "FIELDS", []) or [])):
            setattr(self, "f%d" % i, 0)
            self.args.append(0)
        self.tick = 0

    # ------------------------------------------------------------------ #
    # Decoding
    # ------------------------------------------------------------------ #
    @staticmethod
    def read_field(r, kind):
        """Read one payload field of the given kind from a Reader."""
        if kind == "int":
            # The native ByteStream::readInt returns a signed int. Negative
            # values are common in move/position deltas and -1 references.
            return r.readInt(signed=True)
        if kind == "short":
            return r.readShort()
        if kind == "byte":
            v = r.readByte()
            if v > 127:
                v -= 256
            return v
        if kind == "long":
            return r.readLong()
        if kind == "bool":
            return r.readBool()
        if kind == "string":
            return r.readString()
        if kind in ("vint", "vlong"):
            return r.readVInt()
        if kind == "ubyte":
            return r.readUInteger(1)
        if kind == "ushort":
            return r.readUInteger(2)
        if kind == "uint":
            return r.readUInteger(4)
        if kind == "ulong":
            return r.readUInteger(8)
        if kind == "tick":
            return r.readInt(signed=True)
        if kind == "counted_int_pairs":
            # Some commands are arrays rather than a fixed field list.  The
            # client writes a byte count followed by that many int/int pairs
            # (LogicBuyGoodsWithDiamondsCommand is the first such command).
            count = r.readByte()
            return [(r.readInt(), r.readInt()) for _ in range(count)]
        raise ValueError("unknown field kind %r" % kind)

    def decode_fields(self, r, fields=None):
        """Parse the real binary payload layout into self.args/f{i}."""
        fields = self.FIELDS if fields is None else fields
        # __init__ seeds f{i}/args with zeros so undecoded handlers are safe.
        # A real decode must replace, not append to, that placeholder list --
        # otherwise arg(0) silently returns the stale leading zero.
        self.args = []
        for i, kind in enumerate(fields):
            value = self.read_field(r, kind)
            setattr(self, "f%d" % i, value)
            if kind == "tick":
                self.tick = value
            self.args.append(value)
        self.raw = getattr(r, "buffer", b"").hex() if isinstance(getattr(r, "buffer", None), (bytes, bytearray)) else ""
        return self

    def decode(self):
        """Best-effort decode (kept for handlers that override FIELDS)."""
        if not self.payload:
            return
        self.decode_fields(Reader(self.payload), self.FIELDS)

    def arg(self, index, default=0):
        """Safe accessor for decoded args."""
        if 0 <= index < len(self.args):
            return self.args[index]
        return default

    # ------------------------------------------------------------------ #
    # Execution helpers (operate on the shared GameState)
    # ------------------------------------------------------------------ #
    @property
    def now(self):
        return now_seconds()

    def inventory(self, state):
        return state.home.inventory

    def give(self, state, item, count=1):
        from Logic import Storage
        accepted = Storage.store(
            state.home.data, self.inventory(state), item, count)
        if accepted < int(count or 0):
            logger.info(
                "[CMD] {} -> storage full for item {}: stored {}/{}".format(
                    self.NAME, item, accepted, count))
        if accepted:
            logger.info("[CMD] {} -> give {} x{}".format(
                self.NAME, item, accepted))
        return accepted

    def take(self, state, item, count=1):
        inv = self.inventory(state)
        if inv.take(item, count):
            return True
        logger.info("[CMD] {} -> cannot take {} x{} (have {})".format(
            self.NAME, item, count, inv.amount(item)))
        return False

    def spend_cash(self, state, amount):
        # All resource writes go through GameState: one dirty flag, one
        # transaction per turn, no mid-turn account.save() calls.
        if not state.account_spend("cash", amount):
            logger.info("[CMD] {} -> not enough cash ({})".format(self.NAME, amount))
            return False
        state.account_stat("cash_spent", int(amount or 0))
        logger.info("[CMD] {} -> spend cash {}".format(self.NAME, amount))
        return True

    def spend_diamonds(self, state, amount):
        if not state.account_spend("diamonds", amount):
            logger.info("[CMD] {} -> not enough diamonds ({})".format(self.NAME, amount))
            return False
        state.account_stat("diamonds_spent", int(amount or 0))
        logger.info("[CMD] {} -> spend diamonds {}".format(self.NAME, amount))
        return True

    def earn_cash(self, state, amount):
        state.account_delta(cash=int(amount or 0))
        state.account_stat("cash_earned", int(amount or 0))
        logger.info("[CMD] {} -> earn cash {}".format(self.NAME, amount))

    def earn_diamonds(self, state, amount):
        state.account_delta(diamonds=int(amount or 0))
        state.account_stat("diamonds_earned", int(amount or 0))
        logger.info("[CMD] {} -> earn diamonds {}".format(self.NAME, amount))

    # ------------------------------------------------------------------ #
    # Data table helpers
    # ------------------------------------------------------------------ #
    @property
    def data(self):
        """The decoded client tables (``data/*.csv``)."""
        return game_data()

    def data_row(self, global_id):
        """Row of a global id, or ``None`` when unknown."""
        return self.data.row_for(global_id)

    @staticmethod
    def good_units(row):
        """Output units produced by one recipe (``LogicGoodData::getUnits``)."""
        if row is None:
            return 1
        return max(1, row.i("Units", 1))

    def item(self, name):
        """CSV :class:`~Logic.GameData.Row` of an item, by name."""
        return self.data.item(name)

    def item_id(self, name):
        """Global id of an item looked up by its CSV name."""
        return self.data.item_id(name)

    def require_unlock(self, state, row, key="UnlockLevel"):
        """Client-equivalent ``LogicInventory::isUnlocked`` check."""
        if row is None:
            return True
        level = row.i(key, 0)
        if level <= 0:
            return True
        current = int(getattr(state.account, "exp_level", 1) or 1)
        if current >= level:
            return True
        logger.info("[CMD] {} -> {} needs level {} (have {})".format(
            self.NAME, row.name, level, current))
        return False

    def spend_price(self, state, row, count=0):
        """Charge the client's price for ``row`` (diamonds or cash)."""
        if row is None:
            return True
        currency, price = self.data.shop_price(row, count=count)
        if price <= 0:
            return True
        if currency == "diamond":
            return self.spend_diamonds(state, price)
        return self.spend_cash(state, price)

    @staticmethod
    def instant_complete_price(base_price, seconds_left, total_seconds):
        """Port ``LogicGameConfig::getInstantCompletePrice``.

        The binary scales the full-duration price by the time still left and
        rounds up, with a minimum of one diamond.
        """
        try:
            base_price = int(base_price or 0)
            seconds_left = max(0, int(seconds_left or 0))
            total_seconds = max(1, int(total_seconds or 0))
        except (TypeError, ValueError):
            return 0
        if base_price <= 0:
            return 0
        numerator = seconds_left * base_price
        return max(1, (numerator + total_seconds - 1) // total_seconds)

    def give_named(self, state, name, count=1):
        """Grant an item by CSV name (used for level-up rewards)."""
        if not name or count <= 0:
            return
        item = self.item_id(name)
        if item is None:
            logger.info("[CMD] {} -> unknown reward item {!r}".format(
                self.NAME, name))
            return
        self.give(state, item, count)

    def order_reward(self, state, order_index=0):
        """Data-driven order payout ``(cash, exp)``.

        Orders are generated at runtime by the client, so their exact
        contents are not on disk.  The level's ``OrderMinValue``/
        ``OrderMaxValue`` window (exp_levels.csv) bounds the goods value and
        the typical OrderPrice/OrderValue and OrderExp/OrderValue ratios of
        the goods tables turn it into a reward.
        """
        level = int(getattr(state.account, "exp_level", 1) or 1)
        row = self.data.level_row(level)
        low = row.i("OrderMinValue", 0) if row is not None else 0
        high = row.i("OrderMaxValue", 0) if row is not None else 0
        if high > low:
            value = low + (abs(int(order_index)) * 7) % (high - low + 1)
            return max(1, int(value * 2.5)), max(1, int(value * 2.0))
        return 150, 50  # early levels have no value window in the CSV

    def _grant_level_rewards(self, state, level):
        """Apply the ``GoodReward``/``GoodAmount`` rows of exp_levels.csv."""
        for name, count in self.data.level_rewards(level):
            key = str(name).strip().lower()
            if key == "cash":
                self.earn_cash(state, count)
            elif key in ("freediamonds", "diamonds"):
                self.earn_diamonds(state, count)
            else:
                self.give_named(state, name, count)

    def earn_exp(self, state, amount):
        """Add exp and apply the real ``exp_levels.csv`` curve.

        ``ExpToNextLevel`` is the exp needed to advance *from* that level;
        extra GoodReward/GoodAmount continuation rows are granted on every
        level up (coins, diamonds, seeds, tools, ...).
        """
        try:
            amount = int(amount)
        except (TypeError, ValueError):
            return
        if amount <= 0:
            return
        with state.lock:
            state.account_delta(exp_points=amount)
            state.account_stat("exp_earned", amount)
            acct = state.account
            level = int(getattr(acct, "exp_level", 1) or 1)
            points = int(getattr(acct, "exp_points", 0) or 0)
            max_level = self.data.max_level
            while level < max_level:
                needed = self.data.exp_to_next(level)
                if needed <= 0 or points < needed:
                    break
                points -= needed
                level += 1
                # One state method per change; the actual SQLite write happens
                # once in GameState.flush() after the whole turn.
                state.account_set(exp_level=level, exp_points=points)
                state.account_stat("level_ups", 1)
                self._grant_level_rewards(state, level)
                logger.info("[CMD] {} -> level up to {} (rewarded)".format(
                    self.NAME, level))

    # ------------------------------------------------------------------ #
    # Entry point
    # ------------------------------------------------------------------ #
    def execute(self, state):
        """Default: run the generic action if declared, otherwise log."""
        if self.ACTION:
            from Logic.Actions import perform_action
            try:
                return perform_action(self, state)
            except Exception as e:
                logger.info("[CMD] action error for {}: {}".format(self.NAME, e))
                return False
        logger.info("[CMD] {} not implemented (args={}, raw={})".format(
            self.NAME, self.args, self.raw))
        try:
            state.save()
        except Exception:
            pass
        return False
