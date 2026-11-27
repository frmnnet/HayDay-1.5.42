"""Barn (warehouse) and silo storage rules.

The client classifies resources through
``LogicDataTables::resourceGoesToWarehouse`` and ``resourceGoesToSilo``.
Capacity comes from the placed warehouse/silo object's rank and the matching
continuation row in ``warehouses.csv`` / ``silos.csv``.
"""
from Logic.GameData import GameData, TABLE_IDS

WAREHOUSE_TABLE = TABLE_IDS["warehouses"]
SILO_TABLE = TABLE_IDS["silos"]
WAREHOUSE_OBJECT_ID = WAREHOUSE_TABLE * 100000
SILO_OBJECT_ID = SILO_TABLE * 100000
SILO_RANK_ITEM = GameData.instance().gid(19, "SiloRank")
WAREHOUSE_RANK_ITEM = GameData.instance().gid(19, "WarehouseRank")

SILO_RESOURCE_TABLES = {
    TABLE_IDS["fields"],
    TABLE_IDS["animal_feed"],
}

# LogicDataTables exposes 21 warehouse resource tables.  These are all items
# except crops/feed (silo), decorations/fences (placed inventory) and pets.
WAREHOUSE_RESOURCE_TABLES = {
    TABLE_IDS["animal_goods"],
    TABLE_IDS["tools"],
    *range(TABLE_IDS["dairy_goods"], TABLE_IDS["barbecue_grill_goods"] + 1),
    TABLE_IDS["collection_tools"],
    TABLE_IDS["juice_press_goods"],
    TABLE_IDS["fruits"],
    TABLE_IDS["mine_goods"],
    TABLE_IDS["smelter_goods"],
    TABLE_IDS["jam_maker_goods"],
    TABLE_IDS["ice_cream_maker_goods"],
    TABLE_IDS["jeweler_goods"],
    TABLE_IDS["vouchers"],
    TABLE_IDS["cafe_goods"],
    TABLE_IDS["candy_machine_goods"],
}


def resource_table(item_id):
    try:
        return int(item_id) // 100000
    except (TypeError, ValueError):
        return None


def storage_kind(item_id):
    tid = resource_table(item_id)
    if tid in SILO_RESOURCE_TABLES:
        return "silo"
    if tid in WAREHOUSE_RESOURCE_TABLES:
        return "warehouse"
    return None


def count(data, kind):
    tables = SILO_RESOURCE_TABLES if kind == "silo" else WAREHOUSE_RESOURCE_TABLES
    total = 0
    inventory = data.get("Inventory", {})
    if not isinstance(inventory, dict):
        return 0
    for raw_id, raw_count in inventory.items():
        if resource_table(raw_id) not in tables:
            continue
        try:
            total += max(0, int(raw_count))
        except (TypeError, ValueError):
            continue
    return total


def _object(data, object_id):
    for entry in data.get("Objects", []):
        if not isinstance(entry, dict):
            continue
        try:
            if int(entry.get("ID")) == int(object_id):
                return entry
        except (TypeError, ValueError):
            continue
    return None


def rank(data, kind):
    object_id = SILO_OBJECT_ID if kind == "silo" else WAREHOUSE_OBJECT_ID
    entry = _object(data, object_id)
    return max(1, int(entry.get("Rank", 1) or 1)) if entry else 1


def sync_rank_resources(data):
    """Mirror building ranks into ``SiloRank``/``WarehouseRank`` resources."""
    inventory = data.setdefault("Inventory", {})
    if not isinstance(inventory, dict):
        inventory = {}
        data["Inventory"] = inventory
    inventory[str(SILO_RANK_ITEM)] = rank(data, "silo")
    inventory[str(WAREHOUSE_RANK_ITEM)] = rank(data, "warehouse")


def capacity(data, kind):
    if kind == "silo":
        object_id, table_id = SILO_OBJECT_ID, SILO_TABLE
    else:
        object_id, table_id = WAREHOUSE_OBJECT_ID, WAREHOUSE_TABLE
    entry = _object(data, object_id)
    building_rank = rank(data, kind)
    row = GameData.instance().row(table_id, 0)
    if row is None:
        return 0
    sources = [row.values] + list(row.subs)
    source = sources[min(building_rank - 1, len(sources) - 1)]
    try:
        return max(0, int(source.get("Capacity") or row.i("Capacity", 0)))
    except (TypeError, ValueError):
        return 0


def available(data, item_id):
    kind = storage_kind(item_id)
    if kind is None:
        return None
    return max(0, capacity(data, kind) - count(data, kind))


def can_store(data, item_id, amount=1):
    free = available(data, item_id)
    return free is None or free >= int(amount or 0)


def can_store_many(data, items):
    """Whether one batch fits without exceeding either shared store."""
    required = {"warehouse": 0, "silo": 0}
    for item_id, amount in items:
        kind = storage_kind(item_id)
        if kind is not None:
            required[kind] += max(0, int(amount or 0))
    return all(
        not needed or needed <= capacity(data, kind) - count(data, kind)
        for kind, needed in required.items()
    )


def store(data, inventory, item_id, amount=1):
    """Store as much of ``amount`` as current barn/silo capacity permits."""
    amount = int(amount or 0)
    if amount <= 0:
        return 0
    free = available(data, item_id)
    accepted = amount if free is None else min(amount, free)
    if accepted > 0:
        inventory.give(item_id, accepted)
    return accepted


def snapshot(data):
    return {
        "warehouse": {
            "used": count(data, "warehouse"),
            "capacity": capacity(data, "warehouse"),
        },
        "silo": {
            "used": count(data, "silo"),
            "capacity": capacity(data, "silo"),
        },
    }
