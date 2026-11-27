"""Natural obstacles backed by ``forests.csv``."""

from Logic import HomeObjects
from Logic.GameData import GameData, TABLE_IDS
from Logic.GameTime import now_seconds, remaining_seconds, sync_timer

FOREST_TYPE = TABLE_IDS["forests"]
KEY = "Forests"


def entry_for(data, runtime_id):
    _index, entry = HomeObjects.find_by_runtime_id(data, runtime_id)
    if entry is None or HomeObjects.object_type(entry) != FOREST_TYPE:
        return None
    return entry


def data_row(entry):
    return GameData.instance().row_for(
        entry.get("ID")) if entry is not None else None


def record(data, runtime_id):
    records = data.setdefault(KEY, {})
    if not isinstance(records, dict):
        records = {}
        data[KEY] = records
    value = records.setdefault(str(runtime_id), {})
    if not isinstance(value, dict):
        value = {}
        records[str(runtime_id)] = value
    return value


def begin(data, runtime_id, row, instant=False, now=None):
    now = now_seconds() if now is None else int(now)
    value = record(data, runtime_id)
    duration = max(0, row.seconds())
    ready_at = now if instant else now + duration
    value.update({
        "DataId": row.global_id,
        "StartedAt": now,
        "Ready": ready_at,
        "TotalSeconds": duration,
        "Exp": row.i("ExpClear", 0),
    })
    entry = entry_for(data, runtime_id)
    if entry is not None:
        entry["DestructionStarted"] = True
        entry["_ReadyAt"] = ready_at
        entry["_TotalSeconds"] = duration
        sync_timer(entry, "DestructionTimer", duration, ready_at, now)
        if ready_at <= now:
            entry["_DestroyCompletedAt"] = ready_at
    return value


def sync(data, now=None):
    """Restore destruction timers from their absolute persisted deadlines."""
    now = now_seconds() if now is None else int(now)
    records = data.setdefault(KEY, {})
    if not isinstance(records, dict):
        records = {}
        data[KEY] = records

    # Absolute deadlines live on the object itself so runtime-id renumbering
    # while loading the home cannot detach them from their record.
    for entry in data.get("Objects", []):
        if HomeObjects.object_type(entry) != FOREST_TYPE:
            continue
        runtime_id = str(HomeObjects.runtime_id_for(
            entry, data.get("Objects", [])))
        ready_at = entry.get("_ReadyAt")
        total = max(0, int(entry.get("_TotalSeconds", 0) or 0))
        if ready_at is None:
            value = records.get(runtime_id)
            if isinstance(value, dict):
                ready_at = value.get("Ready")
                total = max(0, int(value.get("TotalSeconds", 0) or 0))
                if ready_at is not None:
                    entry["_ReadyAt"] = int(ready_at)
                    entry["_TotalSeconds"] = total
        if ready_at is None:
            timer = entry.get("DestructionTimer")
            left = remaining_seconds(timer)
            if left <= 0:
                continue
            total = max(
                left, int(timer.get("StartSeconds", left) or left)
                if isinstance(timer, dict) else left)
            ready_at = now + left
            entry["_ReadyAt"] = ready_at
            entry["_TotalSeconds"] = total
        try:
            ready_at = int(ready_at)
        except (TypeError, ValueError):
            continue
        entry["DestructionStarted"] = True
        sync_timer(entry, "DestructionTimer", total, ready_at, now)
        records[runtime_id] = {
            "DataId": int(entry.get("ID") or 0),
            "StartedAt": min(now, ready_at - total),
            "Ready": ready_at,
            "TotalSeconds": total,
        }
        if ready_at <= now:
            entry.pop("_ReadyAt", None)
            entry.pop("_TotalSeconds", None)
            entry["_DestroyCompletedAt"] = ready_at

    for runtime_id, value in list(records.items()):
        entry = entry_for(data, runtime_id)
        if entry is None:
            records.pop(runtime_id, None)
            continue
        if entry.get("_ReadyAt") is not None:
            continue
        if not isinstance(value, dict):
            records.pop(runtime_id, None)
            entry.pop("DestructionTimer", None)
            continue
        try:
            ready_at = int(value.get("Ready") or 0)
            total = max(0, int(value.get("TotalSeconds") or 0))
        except (TypeError, ValueError):
            continue
        entry["DestructionStarted"] = True
        sync_timer(entry, "DestructionTimer", total, ready_at, now)
        if ready_at <= now:
            entry["_DestroyCompletedAt"] = ready_at

    # Legacy saves may only have the client timer; infer an absolute deadline
    # so it continues counting across reconnects instead of resetting.
    for entry in data.get("Objects", []):
        if HomeObjects.object_type(entry) != FOREST_TYPE:
            continue
        runtime_id = str(HomeObjects.runtime_id_for(
            entry, data.get("Objects", [])))
        if runtime_id in records:
            continue
        timer = entry.get("DestructionTimer")
        left = remaining_seconds(timer)
        if left <= 0:
            continue
        total = max(
            left, int(timer.get("StartSeconds", left) or left)
            if isinstance(timer, dict) else left)
        records[runtime_id] = {
            "DataId": int(entry.get("ID") or 0),
            "StartedAt": now,
            "Ready": now + left,
            "TotalSeconds": total,
        }
