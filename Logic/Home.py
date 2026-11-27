import copy
import json
from pathlib import Path

from Utils.Database import atomic_write_text
from Utils.Logging import logger
from Logic.GameData import TABLE_IDS

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_PATH = BASE_DIR / "JSON" / "home_state.json"
DEFAULT_HOME = BASE_DIR / "JSON" / "home.json"

# Keys that represent runtime progress (layered over the layout file when an
# account has no database blob yet, and always present in the blob itself).
# Tile dimensions still come from the configured HomeFile so manual layout
# edits affect new accounts; per-player objects and timers come from the save.
PROGRESS_KEYS = (
    "Objects",
    "TimeLists", "CreatedAnimalProducts", "MineProducts", "SmelterProducts",
    "Sounds", "SpecialObjects",
    "Fields", "Productions", "Inventory", "Avatar", "Expansion",
    "TutorialCompleted", "TutorialStarted", "TutorialNext",
    "TutorialsCompleted",
    "Animals", "FedAnimals", "Orders", "TruckEvents", "CarReward",
    "PeopleOrders", "Boats",
    "Boy", "Pets", "_PetFeedTimers", "BuildingUpgrades",
    "FruitTrees", "Forests",
    "MysteryBoxes", "RoadsideStand", "MovieTickets", "SpinWheel",
    "ClientEvents", "AIRoadsideShopOffers",
    "AchievementsClaimed", "_AchievementsClaimed",
    "AchievementProgress", "AchievementEvents",
    "_AchievementProgress", "_AchievementEvents",
    "_AchievementsInitialized", "RoadsideStandCount",
    "_RoadsideShopInitialized", "_RoadsideShopLastTimerTick",
    "_NewspaperAds", "_NewspaperRefreshAt", "_NewspaperSyntheticSequence",
)

# roadside_shop.csv, table 35 instance 0.  Stand N is ROADSIDE_SHOP_ID + N.
ROADSIDE_SHOP_ID = TABLE_IDS["roadside_shop"] * 100000

# Object ids from older builds that must be upgraded, not dropped.
LEGACY_OBJECT_IDS = {350000: ROADSIDE_SHOP_ID}


def _legacy_id(entry):
    """Old object id to repair in place, or ``None``.

    ``LogicBuyMarketStandCommand`` used to write the roadside shop id without
    its trailing zero: ``350000`` decodes to class 3 / instance 50000 (there
    is no such row, so the client aborts with "Unable to load object 350000
    class:3 instance:50000"), while ``roadside_shop.csv`` row 0 really is
    ``35 * 100000 + 0 = 3500000``.  Saves made with the typo are upgraded
    instead of silently losing the stand the player paid for.
    """
    if not isinstance(entry, dict):
        return None
    try:
        oid = int(entry.get("ID"))
    except (TypeError, ValueError):
        return None
    return LEGACY_OBJECT_IDS.get(oid)


def _valid_object(entry):
    """Objects must carry a global data id the client can instantiate.

    ``LogicGameObjectManager::loadObjectsFromJSON`` splits the id into
    ``class = id / 100000`` and ``instance = id % 100000`` and calls
    ``Debugger::error`` when that data row does not exist, which aborts the
    game while loading home.  That is how ``-1`` / ``4294967295`` ids
    ("Unable to load object -1 class:0 instance:-1") and the roadside shop
    id that was missing a zero ("Unable to load object 350000 class:3
    instance:50000") took the client down.

    The lookup is mirrored here so a stale or hand edited save can never
    crash the client.
    """
    if not isinstance(entry, dict):
        return False
    try:
        oid = int(entry.get("ID"))
    except (TypeError, ValueError):
        return False
    if not 1 <= oid <= 10000000:
        return False
    from Logic.GameData import GameData, TABLES
    data = GameData.instance()
    tid, instance = divmod(oid, 100000)
    if tid not in TABLES:
        logger.warning("[HOME] dropping object {}: unknown data table {}".format(
            oid, tid))
        return False
    table = data.table(tid)
    # Fail open when a decoded table is unavailable: dropping every object
    # would wipe the farm, while the client runs this check itself anyway.
    if table is None:
        return True
    if instance >= len(table.rows):
        logger.warning("[HOME] dropping object {}: class {} instance {} "
                       "does not exist".format(oid, tid, instance))
        return False
    return True


def _stringify_keys(obj, include_internal=False):
    """Recursively convert dict keys to strings for unambiguous JSON.

    The client's LogicJSONObject::put() throws on duplicate keys.  Python
    emits the same JSON key twice when a dict holds both ``12`` and ``"12"``
    (which happened with inventory items loaded from JSON and then added by
    id), so normalize everything before serializing.
    """
    if isinstance(obj, dict):
        return {
            str(k): _stringify_keys(v, include_internal)
            for k, v in obj.items()
            if include_internal or not str(k).startswith("_")
        }
    if isinstance(obj, (list, tuple)):
        return [_stringify_keys(v, include_internal) for v in obj]
    return obj


def config_home_file():
    """The farm layout file configured in config.json (HomeFile)."""
    try:
        conf = json.loads((BASE_DIR / "config.json").read_text(encoding="utf-8"))
        value = conf.get("HomeFile")
    except Exception:
        value = None
    path = Path(value) if value else DEFAULT_HOME
    if not path.is_absolute():
        path = BASE_DIR / path
    return path


class Home:
    """Mutable representation of a player's farm."""

    # Default farm keys, matching the schema the game client parses
    # (see LogicGameMode::load in the game binary).
    DEFAULT_KEYS = {
        "TileMapWidth": 48,
        "TileMapHeight": 32,
        "Objects": [],
        "Fields": {},
        "Productions": {},
        "Inventory": {},
        "Avatar": {"name": "", "level": 1, "icon": 0},
        "Expansion": 0,
        "Sounds": {},
        "SpecialObjects": [],
        "TimeLists": [],
        "CreatedAnimalProducts": [],
        "MineProducts": [],
        "SmelterProducts": [],
        "TutorialCompleted": False,
        "TutorialStarted": 0,
        "TutorialsCompleted": [],
    }

    def __init__(self, path=None):
        self.path = Path(path) if path else STATE_PATH
        self.data = {}
        self.load()
        self.apply_defaults(reset_runtime=True)
        # OOP views over the persisted dicts (shared, so mutations are saved)
        from Logic.Inventory import Inventory
        from Logic.Fields import FieldManager
        from Logic.Productions import ProductionManager
        self.inventory = Inventory(self.data.setdefault("Inventory", {}))
        from Logic.HomeFields import sync_manager
        self.fields = sync_manager(
            self.data, FieldManager(self.data.setdefault("Fields", {})))
        self.productions = ProductionManager(
            self.data.setdefault("Productions", {}), home_data=self.data
        ).sync_from_objects()

    def apply_defaults(self, reset_runtime=False):
        """Fill in missing farm keys with the game's default schema.

        Defaults are deep-copied: sharing ``DEFAULT_KEYS``' list/dict objects
        between ``Home`` instances would let one player's farm mutate
        another's (all freshly created farms literally pointed at the same
        ``Avatar`` dict).

        ``reset_runtime`` is true only when loading a home for a new client
        session.  Persistence serialization must preserve ids allocated during
        the current session, including removals that create ordinal holes.
        """
        for k, v in self.DEFAULT_KEYS.items():
            if k not in self.data:
                self.data[k] = copy.deepcopy(v)
        from Logic.GameData import GameData
        data = GameData.instance()
        # Older builds mirrored transforms into keys the client never reads.
        # The normalized home_objects table and Objects array are authoritative.
        self.data.pop("ObjectPositions", None)
        self.data.pop("ObjectOrientations", None)
        from Logic.Tutorials import normalize_completed
        self.data["TutorialsCompleted"] = normalize_completed(self, data)
        # Repair ids written by older builds and drop whatever the client
        # still could not load (both crash LogicGameObjectManager::
        # loadObjectsFromJSON, see _valid_object).
        objects = self.data.get("Objects")
        if isinstance(objects, list):
            repaired = []
            for entry in objects:
                legacy = _legacy_id(entry)
                if legacy is not None:
                    entry["ID"] = legacy
                if _valid_object(entry):
                    repaired.append(entry)
            self.data["Objects"] = repaired
        if reset_runtime:
            from Logic import HomeObjects
            HomeObjects.reset_runtime_ids(self.data)
        from Logic.HomeAnimals import sync_from_metadata, sync_habitats
        from Logic.HomeBuildings import sync_timers as sync_building_timers
        from Logic.HomeBuildings import normalize_upgrades
        from Logic import Forests, FruitTrees, Pets, Storage
        from Logic.TruckOrders import normalize as normalize_truck_orders
        sync_building_timers(self.data)
        normalize_upgrades(self.data)
        Storage.sync_rank_resources(self.data)
        sync_habitats(self.data)
        sync_from_metadata(self.data)
        normalize_truck_orders(self.data)
        # Rebuild OOP views so they point at the (possibly new) dicts.
        from Logic.Inventory import Inventory
        from Logic.Fields import FieldManager
        from Logic.Productions import ProductionManager
        self.inventory = Inventory(self.data.setdefault("Inventory", {}))
        self.inventory.prune_unknown(data)
        from Logic.HomeFields import sync_manager
        self.fields = sync_manager(
            self.data, FieldManager(self.data.setdefault("Fields", {})))
        self.productions = ProductionManager(
            self.data.setdefault("Productions", {}), home_data=self.data
        ).sync_from_objects()
        Pets.sync(self.data)
        FruitTrees.sync(self.data)
        Forests.sync(self.data)

    def load(self):
        # Base layout always comes from the configured HomeFile (home.json).
        # Runtime progress is layered on top from home_state.json.
        self.data = {}
        base_path = config_home_file()
        try:
            if base_path.exists():
                self.data = json.loads(base_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.data = {}
        try:
            if self.path.exists():
                saved = json.loads(self.path.read_text(encoding="utf-8"))
                for key in PROGRESS_KEYS:
                    if key in saved:
                        self.data[key] = saved[key]
        except (OSError, ValueError):
            pass
        if not self.data:
            self.data = {"TileMapWidth": 48, "TileMapHeight": 32, "Objects": []}

    def save(self):
        """Write the JSON export of the farm.

        The database (``home_states``) is the source of truth — see
        :meth:`Logic.GameState.GameState.flush` — this file is a readable
        copy for humans and for a fresh install with an empty database.
        Writes are atomic so a crash can never leave a half-written save.
        """
        self.apply_defaults()
        atomic_write_text(
            self.path, json.dumps(_stringify_keys(self.data)))

    def to_json(self, include_internal=False):
        self.apply_defaults()
        return json.dumps(_stringify_keys(
            self.data, include_internal=include_internal))
