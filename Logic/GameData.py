"""Decoded Hay Day data tables (``data/*.csv``).

The client ships its balance data as LZMA compressed CSVs.  ``tools/
decode_data.py`` unpacks every table into ``data/`` using the community
``supercell-resource-decoder``; this module loads them back into Python
objects so the server can use the *real* prices, grow times, experience
curve, requirements and unlock levels instead of hardcoded stubs.

File layout (as written by the game's CSV writer)::

    row 0   column names      (``Name``, ``Price``, ``TimeMin``, ...)
    row 1   column types      (``int`` / ``String`` / ``boolean`` / ...)
    row 2+  data rows

A data row whose first cell is empty is a *continuation* row of the
previously named row: extra recipe requirements, building upgrade tiers,
extra level-up rewards, ...  They are exposed as ``Row.subs``.

Global ids follow ``table_id * 100000 + instance_index`` (see
``LogicClientAvatar`` / ``LogicDataTables::getDataById`` in the binary).
"""
import csv
import threading
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# --------------------------------------------------------------------------- #
# table id -> CSV file name (extracted from
# LogicResources::createDataTableResourcesArray / __GLOBAL__I_a_37)
# --------------------------------------------------------------------------- #
TABLES = {
    1: "locales", 2: "cars", 3: "decorations", 4: "fields", 5: "forests",
    6: "processing_buildings", 7: "sounds", 8: "wonders", 9: "tiles",
    10: "houses", 11: "animal_habitats", 12: "animal_habitat_pieces",
    13: "animals", 14: "warehouses", 15: "animal_goods", 16: "animal_feed",
    17: "boosters", 18: "silos", 19: "money", 21: "construction_buildings",
    22: "tools", 23: "dairy_goods", 24: "bakery_goods",
    25: "cake_oven_goods", 26: "pie_oven_goods", 27: "sugar_mill_goods",
    28: "loom_goods", 29: "popcorn_pot_goods", 30: "barbecue_grill_goods",
    31: "exp_levels", 32: "order_tables", 33: "predefined_orders",
    34: "orders", 35: "roadside_shop", 36: "tutorials", 37: "events",
    38: "collection_tools", 39: "scarecrows", 40: "mailboxes",
    41: "newspaper_stories", 42: "newspaper_layout", 43: "cash_packages",
    44: "diamond_packages", 45: "ambient_animals",
    46: "ambient_animal_spawners", 47: "fonts", 48: "deco_fences",
    49: "people", 50: "people_spawners", 51: "tutorial_people_orders",
    52: "features", 53: "mystery_boxes", 54: "mystery_box_spawners",
    55: "ai_roadside_shop", 56: "docks", 57: "shacks", 58: "boats",
    59: "achievements", 60: "juice_press_goods", 61: "fruits",
    62: "fruit_trees", 63: "mines", 64: "mine_goods", 65: "smelter_goods",
    66: "jam_maker_goods", 67: "notifications", 68: "special_orders",
    69: "ice_cream_maker_goods", 70: "boy", 71: "boy_box", 72: "faqs",
    73: "movie_tickets", 74: "wheel_cars", 75: "jeweler_goods",
    76: "tracking_events", 77: "vouchers", 78: "pets", 79: "pet_habitats",
    80: "expansions", 81: "expansion_fences", 82: "cafe_goods",
    83: "offers", 84: "candy_machine_goods",
}
TABLE_IDS = {name: tid for tid, name in TABLES.items()}

# Well known tables (used all over the code base).
MONEY_TABLE = 19
EXP_TABLE = 31
FIELD_TABLE = 4
ANIMAL_TABLE = 13
FEATURE_TABLE = 52
ACHIEVEMENT_TABLE = 59
TUTORIAL_TABLE = 36

# Bit lists written into the avatar payload (table id -> instance count).
BIT_LIST_ROWS = {
    3: 53, 4: 11, 6: 17, 13: 5, 15: 5, 16: 5, 17: 0, 22: 5, 23: 4, 24: 7,
    25: 6, 26: 5, 27: 3, 28: 3, 29: 3, 30: 5, 33: 7, 36: 60, 38: 9,
    48: 8, 51: 3, 60: 5, 61: 6, 64: 3, 65: 3, 66: 4, 68: 10, 69: 4,
    75: 3, 77: 4, 78: 9, 80: 17, 82: 5, 84: 5,
}
BITLIST_TABLES = sorted(BIT_LIST_ROWS)

# money.csv instance ids (kept for backwards compatibility).
MONEY_ROWS = {'Cash': 0, 'Diamonds': 1, 'ExpLevel': 2, 'ExpPoints': 3}

# Tables that hold "items" (goods / crops / tools) addressable by name.
# Order matters: the first table that contains a name wins.
ITEM_TABLES = [
    4,    # fields (crops)
    22,   # tools
    16,   # animal_feed
    15,   # animal_goods
    23, 24, 25, 26, 27, 28, 29, 30,  # dairy / bakery / cake / pie / sugar /
    60, 65, 66, 69, 75, 82, 84,      # loom / popcorn / bbq / juice / smelter /
    38,   #            jam / ice cream / jeweler / cafe / candy
    61,   # fruits
    64,   # mine_goods
    77,   # vouchers
    78,   # pets
    3,    # decorations
    48,   # deco_fences
]

# Tables whose rows are "goods" produced by a processing building.
GOODS_TABLES = [16, 23, 24, 25, 26, 27, 28, 29, 30, 60, 65, 66, 69, 75,
                82, 84]

_INT_TYPES = {"int", "Int"}
_BOOL_TYPES = {"boolean", "Boolean"}
_TYPE_TOKENS = _INT_TYPES | _BOOL_TYPES | {"String", "string", "t", "e"}


def tutorial_instance(value):
    """Normalize a tutorial id to its 0-based CSV instance id."""
    try:
        v = int(value)
    except (TypeError, ValueError):
        return None
    if v >= TUTORIAL_TABLE * 100000:
        v -= TUTORIAL_TABLE * 100000
    return v if v >= 0 else None


# --------------------------------------------------------------------------- #
# CSV value conversion
# --------------------------------------------------------------------------- #
def _convert(raw, typ):
    """Convert one CSV cell using the column's declared type."""
    if raw is None:
        raw = ""
    raw = raw.strip()
    if typ in _INT_TYPES:
        if not raw:
            return 0
        try:
            return int(raw)
        except ValueError:
            try:
                return int(float(raw))
            except ValueError:
                return raw
    if typ in _BOOL_TYPES:
        return raw.lower() in ("true", "1", "yes", "y")
    return raw


def _is_type_row(row):
    cells = [c.strip() for c in (row or []) if c and c.strip()]
    return bool(cells) and all(c in _TYPE_TOKENS for c in cells)


# --------------------------------------------------------------------------- #
# Rows / tables
# --------------------------------------------------------------------------- #
class Row:
    """One instance (named CSV row) plus its continuation rows."""

    __slots__ = ("table", "index", "name", "values", "subs")

    def __init__(self, table, index, name, values, subs=None):
        self.table = table          # owning Table
        self.index = index          # 0 based instance id
        self.name = name
        self.values = values        # column -> typed value
        self.subs = subs if subs is not None else []

    # -- basic accessors -------------------------------------------------- #
    def get(self, key, default=None):
        value = self.values.get(key)
        if value is None or value == "":
            return default
        return value

    def i(self, key, default=0):
        value = self.values.get(key)
        if value is None or value == "":
            return default
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return default

    def s(self, key, default=""):
        value = self.values.get(key)
        if value is None:
            return default
        return str(value)

    def b(self, key, default=False):
        value = self.values.get(key)
        if value is None or value == "":
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("true", "1", "yes", "y")

    def seconds(self, min_key="TimeMin", sec_key="TimeSec"):
        """``TimeMin``/``TimeSec`` pair -> seconds (the game's
        ``LogicFieldData::getGrowTimeSeconds`` / ``LogicGoodData``
        convention: seconds + 60 * minutes)."""
        return self.i(sec_key, 0) + 60 * self.i(min_key, 0)

    def requirements(self):
        """Recipe inputs: ``[(item_name, amount), ...]``.

        The first requirement lives on the named row, every extra one on a
        continuation row (this is how ``*_goods.csv`` stores recipes).
        """
        out = []
        sources = [self.values] + self.subs
        for src in sources:
            name = src.get("Requirement")
            if not name:
                continue
            amount = src.get("RequirementAmount")
            try:
                amount = int(str(amount).strip() or 0)
            except (TypeError, ValueError):
                amount = 0
            if amount > 0:
                out.append((name, amount))
        return out

    @property
    def global_id(self):
        return self.table.tid * 100000 + self.index

    @property
    def tid(self):
        return self.table.tid

    def __repr__(self):
        return "<Row {}#{} {!r}>".format(self.table.name, self.index,
                                         self.name)


class Table:
    """A decoded CSV file: an ordered list of :class:`Row`."""

    __slots__ = ("tid", "name", "rows", "by_name")

    def __init__(self, tid, name, rows):
        self.tid = tid
        self.name = name
        self.rows = rows
        self.by_name = {}
        for row in rows:
            row.table = self
            if row.name and row.name not in self.by_name:
                self.by_name[row.name] = row
            # Also index by the raw first column (Level, TID, ...) so
            # lookups work for tables without a Name column.
            first = row.values.get(next(iter(row.values), None)) \
                if row.values else None
            if first and first not in self.by_name:
                self.by_name.setdefault(str(first), row)

    def __len__(self):
        return len(self.rows)

    def row(self, index):
        if isinstance(index, str) and not index.isdigit():
            return self.find(index)
        try:
            index = int(index)
        except (TypeError, ValueError):
            return None
        if 0 <= index < len(self.rows):
            return self.rows[index]
        return None

    def find(self, name):
        if name is None:
            return None
        return self.by_name.get(str(name))


# --------------------------------------------------------------------------- #
# Loader
# --------------------------------------------------------------------------- #
def _read_csv(path):
    with open(path, "r", newline="", encoding="utf-8-sig",
              errors="replace") as handle:
        return list(csv.reader(handle))


def _load_table(path, tid, name):
    raw_rows = _read_csv(path)
    if not raw_rows:
        return Table(tid, name, [])

    headers = [h.strip() for h in raw_rows[0]]
    body = raw_rows[1:]
    types = []
    if body and _is_type_row(body[0]):
        types = [t.strip() for t in body[0]]
        body = body[1:]

    def to_values(raw):
        values = {}
        for i, column in enumerate(headers):
            if not column:
                continue
            cell = raw[i] if i < len(raw) else ""
            values[column] = _convert(cell, types[i] if i < len(types) else "")
        return values

    def first_cell(raw):
        return raw[0].strip() if raw and len(raw) else ""

    def is_blank(raw):
        return not raw or all(not str(c).strip() for c in raw)

    usable = [r for r in body if not is_blank(r)]
    has_named = any(first_cell(r) for r in usable)

    rows = []
    if has_named:
        current = None
        for raw in usable:
            values = to_values(raw)
            head = first_cell(raw)
            if head:
                current = Row(None, len(rows), head, values)
                rows.append(current)
            elif current is not None:
                current.subs.append(values)
            else:
                current = Row(None, len(rows), "", values)
                rows.append(current)
    else:
        for raw in usable:
            values = to_values(raw)
            rows.append(Row(None, len(rows), "", values))

    return Table(tid, name, rows)


# --------------------------------------------------------------------------- #
# GameData
# --------------------------------------------------------------------------- #
class GameData:
    """Lazy, process wide access to the decoded CSV tables."""

    _instance = None
    _instance_lock = threading.Lock()

    @classmethod
    def instance(cls):
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
        return cls._instance

    def __init__(self, data_dir=None):
        self.data_dir = Path(data_dir) if data_dir else DATA_DIR
        self._tables = {}
        self._named = {}
        self._items = None
        # Reentrant: the item index builds itself while holding the lock and
        # calls table() (which locks again) for every item table.
        self._lock = threading.RLock()

    # -- table access ------------------------------------------------------ #
    def table(self, key):
        """Return the :class:`Table` for a table id or file name."""
        if isinstance(key, str):
            tid = TABLE_IDS.get(key)
            if tid is None:
                return None
        else:
            try:
                tid = int(key)
            except (TypeError, ValueError):
                return None
        if tid not in TABLES:
            return None
        with self._lock:
            table = self._tables.get(tid)
            if table is None:
                path = self.data_dir / (TABLES[tid] + ".csv")
                if not path.exists():
                    return None
                table = _load_table(path, tid, TABLES[tid])
                self._tables[tid] = table
            return table

    def rows(self, key):
        table = self.table(key)
        return table.rows if table else []

    def row(self, table_key, index):
        table = self.table(table_key)
        return table.row(index) if table else None

    def find(self, table_key, name):
        table = self.table(table_key)
        return table.find(name) if table else None

    def count(self, tid):
        """Number of instances in a table (drives the avatar bit lists)."""
        table = self.table(tid)
        if table is not None:
            return len(table.rows)
        return BIT_LIST_ROWS.get(tid, 0)

    def gid(self, tid, name):
        """Global id of ``name`` inside table ``tid`` (None when unknown)."""
        row = self.find(tid, name)
        return row.global_id if row is not None else None

    def resolve(self, global_id):
        """``global_id`` -> ``(table_id, instance_index, Row|None)``."""
        try:
            gid = int(global_id)
        except (TypeError, ValueError):
            return None, None, None
        tid, index = divmod(gid, 100000)
        if tid not in TABLES:
            return None, index, None
        return tid, index, self.row(tid, index)

    def row_for(self, global_id):
        return self.resolve(global_id)[2]

    # -- item lookups ------------------------------------------------------ #
    def _item_index(self):
        if self._items is not None:
            return self._items
        with self._lock:
            if self._items is not None:
                return self._items
            index = {}
            for tid in ITEM_TABLES:
                table = self.table(tid)
                if table is None:
                    continue
                for row in table.rows:
                    if row.name:
                        index.setdefault(row.name.lower(), row)
            self._items = index
            return index

    def item(self, name):
        """Find an item (crop / good / tool / material) by its CSV name."""
        if not name:
            return None
        return self._item_index().get(str(name).strip().lower())

    def item_id(self, name):
        row = self.item(name)
        return row.global_id if row is not None else None

    def goods_for(self, building):
        """All goods produced by a processing building (by CSV name)."""
        out = []
        if not building:
            return out
        building = str(building).strip().lower()
        for tid in GOODS_TABLES:
            table = self.table(tid)
            if table is None:
                continue
            for row in table.rows:
                if row.s("ProcessingBuilding").strip().lower() == building:
                    out.append(row)
        return out

    # -- experience / levels ---------------------------------------------- #
    @property
    def max_level(self):
        table = self.table(EXP_TABLE)
        return len(table.rows) if table else 0

    def level_row(self, level):
        try:
            level = int(level)
        except (TypeError, ValueError):
            return None
        if level < 1:
            return None
        return self.row(EXP_TABLE, level - 1)

    def exp_to_next(self, level):
        """Experience required to go from ``level`` to ``level + 1``."""
        row = self.level_row(level)
        if row is None:
            return 0
        return row.i("ExpToNextLevel", 0)

    def level_rewards(self, level):
        """``[(good_name, amount), ...]`` granted when reaching ``level``."""
        row = self.level_row(level)
        if row is None:
            return []
        out = []
        for source in [row.values] + row.subs:
            good = source.get("GoodReward")
            if not good:
                continue
            try:
                amount = int(str(source.get("GoodAmount") or 0).strip() or 0)
            except (TypeError, ValueError):
                amount = 0
            if amount > 0:
                out.append((good, amount))
        return out

    # -- misc -------------------------------------------------------------- #
    # -- game_config.csv -------------------------------------------------- #
    def named_table(self, name):
        """Load a CSV that has no entry in the id map (e.g. game_config)."""
        with self._lock:
            table = self._named.get(name)
            if table is None:
                path = self.data_dir / (name + ".csv")
                if not path.exists():
                    return None
                table = _load_table(path, 0, name)
                self._named[name] = table
            return table

    def config(self, name):
        """Row of ``game_config.csv`` by its ``Name``."""
        table = self.named_table("game_config")
        return table.find(name) if table else None

    def config_int(self, name, default=0):
        row = self.config(name)
        if row is None:
            return default
        return row.i("IntValue", default)

    def config_bool(self, name, default=False):
        row = self.config(name)
        if row is None:
            return default
        value = row.get("BooleanValue")
        if value is None or value == "":
            value = row.get("IntValue")
        if value is None or value == "":
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("true", "1", "yes", "y")

    def config_str(self, name, default=""):
        row = self.config(name)
        if row is None:
            return default
        return row.s("StringValue", default)

    def feature(self, name):
        row = self.find(FEATURE_TABLE, name)
        return row

    def feature_enabled(self, name):
        row = self.feature(name)
        if row is None:
            return False
        if not row.values.get("Enabled"):
            return False
        return row.b("Enabled", True)

    def achievement(self, global_id):
        return self.row_for(global_id)

    def shop_price(self, row, count=0):
        """Price of ``row`` as ``(currency, amount)``.

        Mirrors the client: ``ShopItem::getPrice`` charges diamonds when the
        row has a ``DiamondPrice`` (>= 1), otherwise coins, and
        ``LogicObjectData::getShopPrice`` scales the base price with
        ``PriceIncrease`` every ``DoPriceIncreaseEveryNObject`` copies.
        """
        if row is None:
            return "cash", 0
        diamond = row.i("DiamondPrice", 0)
        base = diamond if diamond >= 1 else row.i("Price", 0)
        if base < 1:
            return ("diamond" if diamond >= 1 else "cash"), 0
        every = row.i("DoPriceIncreaseEveryNObject", 0)
        increase = row.i("PriceIncrease", 0)
        currency = "diamond" if diamond >= 1 else "cash"
        if every >= 1 and increase and count >= every:
            base += (count // every) * increase
        return currency, base


def game_data():
    """Process wide :class:`GameData` singleton."""
    return GameData.instance()
