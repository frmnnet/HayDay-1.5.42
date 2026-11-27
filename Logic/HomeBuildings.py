"""Construction-site state for purchased processing buildings."""
from Logic import HomeObjects
from Logic.GameData import GameData, TABLE_IDS
from Logic.GameTime import now_seconds, sync_timer

CONSTRUCTION_TYPE = TABLE_IDS["construction_buildings"]


def construction_id_for(data_id):
    """Pick the construction-site row matching the target tile dimensions."""
    game_data = GameData.instance()
    target = game_data.row_for(data_id)
    width = target.i("TileWidth", 3) if target is not None else 3
    height = target.i("TileHeight", 3) if target is not None else 3
    candidates = []
    for row in game_data.rows(TABLE_IDS["construction_buildings"]):
        if row.i("TileWidth", 0) != width or row.i("TileHeight", 0) != height:
            continue
        candidates.append(row)
    if candidates:
        generic = [row for row in candidates
                   if "construction" in row.name.lower()]
        return (generic or candidates)[0].global_id
    row = game_data.row(TABLE_IDS["construction_buildings"], 1)
    return row.global_id if row is not None else None


def place(data, data_id, accurate_x, accurate_y, total_seconds,
          mirrored=False, now=None):
    construction_id = construction_id_for(data_id)
    if construction_id is None:
        return None
    now = now_seconds() if now is None else int(now)
    entry = {
        "ID": construction_id,
        "X": int(accurate_x) >> 9,
        "Y": int(accurate_y) >> 9,
        "_AccurateX": int(accurate_x),
        "_AccurateY": int(accurate_y),
        "TargetData": int(data_id),
        "_ReadyAt": now + max(1, int(total_seconds or 0)),
        "_TotalSeconds": max(1, int(total_seconds or 0)),
        "_PendingRuntime": True,
    }
    if mirrored:
        entry["Mirrored"] = True
    _sync_entry(entry, now)
    data.setdefault("Objects", []).append(entry)
    return entry


def _sync_entry(entry, now):
    ready_at = int(entry.get("_ReadyAt") or 0)
    sync_timer(
        entry, "ConstructionTimer",
        int(entry.get("_TotalSeconds") or 0),
        ready_at, now)


def sync_timers(data, now=None):
    now = now_seconds() if now is None else int(now)
    for entry in data.get("Objects", []):
        if HomeObjects.object_type(entry) != CONSTRUCTION_TYPE:
            continue
        if entry.get("TargetData") is None:
            continue
        _sync_entry(entry, now)


def normalize_upgrades(data):
    """Repair ranks written by the old hardcoded upgrade implementation.

    That version stored ``Level: 1`` for the first successful upgrade but
    left the building at rank 1, so the client never saw a capacity increase.
    """
    records = data.get("BuildingUpgrades", {})
    if not isinstance(records, dict):
        return
    # Upgrade records used to be keyed by load-scoped runtime ids.  Move them
    # to the stable data id before repairing the old Level/Rank mismatch.
    for old_key in list(records.keys()):
        try:
            runtime_id = int(old_key)
        except (TypeError, ValueError):
            continue
        _index, entry = HomeObjects.find_by_runtime_id(data, runtime_id)
        if entry is None:
            continue
        stable_key = str(entry.get("ID"))
        if stable_key == old_key:
            continue
        record = records.pop(old_key)
        target = records.setdefault(stable_key, {})
        if isinstance(record, dict) and isinstance(target, dict):
            target.update(record)
    for entry in data.get("Objects", []):
        if not isinstance(entry, dict):
            continue
        key = str(entry.get("ID", ""))
        record = records.get(key)
        if not isinstance(record, dict) or "Level" not in record:
            continue
        try:
            level = int(record.get("Level") or 0)
            rank = int(entry.get("Rank", 1) or 1)
        except (TypeError, ValueError):
            continue
        if level == 1 and rank <= 1:
            entry["Rank"] = 2
            record["Level"] = 2


def complete(data, construction_runtime_id, now=None, force=False):
    """Convert a construction site into its target processing building."""
    _, entry = HomeObjects.find_by_runtime_id(data, construction_runtime_id)
    if entry is None or HomeObjects.object_type(entry) != CONSTRUCTION_TYPE:
        return None
    try:
        target_data = int(entry.get("TargetData"))
    except (TypeError, ValueError):
        return None
    now = now_seconds() if now is None else int(now)
    if not force and int(entry.get("_ReadyAt") or 0) > now:
        _sync_entry(entry, now)
        return None
    entry["ID"] = target_data
    entry.pop("TargetData", None)
    entry.pop("ConstructionTimer", None)
    entry.pop("_ReadyAt", None)
    entry.pop("_TotalSeconds", None)
    entry.pop("_PendingRuntime", None)
    entry.pop("_ClientRuntimeID", None)
    return target_data
