"""Roadside-shop persistence in the client's own save format.

The client has one placed roadside-shop building (data type 35) whose
``AITimer`` and ``AdTimers`` arrays belong to the configured stand count.
The stands themselves are a list under ``Avatar.roadside_shop.Stands``.

Each stand is persisted as::

    {"Data": item_id, "Price": total_price, "Count": amount,
     "Advertised": bool, "BH": buyer_high, "BL": buyer_low}

``Price`` is the total sale price; ``LogicClaimRoadsideShopStandCommand``
credits exactly that value, not ``Price * Count``.
"""
import time

from Logic.GameData import GameData, TABLE_IDS
from Logic.GameTime import seconds_to_ticks, ticks_to_seconds


SHOP_TYPE = TABLE_IDS["roadside_shop"]
SHOP_ID = SHOP_TYPE * 100000
SPAWN_X = 12
SPAWN_Y = 32
UNLOCK_LEVEL = 7

STAND_COUNT_ITEM = 1900008
FRIEND_STAND_COUNT_ITEM = 1900027
ADS_PLACED_ITEM = 1900028
AD_PURCHASES_ITEM = 1900030
SOLD_VALUE_ITEM = 1900024

# Legacy server-only representation, retained only for migration.
MIRROR_KEY = "RoadsideStand"
INITIALIZED_KEY = "_RoadsideShopInitialized"
LAST_TIMER_TICK = "_RoadsideShopLastTimerTick"


def _default_stand():
    return {"Data": 0, "Price": 0, "Count": 0, "Advertised": False}


def _inventory(data):
    inventory = data.setdefault("Inventory", {})
    if not isinstance(inventory, dict):
        inventory = {}
        data["Inventory"] = inventory
    return inventory


def amount(data, item_id):
    try:
        return max(0, int(_inventory(data).get(str(item_id), 0) or 0))
    except (TypeError, ValueError):
        return 0


def add_resource(data, item_id, amount_to_add):
    amount_to_add = int(amount_to_add or 0)
    if amount_to_add <= 0:
        return 0
    inventory = _inventory(data)
    key = str(item_id)
    try:
        current = int(inventory.get(key, 0) or 0)
    except (TypeError, ValueError):
        current = 0
    inventory[key] = current + amount_to_add
    return amount_to_add


def take_resource(data, item_id, amount_to_take=1):
    amount_to_take = max(0, int(amount_to_take or 0))
    if amount_to_take == 0:
        return True
    inventory = _inventory(data)
    key = str(item_id)
    try:
        current = int(inventory.get(key, 0) or 0)
    except (TypeError, ValueError):
        current = 0
    if current < amount_to_take:
        return False
    remaining = current - amount_to_take
    if remaining:
        inventory[key] = remaining
    else:
        inventory.pop(key, None)
    return True


def _avatar(data):
    avatar = data.get("Avatar")
    if not isinstance(avatar, dict):
        avatar = {}
        data["Avatar"] = avatar
    roadside = avatar.get("roadside_shop")
    if not isinstance(roadside, dict):
        roadside = {}
        avatar["roadside_shop"] = roadside
    return roadside


def stands(data):
    roadside = _avatar(data)
    values = roadside.get("Stands")
    if not isinstance(values, list):
        values = []
        roadside["Stands"] = values
    return values


def _objects(data):
    objects = data.setdefault("Objects", [])
    if not isinstance(objects, list):
        objects = []
        data["Objects"] = objects
    return objects


def shop_building(data, create=False):
    candidates = [
        entry for entry in _objects(data)
        if isinstance(entry, dict)
        and isinstance(entry.get("ID"), int)
        and entry["ID"] // 100000 == SHOP_TYPE
    ]
    if len(candidates) > 1:
        # The client only has one placed shop.  Older server revisions added a
        # building object for every stand; retain the first real building.
        objects = _objects(data)
        for duplicate in candidates[1:]:
            try:
                objects.remove(duplicate)
            except ValueError:
                pass
        candidates = candidates[:1]
    if not candidates and create:
        building = {
            "ID": SHOP_ID,
            "X": SPAWN_X,
            "Y": SPAWN_Y,
            "_AccurateX": SPAWN_X * 512,
            "_AccurateY": SPAWN_Y * 512,
            "AITimer": [],
            "AdTimers": [],
            "FreeAdTimer": {},
        }
        _objects(data).append(building)
        candidates = [building]
    return candidates[0] if candidates else None


def _unlocked(level):
    row = GameData.instance().feature("RoadsideShop")
    required = row.i("UnlockLevel", UNLOCK_LEVEL) if row is not None else UNLOCK_LEVEL
    return int(level or 1) >= required


def is_unlocked(level):
    return _unlocked(level)


def stand_count(data):
    return amount(data, STAND_COUNT_ITEM) + amount(data, FRIEND_STAND_COUNT_ITEM)


def _seed_count(data, level):
    if not _unlocked(level) or data.get(INITIALIZED_KEY):
        return
    inventory = _inventory(data)
    key = str(STAND_COUNT_ITEM)
    try:
        current = int(inventory.get(key, 0) or 0)
    except (TypeError, ValueError):
        current = 0
    if current <= 0:
        initial = GameData.instance().config_int(
            "InitialRoadsideShopStandCount", 4)
        inventory[key] = max(0, initial)
    data[INITIALIZED_KEY] = True


def _migrate_legacy(data):
    legacy = data.get(MIRROR_KEY)
    if not isinstance(legacy, dict):
        return
    values = stands(data)
    for raw_slot, raw_entry in legacy.items():
        if not isinstance(raw_entry, dict):
            continue
        try:
            slot = int(raw_slot)
        except (TypeError, ValueError):
            continue
        if slot < 0 or slot >= len(values):
            continue
        target = values[slot]
        if target.get("Data"):
            continue
        for key in ("Data", "Count", "Price", "Advertised", "BH", "BL"):
            if key in raw_entry:
                target[key] = raw_entry[key]
    data[MIRROR_KEY] = {}


def _normalized_stand(value):
    stand = _default_stand()
    if isinstance(value, dict):
        for key in ("Data", "Count", "Price", "Advertised", "BH", "BL"):
            if key in value:
                stand[key] = value[key]
    try:
        stand["Data"] = max(0, int(stand.get("Data") or 0))
        stand["Count"] = max(0, int(stand.get("Count") or 0))
        stand["Price"] = max(0, int(stand.get("Price") or 0))
        stand["Advertised"] = bool(stand.get("Advertised"))
        stand["BH"] = max(0, int(stand.get("BH") or 0))
        stand["BL"] = max(0, int(stand.get("BL") or 0))
    except (TypeError, ValueError):
        return _default_stand()
    if not stand["Data"] or not stand["Count"]:
        return _default_stand()
    if not stand["BH"]:
        stand.pop("BH", None)
    if not stand["BL"]:
        stand.pop("BL", None)
    if not stand["Advertised"]:
        stand.pop("Advertised", None)
    return stand


def _sync_lists(building, count):
    if building is None:
        return
    ai = building.setdefault("AITimer", [])
    ads = building.setdefault("AdTimers", [])
    if not isinstance(ai, list):
        ai = []
        building["AITimer"] = ai
    if not isinstance(ads, list):
        ads = []
        building["AdTimers"] = ads
    del ai[count:]
    del ads[count:]
    while len(ai) < count:
        ai.append(0)
    while len(ads) < count:
        ads.append(0)


def _decay_timer_object(timer, elapsed_seconds):
    if not isinstance(timer, dict):
        return {}
    ticks = max(0, int(timer.get("TicksLeft", 0) or 0))
    ticks = max(0, ticks - seconds_to_ticks(elapsed_seconds))
    if ticks <= 0:
        return {}
    result = dict(timer)
    result["TicksLeft"] = ticks
    return result


def _decay_timer_list(values, elapsed_seconds):
    if not isinstance(values, list):
        return []
    delta = seconds_to_ticks(elapsed_seconds)
    result = []
    for value in values:
        try:
            current = int(value or 0)
        except (TypeError, ValueError):
            current = 0
        result.append(max(0, current - delta) if current > 0 else current)
    return result


def ensure(data, level=1, now=None):
    """Create or repair the complete client-side roadside shop state."""
    now = int(time.time()) if now is None else int(now)
    level = int(level or 1)
    _seed_count(data, level)
    building = shop_building(data, create=_unlocked(level))
    _migrate_legacy(data)

    count = stand_count(data)
    values = stands(data)
    while len(values) < count:
        values.append(_default_stand())
    del values[count:]
    for index, value in enumerate(values):
        normalized = _normalized_stand(value)
        if isinstance(value, dict):
            value.clear()
            value.update(normalized)
        else:
            values[index] = normalized
    _sync_lists(building, count)

    if building is not None:
        previous = int(building.get(LAST_TIMER_TICK, now) or now)
        elapsed = max(0, now - previous)
        if elapsed:
            building["AITimer"] = _decay_timer_list(
                building.get("AITimer"), elapsed)
            building["AdTimers"] = _decay_timer_list(
                building.get("AdTimers"), elapsed)
            building["FreeAdTimer"] = _decay_timer_object(
                building.get("FreeAdTimer"), elapsed)
            for slot, ticks in enumerate(building["AdTimers"]):
                if ticks <= 0 and slot < len(values):
                    values[slot].pop("Advertised", None)
        building[LAST_TIMER_TICK] = now
    data.pop("RoadsideStandCount", None)
    return {
        "count": count,
        "building": building,
        "stands": values,
    }


def stand_at(data, slot, level=1, now=None):
    slot = int(slot)
    ensure(data, level, now)
    values = stands(data)
    if slot < 0 or slot >= len(values):
        return None
    return values[slot]


def is_clear(stand):
    return not isinstance(stand, dict) or not int(stand.get("Data") or 0)


def is_on_sale(stand):
    return bool(stand and int(stand.get("Data") or 0))


def is_claimed(stand):
    return bool(stand and (int(stand.get("BH") or 0)
                           or int(stand.get("BL") or 0)))


def put(data, slot, item, count, price, advertised=False,
        buyer_high=0, buyer_low=0, level=1, now=None):
    """Stock one stand. ``price`` is the total price shown in the client."""
    stand = stand_at(data, slot, level, now)
    if stand is None:
        return None
    stand.clear()
    stand.update({
        "Data": int(item),
        "Price": max(0, int(price)),
        "Count": max(1, int(count)),
    })
    if advertised:
        stand["Advertised"] = True
    if buyer_high or buyer_low:
        stand["BH"] = int(buyer_high)
        stand["BL"] = int(buyer_low)
    return stand


def set_advertised(data, slot, advertised, level=1, now=None):
    stand = stand_at(data, slot, level, now)
    if stand is None:
        return None
    if advertised:
        stand["Advertised"] = True
    else:
        stand.pop("Advertised", None)
    return stand


def set_buyer(data, slot, buyer_high, buyer_low, level=1, now=None):
    stand = stand_at(data, slot, level, now)
    if stand is None:
        return None
    stand["BH"] = int(buyer_high)
    stand["BL"] = int(buyer_low)
    stand.pop("Advertised", None)
    building = shop_building(data)
    if building is not None and slot < len(building.get("AdTimers", [])):
        building["AdTimers"][int(slot)] = 0
    return stand


def clear(data, slot, level=1, now=None):
    stand = stand_at(data, slot, level, now)
    if stand is None:
        return {}
    entry = dict(stand)
    stand.clear()
    stand.update(_default_stand())
    building = shop_building(data)
    if building is not None and slot < len(building.get("AITimer", [])):
        building["AITimer"][int(slot)] = 0
    if building is not None and slot < len(building.get("AdTimers", [])):
        building["AdTimers"][int(slot)] = 0
    return entry


def free_advertisement_available(data, level=1, now=None):
    state = ensure(data, level, now)
    building = state["building"]
    if building is None:
        return False
    timer = building.get("FreeAdTimer")
    return not timer or ticks_to_seconds(timer.get("TicksLeft", 0)) <= 0


def advertise(data, slot, level=1, now=None):
    """Place one newspaper advertisement using the client's free/paid rules."""
    now = int(time.time()) if now is None else int(now)
    state = ensure(data, level, now)
    building = state["building"]
    stand = stand_at(data, slot, level, now)
    if building is None or stand is None or not is_on_sale(stand):
        return False
    if stand.get("Advertised") or is_claimed(stand):
        return False

    used_free = free_advertisement_available(data, level, now)
    if used_free:
        cooldown = max(1, GameData.instance().config_int(
            "RoadSideShopStandAdvertisementCooldownMinutes", 30))
        building["FreeAdTimer"] = {
            "StartSeconds": cooldown * 60,
            "TicksLeft": seconds_to_ticks(cooldown * 60),
        }
    elif not take_resource(data, AD_PURCHASES_ITEM, 1):
        return False

    life = max(1, GameData.instance().config_int(
        "RoadsideShopStandAdvertisementLifeMinutes", 180))
    stand["Advertised"] = True
    _sync_lists(building, len(state["stands"]))
    building["AdTimers"][int(slot)] = seconds_to_ticks(life * 60)
    add_resource(data, ADS_PLACED_ITEM, 1)
    return True


def buy_advertisement(data, level=1, now=None):
    """Buy one advertisement token after the free cooldown has started."""
    if free_advertisement_available(data, level, now):
        return False
    if amount(data, AD_PURCHASES_ITEM) > 0:
        return False
    add_resource(data, AD_PURCHASES_ITEM, 1)
    return True


def active_ads(data, level=1, now=None):
    """Return all currently advertised, unsold stands in slot order."""
    state = ensure(data, level, now)
    result = []
    for slot, stand in enumerate(state["stands"]):
        if not stand.get("Advertised") or is_claimed(stand):
            continue
        data_id = int(stand.get("Data") or 0)
        count = int(stand.get("Count") or 0)
        price = int(stand.get("Price") or 0)
        if data_id > 0 and count > 0 and price > 0:
            result.append({
                "slot": slot,
                "Data": data_id,
                "Count": count,
                "Price": price,
            })
    return result


def can_put(data, item_id):
    """Approximate the client's LogicDataTables::canBePutToRoadsideShop."""
    row = GameData.instance().row_for(item_id)
    if row is None:
        return False
    from Logic.GameData import ITEM_TABLES
    return row.tid in ITEM_TABLES


def max_price(item_id, count):
    row = GameData.instance().row_for(item_id)
    if row is None:
        return 0
    base = max(
        row.i("OrderValue", 0),
        row.i("DumbValue", 0),
        row.i("Value", 0),
        row.i("OrderPrice", 0),
    )
    maximum_percent = max(
        100, GameData.instance().config_int(
            "RoadsideShopMaxPricePercentage", 100))
    return max(
        0, base * max(1, int(count or 1)) * maximum_percent // 100)
