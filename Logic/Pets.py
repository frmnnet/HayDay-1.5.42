"""Table-driven pet state for placed pet objects."""

from Logic import HomeObjects
from Logic.GameData import GameData, TABLE_IDS
from Logic.GameTime import (
    now_seconds, remaining_seconds, sync_timer,
)

PET_TYPE = TABLE_IDS["pets"]
HABITAT_TYPE = TABLE_IDS["pet_habitats"]
PET_TIMERS_KEY = "_PetFeedTimers"


def entry_for(data, runtime_id):
    _index, entry = HomeObjects.find_by_runtime_id(data, runtime_id)
    if entry is None or HomeObjects.object_type(entry) != PET_TYPE:
        return None
    return entry


def data_row(entry):
    return GameData.instance().row_for(
        entry.get("ID")) if entry is not None else None


def habitat_row(pet_row):
    if pet_row is None:
        return None
    return GameData.instance().find(79, pet_row.s("Habitat"))


def _timers(data):
    timers = data.setdefault(PET_TIMERS_KEY, {})
    if not isinstance(timers, dict):
        timers = {}
        data[PET_TIMERS_KEY] = timers
    return timers


def feed_pet(data, runtime_id, now=None):
    now = now_seconds() if now is None else int(now)
    entry = entry_for(data, runtime_id)
    row = data_row(entry)
    habitat = habitat_row(row)
    if entry is None or row is None or habitat is None:
        return None, None, 0
    feed = GameData.instance().item(habitat.s("Feed"))
    amount = max(1, habitat.i("FeedAmount", 1))
    duration = max(0, row.i("FedDurationMinutes", 0) * 60)
    entry["Habitat"] = -1
    ready_at = now + duration
    sync_timer(entry, "T", duration, ready_at, now)
    _timers(data)[str(runtime_id)] = {
        "DataId": int(row.global_id),
        "FedAt": now,
        "Ready": ready_at,
        "TotalSeconds": duration,
    }
    return entry, feed, amount


def add(data, data_id, accurate_x, accurate_y, habitat_id=None,
        mirrored=False):
    parent_x = 0
    parent_y = 0
    if habitat_id is not None:
        _index, parent = HomeObjects.find_by_runtime_id(data, habitat_id)
        if parent is not None and HomeObjects.object_type(parent) == HABITAT_TYPE:
            parent_x = int(parent.get(
                "_AccurateX", int(parent.get("X") or 0) * 512))
            parent_y = int(parent.get(
                "_AccurateY", int(parent.get("Y") or 0) * 512))
    relative_x = int(accurate_x) - parent_x
    relative_y = int(accurate_y) - parent_y
    entry = {
        "ID": int(data_id),
        "X": relative_x >> 9,
        "Y": relative_y >> 9,
        "_AccurateX": relative_x,
        "_AccurateY": relative_y,
        "Habitat": -1,
        "_PendingRuntime": True,
    }
    if mirrored:
        entry["Mirrored"] = True
    data.setdefault("Objects", []).append(entry)
    return entry


def clear_timer(entry):
    if entry is not None:
        entry.pop("T", None)


def sync(data, now=None):
    """Restore pet feeding timers from absolute deadlines after reconnect."""
    now = now_seconds() if now is None else int(now)
    timers = _timers(data)
    for runtime_id, timer in list(timers.items()):
        entry = entry_for(data, runtime_id)
        if entry is None:
            timers.pop(runtime_id, None)
            continue
        try:
            ready_at = int(timer.get("Ready") or 0)
            total = max(0, int(timer.get("TotalSeconds") or 0))
        except (TypeError, ValueError):
            timers.pop(runtime_id, None)
            entry.pop("T", None)
            continue
        sync_timer(entry, "T", total, ready_at, now)

    for entry in data.get("Objects", []):
        if HomeObjects.object_type(entry) != PET_TYPE:
            continue
        runtime_id = str(HomeObjects.runtime_id_for(
            entry, data.get("Objects", [])))
        if runtime_id in timers:
            continue
        current = entry.get("T")
        remaining = remaining_seconds(current)
        if remaining > 0:
            total = max(
                remaining,
                int(current.get("StartSeconds", remaining) or remaining))
            timers[runtime_id] = {
                "DataId": int(entry.get("ID") or 0),
                "FedAt": now,
                "Ready": now + remaining,
                "TotalSeconds": total,
            }
    return timers


def is_ready(data, runtime_id, now=None):
    now = now_seconds() if now is None else int(now)
    entry = entry_for(data, runtime_id)
    if entry is None:
        return False
    timer = _timers(data).get(str(runtime_id))
    if isinstance(timer, dict):
        try:
            return int(timer.get("Ready") or 0) <= now
        except (TypeError, ValueError):
            return False
    return remaining_seconds(entry.get("T")) <= 0


def clear(data, runtime_id):
    entry = entry_for(data, runtime_id)
    clear_timer(entry)
    _timers(data).pop(str(runtime_id), None)
