"""Field state in the client's persisted ``Objects`` array.

The client does not read the server's old top-level ``Fields`` dictionary.
It instantiates field objects from home JSON and uses each object's ``ID``
as the crop data id (``400000`` means empty field).  Keeping both views in
sync makes planted/harvested fields survive a reconnect.
"""
from Logic import HomeObjects
from Logic.Fields import Field, FieldManager
from Logic.GameTime import now_seconds, seconds_to_ticks, ticks_to_seconds

EMPTY_FIELD_ID = 400000
FIELD_TIMER_KEY = "Timer"
LEGACY_FIELD_TIMER_KEY = "GrowTimer"


def _entry_timer(entry):
    """Read the client's field timer, including pre-fix server saves."""
    timer = entry.get(FIELD_TIMER_KEY)
    if not isinstance(timer, dict):
        timer = entry.get(LEGACY_FIELD_TIMER_KEY)
    return timer


def _clear_timer(entry):
    entry.pop(FIELD_TIMER_KEY, None)
    entry.pop(LEGACY_FIELD_TIMER_KEY, None)


def _ticks_left(entry, now):
    timer = _entry_timer(entry)
    if not isinstance(timer, dict):
        return 0, 0
    try:
        ticks = max(0, int(timer.get("TicksLeft") or 0))
        total = max(0, int(timer.get("StartSeconds") or 0))
    except (TypeError, ValueError):
        return 0, 0
    return total, ticks


def _ready_at(entry):
    """Return the persisted absolute crop deadline, if one exists."""
    if not isinstance(entry, dict):
        return None
    try:
        value = int(entry.get("_ReadyAt"))
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _set_timer(entry, total_seconds, ticks_left):
    ticks_left = max(0, int(ticks_left))
    if ticks_left <= 0:
        _clear_timer(entry)
        return
    # LogicField::save/load uses "Timer".  Writing "GrowTimer" leaves the
    # client-side LogicTimer at zero, which makes every crop look ready.
    entry[FIELD_TIMER_KEY] = {
        "StartSeconds": max(0, int(total_seconds)),
        "TicksLeft": ticks_left,
    }
    entry.pop(LEGACY_FIELD_TIMER_KEY, None)


def entry_for(data, field_id):
    """Return the JSON entry for one field runtime id."""
    _, entry = HomeObjects.resolve_runtime_id(data, field_id)
    if entry is None or HomeObjects.object_type(entry) != 4:
        return None
    return entry


def sync_manager(data, manager=None, now=None):
    """Rebuild the in-memory field view from client-visible objects."""
    now = now_seconds() if now is None else int(now)
    manager = manager or FieldManager(data.setdefault("Fields", {}))
    existing_states = {
        str(key): Field.from_dict(value)
        for key, value in manager.data.items()
    }
    manager.data.clear()
    objects = data.setdefault("Objects", [])
    for entry in objects:
        if HomeObjects.object_type(entry) != 4:
            continue
        runtime_id = HomeObjects.runtime_id_for(entry, objects)
        crop = int(entry.get("ID") or 0)
        if crop == EMPTY_FIELD_ID:
            _clear_timer(entry)
            entry.pop("_ReadyAt", None)
            manager.set(runtime_id, Field(crop=0, state=Field.EMPTY,
                                          planted=0, ready=0))
        else:
            existing = existing_states.get(str(runtime_id), Field(crop=0))
            total, ticks = _ticks_left(entry, now)
            deadline = _ready_at(entry)
            if deadline is None and ticks > 0:
                deadline = now + ticks_to_seconds(ticks)
                entry["_ReadyAt"] = deadline
            if existing.crop == crop and existing.state == Field.GROWING:
                if deadline is not None:
                    existing.ready = deadline
                if existing.ready > now:
                    _set_timer(
                        entry,
                        existing.ready - existing.planted,
                        seconds_to_ticks(existing.ready - now),
                    )
                    manager.set(runtime_id, existing)
                    continue
                existing.state = Field.READY
                _clear_timer(entry)
                entry.pop("_ReadyAt", None)
                manager.set(runtime_id, existing)
            elif existing.crop == crop and existing.state == Field.READY:
                _clear_timer(entry)
                entry.pop("_ReadyAt", None)
                manager.set(runtime_id, existing)
            elif deadline is not None and deadline > now:
                total = max(1, total)
                _set_timer(entry, total, seconds_to_ticks(deadline - now))
                manager.set(runtime_id, Field(
                    crop=crop, state=Field.GROWING,
                    planted=deadline - total, ready=deadline))
            else:
                # Objects without a live Timer are mature.
                _clear_timer(entry)
                entry.pop("_ReadyAt", None)
                manager.set(runtime_id, Field(crop=crop, state=Field.READY,
                                              planted=0, ready=0))
    return manager


def advance(data, manager, now=None):
    """Advance crop deadlines and mirror their remaining time to the client."""
    now = now_seconds() if now is None else int(now)
    sync_manager(data, manager, now=now)
    grown = manager.grow_all(now)
    sync_manager(data, manager, now=now)
    return grown


def set_growing(data, field_id, crop, total_seconds=None, ready_at=None,
                now=None):
    entry = entry_for(data, field_id)
    if entry is None:
        return None
    entry["ID"] = int(crop)
    entry.pop("_HarvestStarted", None)
    entry.pop("_ResourceGained", None)
    now = now_seconds() if now is None else int(now)
    ready_at = int(ready_at or (now + int(total_seconds or 0)))
    entry["_ReadyAt"] = ready_at
    _set_timer(entry, total_seconds or max(0, ready_at - now),
               seconds_to_ticks(max(0, ready_at - now)))
    return entry


def set_ready(data, field_id, crop):
    entry = entry_for(data, field_id)
    if entry is None:
        return None
    entry["ID"] = int(crop)
    _clear_timer(entry)
    entry.pop("_ReadyAt", None)
    return entry


def set_empty(data, field_id):
    entry = entry_for(data, field_id)
    if entry is None:
        return None
    entry["ID"] = EMPTY_FIELD_ID
    _clear_timer(entry)
    entry.pop("_ReadyAt", None)
    entry.pop("_HarvestStarted", None)
    entry.pop("_ResourceGained", None)
    return entry


def crop_for(data, field_id):
    entry = entry_for(data, field_id)
    if entry is None:
        return 0
    crop = int(entry.get("ID") or 0)
    return 0 if crop == EMPTY_FIELD_ID else crop


def is_ready(data, field_id, now=None):
    """Whether a field has a crop and no remaining Timer time."""
    if not crop_for(data, field_id):
        return False
    entry = entry_for(data, field_id)
    if entry is None:
        return False
    now = now_seconds() if now is None else int(now)
    deadline = _ready_at(entry)
    if deadline is not None:
        return deadline <= now
    timer = _entry_timer(entry)
    if not isinstance(timer, dict):
        # Mature fields saved by the client omit Timer.
        return True
    try:
        return ticks_to_seconds(timer.get("TicksLeft", 0)) <= 0
    except (TypeError, ValueError):
        return False


def seconds_left(data, field_id, now=None):
    """Remaining crop time from the server's absolute deadline."""
    entry = entry_for(data, field_id)
    if entry is None:
        return 0
    now = now_seconds() if now is None else int(now)
    deadline = _ready_at(entry)
    if deadline is not None:
        return max(0, deadline - now)
    timer = _entry_timer(entry)
    if not isinstance(timer, dict):
        return 0
    try:
        return ticks_to_seconds(timer.get("TicksLeft", 0))
    except (TypeError, ValueError):
        return 0
