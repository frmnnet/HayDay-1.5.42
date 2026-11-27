"""Achievement progress, claim state and client-facing inventory resources.

The 1.5.42 client stores one table-59 resource per achievement:

* ``0`` - unavailable
* ``1`` - completed and claimable
* ``2`` - claimed

``LogicClaimAchievementCommand::canExecute`` requires exactly ``1``.
``LogicClaimAchievementCommand::execute`` adds the achievement resource,
which transitions it from ``1`` to ``2``.  Claim state therefore must be
included in the avatar's resource list; a private home-JSON key is never
observed by the client.
"""
import time

from Logic.GameTime import seconds_to_ticks
from Logic.GameData import TABLE_IDS


TABLE_ID = TABLE_IDS["achievements"]
HOUSE_TABLE = TABLE_IDS["houses"]
HOUSE_ID = HOUSE_TABLE * 100000
CLAIMED_KEY = "_AchievementsClaimed"
LEGACY_CLAIMED_KEY = "AchievementsClaimed"
PROGRESS_KEY = "_AchievementProgress"
EVENTS_KEY = "_AchievementEvents"
INITIALIZED_KEY = "_AchievementsInitialized"

STATE_LOCKED = 0
STATE_CLAIMABLE = 1
STATE_CLAIMED = 2

# Exact enum values from LogicSpecialEventData::parseAction.
ACTION_IDS = {
    "DecosWorth": 1,
    "CarOrders": 2,
    "RoadsideShopSalesWorth": 3,
    "PeopleOrders": 4,
    "TurboHarvest": 5,
    "TurboCollectAnimalGoods": 6,
    "TurboCarOrders": 7,
    "BuildBuildings": 8,
    "PlaceNewspaperAd": 9,
    "CollectAnimalProduct": 10,
    "EarnCoinsFromBoat": 13,
    "CompleteConsecutiveBoatOrders": 14,
    "PickFruits": 15,
    "PickBerries": 16,
    "ReviveFruitTrees": 17,
    "CollectMineGood": 18,
    "CollectFromSmelter": 19,
    "BuyPet": 20,
    "FeedPet": 21,
    "SocialBoat": 22,
    "SpinTheWheel": 23,
    "Expansion": 24,
}

TIMED_ACTIONS = {"TurboHarvest", "TurboCollectAnimalGoods", "TurboCarOrders"}

# Actions whose progress the client reads from table-19 money counters.
MONEY_COUNTERS = {
    "DecosWorth": "MoneySpentOnDecorations",
    "CarOrders": "CarOrderCompleteCount",
    "RoadsideShopSalesWorth": "RoadsideShopSoldGoodsValue",
    "PeopleOrders": "PeopleOrderCompleteCount",
    "BuildBuildings": "BuildingsConstructedCount",
    "PlaceNewspaperAd": "AdsPlacedToNewspaperCount",
    "BoatOrders": "BoatOrderCompleteCount",
    "BoatCrates": "BoatCrateCompleteCount",
    "EarnCoinsFromBoat": "CoinsEarnedFromBoatOrders",
    "CompleteConsecutiveBoatOrders": "ConsecutiveBoatOrdersCompleted",
    "PickFruits": "FruitsPicked",
    "PickBerries": "BerriesPicked",
    "ReviveFruitTrees": "FruitTreesRevived",
    "FeedPet": "PetFeedCount",
    "SocialBoat": "SocialBoatCount",
}

# One-time migration for accounts whose progress used command counters.
LEGACY_STATS = {
    "CarOrders": ("truck_orders_completed", "LogicCompleteOrderCommand"),
    "PeopleOrders": ("LogicCompletePeopleOrderCommand",),
    "TurboHarvest": ("LogicHarvestFieldCommand",),
    "TurboCarOrders": ("truck_orders_completed",),
    "TurboCollectAnimalGoods": ("LogicCollectAnimalCommand",),
    "BuildBuildings": (
        "BuildingsConstructedCount",
        "LogicInstantCompleteBuildingCommand",
    ),
    "BoatOrders": ("LogicCompleteBoatOrderCommand",),
    "BoatCrates": ("LogicCompleteBoatCrateCommand",),
    "PickFruits": ("FruitsPicked", "LogicCollectFruitTreeCommand"),
    "PickBerries": ("BerriesPicked", "LogicCollectFruitCommand"),
    "ReviveFruitTrees": ("FruitTreesRevived", "LogicReviveFruitTreeCommand"),
    "CollectMineGood": ("LogicUseMineCommand",),
    "CollectFromSmelter": ("LogicCollectProductionsCommand",),
    "FeedPet": ("PetFeedCount", "LogicFillPetBowlCommand"),
    "SocialBoat": ("SocialBoatCount", "LogicAskHelpForBoatOrderCommand"),
    "SpinTheWheel": ("SpinTheWheelCount", "LogicSpinWheelCommand"),
}


def _table():
    from Logic.GameData import GameData
    return GameData.instance().table(TABLE_ID)


def _achievement_rows():
    table = _table()
    return list(table.rows) if table is not None else []


def _claimed(data):
    values = data.setdefault(CLAIMED_KEY, [])
    if not isinstance(values, list):
        values = []
        data[CLAIMED_KEY] = values
    normalized = []
    seen = set()
    for value in values:
        try:
            value = int(value)
        except (TypeError, ValueError):
            continue
        if value not in seen:
            normalized.append(value)
            seen.add(value)
    if normalized != values:
        values[:] = normalized
    return values


def is_claimed(data, achievement_id):
    return int(achievement_id) in {
        int(value) for value in _claimed(data)
    }


def mark_claimed(data, achievement_id):
    values = _claimed(data)
    achievement_id = int(achievement_id)
    if achievement_id not in values:
        values.append(achievement_id)
    return achievement_id


def _progress(data):
    values = data.setdefault(PROGRESS_KEY, {})
    if not isinstance(values, dict):
        values = {}
        data[PROGRESS_KEY] = values
    return values


def _events(data):
    values = data.setdefault(EVENTS_KEY, {})
    if not isinstance(values, dict):
        values = {}
        data[EVENTS_KEY] = values
    return values


def _action_data(row):
    if row is None:
        return ""
    value = row.s("ActionData")
    return str(value or "").strip()


def _metric(action, action_data=""):
    action_data = str(action_data or "").strip()
    return "{}:{}".format(action, action_data) if action_data else action


def _legacy_value(account, action):
    stats = getattr(account, "stats", {}) if account is not None else {}
    for key in LEGACY_STATS.get(action, ()):
        try:
            value = int(stats.get(key, 0) or 0)
        except (TypeError, ValueError):
            continue
        if value:
            return value
    return 0


def normalize(state):
    """Migrate persisted progress and synchronize house rank/time lists."""
    data = state.home.data
    legacy_claimed = data.pop(LEGACY_CLAIMED_KEY, None)
    if isinstance(legacy_claimed, list):
        current = data.get(CLAIMED_KEY)
        if not isinstance(current, list):
            data[CLAIMED_KEY] = legacy_claimed
        else:
            current[:] = list(current) + list(legacy_claimed)
    _claimed(data)
    legacy_progress = data.pop("AchievementProgress", None)
    if isinstance(legacy_progress, dict):
        current = data.get(PROGRESS_KEY)
        if not isinstance(current, dict):
            data[PROGRESS_KEY] = legacy_progress
        else:
            for key, value in legacy_progress.items():
                current.setdefault(key, value)
    legacy_events = data.pop("AchievementEvents", None)
    if isinstance(legacy_events, dict):
        current = data.get(EVENTS_KEY)
        if not isinstance(current, dict):
            data[EVENTS_KEY] = legacy_events
        else:
            for key, value in legacy_events.items():
                current.setdefault(key, value)
    progress = _progress(data)
    if not data.get(INITIALIZED_KEY):
        for action in ACTION_IDS:
            key = _metric(action)
            if not progress.get(key):
                value = _legacy_value(state.account, action)
                if value:
                    progress[key] = value
        expansions = data.get("Expansions", [])
        if isinstance(expansions, list):
            progress[_metric("Expansion")] = max(
                int(progress.get(_metric("Expansion"), 0) or 0),
                len(expansions),
            )
        data[INITIALIZED_KEY] = True
    sync_time_lists(data)
    update_house_rank(state)


def _timed_window_seconds(action):
    windows = []
    for row in _achievement_rows():
        if row.s("Action") != action:
            continue
        minutes = row.i("MinutesLimit", 0)
        if minutes > 0:
            windows.append(minutes * 60)
    return max(windows) if windows else 0


def _event_count(data, action, now=None):
    now = int(time.time()) if now is None else int(now)
    seconds = _timed_window_seconds(action)
    if seconds <= 0:
        return 0
    cutoff = now - seconds
    values = _events(data).get(_metric(action), [])
    if not isinstance(values, list):
        return 0
    kept = []
    for value in values:
        try:
            value = int(value)
        except (TypeError, ValueError):
            continue
        if value >= cutoff:
            kept.append(value)
    values[:] = sorted(kept)
    return len(values)


def progress_for(state, action, action_data="", now=None):
    data = state.home.data
    if action in TIMED_ACTIONS:
        return _event_count(data, action, now)
    progress = _progress(data)
    data_key = _metric(action, action_data)
    if data_key in progress:
        try:
            return max(0, int(progress[data_key]))
        except (TypeError, ValueError):
            pass
    try:
        return max(0, int(progress.get(_metric(action), 0) or 0))
    except (TypeError, ValueError):
        return 0


def record(state, action, amount=1, action_data="", now=None):
    """Record one gameplay event and refresh client-visible progress."""
    amount = int(amount or 0)
    if amount <= 0:
        return progress_for(state, action, action_data, now)
    now = int(time.time()) if now is None else int(now)
    data = state.home.data
    progress = _progress(data)
    key = _metric(action, action_data)
    try:
        progress[key] = max(0, int(progress.get(key, 0) or 0) + amount)
    except (TypeError, ValueError):
        progress[key] = amount

    if action in TIMED_ACTIONS:
        event_key = _metric(action)
        events = _events(data)
        values = events.get(event_key, [])
        if not isinstance(values, list):
            values = []
        values.extend([now] * amount)
        max_count = max(
            [row.i("ActionCount", 0) for row in _achievement_rows()
             if row.s("Action") == action] or [1])
        events[event_key] = sorted(
            int(value) for value in values
            if str(value).lstrip("-").isdigit()
        )[-max_count:]
        sync_time_lists(data, now)
    state.save()
    return progress_for(state, action, action_data, now)


def set_progress(state, action, value, action_data=""):
    progress = _progress(state.home.data)
    progress[_metric(action, action_data)] = max(0, int(value or 0))
    state.save()


def _row_status(data, row, now=None):
    achievement_id = row.global_id
    if is_claimed(data, achievement_id):
        return STATE_CLAIMED
    return STATE_CLAIMABLE \
        if progress_for(
            _StateProxy(data), row.s("Action"), _action_data(row), now
        ) >= max(1, row.i("ActionCount", 1)) else STATE_LOCKED


class _StateProxy:
    """Small adapter for progress lookups during avatar serialization."""
    def __init__(self, data):
        self.home = type("_HomeProxy", (), {"data": data})()


def resource_pairs(state):
    """Non-zero table-59 resources exactly as LogicInventory::encode sends."""
    data = state.home.data
    now = int(time.time())
    pairs = []
    for row in _achievement_rows():
        status = _row_status(data, row, now)
        if status:
            pairs.append((row.global_id, status))
    return pairs


def can_claim(state, achievement_id):
    row = _row_by_id(achievement_id)
    if row is None or row.b("Deprecated", False):
        return False
    return _row_status(state.home.data, row, int(time.time())) == STATE_CLAIMABLE


def _row_by_id(achievement_id):
    try:
        achievement_id = int(achievement_id)
    except (TypeError, ValueError):
        return None
    for row in _achievement_rows():
        if row.global_id == achievement_id:
            return row
    return None


def money_resource_pairs(state):
    """Counters read by LogicGameMode::getSpecialEventDoneCount."""
    data = state.home.data
    pairs = []
    for action, counter_name in MONEY_COUNTERS.items():
        value = progress_for(state, action)
        if value <= 0:
            continue
        from Logic.GameData import GameData
        row = GameData.instance().find(19, counter_name)
        if row is not None:
            pairs.append((row.global_id, value))
    return pairs


def sync_time_lists(data, now=None):
    now = int(time.time()) if now is None else int(now)
    lists = data.setdefault("TimeLists", [])
    by_action = {
        int(item.get("Action", -1)): item
        for item in lists
        if isinstance(item, dict)
    }
    for action in TIMED_ACTIONS:
        action_id = ACTION_IDS[action]
        item = by_action.get(action_id)
        if item is None:
            item = {"Action": action_id, "List": []}
            lists.append(item)
        window = _timed_window_seconds(action)
        cutoff = now - window if window > 0 else now
        timestamps = _events(data).get(_metric(action), [])
        if not isinstance(timestamps, list):
            timestamps = []
        valid = sorted(
            int(value) for value in timestamps
            if str(value).lstrip("-").isdigit() and int(value) >= cutoff
        )
        max_count = max(
            [row.i("ActionCount", 0) for row in _achievement_rows()
             if row.s("Action") == action] or [1])
        valid = valid[-max_count:]
        _events(data)[_metric(action)] = valid
        item["List"] = [
            seconds_to_ticks(max(0, now - value))
            for value in valid
        ]


def update_house_rank(state):
    """Mirror LogicHouseData::getDeservedRank for the house object."""
    claimed_count = len(_claimed(state.home.data))
    thresholds = []
    from Logic.GameData import GameData
    house = GameData.instance().row(HOUSE_TABLE, 0)
    if house is not None:
        for source in house.subs:
            try:
                thresholds.append(int(source.get("RequiredAchievementPoints") or 0))
            except (TypeError, ValueError):
                continue
    rank = 1
    for index, threshold in enumerate(thresholds):
        if threshold <= claimed_count:
            rank = index + 1
    for entry in state.home.data.get("Objects", []):
        if isinstance(entry, dict) and entry.get("ID") == HOUSE_ID:
            entry["Rank"] = rank
            return rank
    return rank
