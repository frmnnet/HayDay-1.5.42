"""Placed fruit-tree/bush state backed by ``fruit_trees.csv``."""
from Logic.GameTime import (
    now_seconds, remaining_seconds, sync_timer,
)
from Logic import HomeObjects
from Logic.GameData import GameData, TABLE_IDS

TREE_TYPE = TABLE_IDS["fruit_trees"]


def entry_for(data, runtime_id):
    _index, entry = HomeObjects.find_by_runtime_id(data, runtime_id)
    if entry is None or HomeObjects.object_type(entry) != TREE_TYPE:
        return None
    return entry


def data_row(entry):
    if entry is None:
        return None
    return GameData.instance().row_for(entry.get("ID"))


def phase_values(row, entry):
    if row is None:
        return None
    phase = max(1, int(entry.get("Phase", 1) or 1))
    sources = [row.values] + list(row.subs)
    return sources[min(phase - 1, len(sources) - 1)]


def fruit_item(row):
    if row is None:
        return None
    name = row.s("Name")
    for suffix in ("Tree", "Bush"):
        if name.endswith(suffix):
            name = name[:-len(suffix)]
            break
    return GameData.instance().item(name)


def fruit_count(row, entry):
    values = phase_values(row, entry)
    if values is None:
        return 0
    try:
        return max(0, int(values.get("FruitCount") or 0))
    except (TypeError, ValueError):
        return 0


def _phase_duration(row, phase):
    values = phase_values(
        row, {"Phase": max(1, int(phase or 1))})
    if values is None:
        return 0
    try:
        return (
            int(values.get("TimeSec") or 0)
            + 60 * int(values.get("TimeMin") or 0)
        )
    except (TypeError, ValueError):
        return 0


def _max_phase(row):
    return max(1, 1 + len(row.subs))


def start_growth(data, runtime_id, row, now=None, phase=None,
                 immediate=False):
    """Start or refresh one tree's absolute growth deadline."""
    now = now_seconds() if now is None else int(now)
    entry = entry_for(data, runtime_id)
    if entry is None or row is None:
        return None
    return start_growth_entry(entry, row, now=now, phase=phase,
                              immediate=immediate)


def start_growth_entry(entry, row, now=None, phase=None, immediate=False):
    now = now_seconds() if now is None else int(now)
    if entry is None or row is None:
        return None
    if phase is not None:
        entry["Phase"] = max(1, min(_max_phase(row), int(phase)))
    else:
        entry["Phase"] = max(1, min(
            _max_phase(row), int(entry.get("Phase", 1) or 1)))
    count = max(1, fruit_count(row, entry))
    entry["Fruits"] = [False] * count
    duration = _phase_duration(row, entry["Phase"])
    if immediate or duration <= 0:
        entry["Fruits"] = [True] * count
        entry.pop("GrowTimer", None)
        entry.pop("_ReadyAt", None)
        entry.pop("_TotalSeconds", None)
        entry["_CompletedAt"] = now
        return entry
    ready_at = now + duration
    entry["_ReadyAt"] = ready_at
    entry["_TotalSeconds"] = duration
    entry.pop("_CompletedAt", None)
    sync_timer(entry, "GrowTimer", duration, ready_at, now)
    return entry


def sync(data, now=None):
    """Advance tree growth from persisted deadlines or legacy timer ticks."""
    now = now_seconds() if now is None else int(now)
    for entry in data.get("Objects", []):
        if HomeObjects.object_type(entry) != TREE_TYPE:
            continue
        total = int(entry.get("_TotalSeconds", 0) or 0)
        ready_at = entry.get("_ReadyAt")
        if ready_at is None:
            timer = entry.get("GrowTimer")
            left = remaining_seconds(timer)
            if left <= 0:
                continue
            total = max(
                left, int(
                    timer.get("StartSeconds", left) or left)
                if isinstance(timer, dict) else left)
            ready_at = now + left
            entry["_ReadyAt"] = ready_at
            entry["_TotalSeconds"] = total
        try:
            ready_at = int(ready_at)
        except (TypeError, ValueError):
            entry.pop("_ReadyAt", None)
            entry.pop("_TotalSeconds", None)
            entry.pop("GrowTimer", None)
            continue
        if ready_at <= now:
            row = data_row(entry)
            count = max(1, fruit_count(row, entry)) if row is not None else max(
                len(entry.get("Fruits") or []), 1)
            entry["Fruits"] = [True] * count
            entry.pop("GrowTimer", None)
            entry.pop("_ReadyAt", None)
            entry.pop("_TotalSeconds", None)
            entry["_CompletedAt"] = ready_at
        else:
            sync_timer(entry, "GrowTimer", total, ready_at, now)


def start_next_growth(entry, row, now=None):
    """Start regrowth only after the tree has no collectable fruit left."""
    if entry is None or row is None:
        return None
    fruits = entry.get("Fruits")
    if isinstance(fruits, list) and any(bool(value) for value in fruits):
        return entry
    phase = min(
        _max_phase(row),
        max(1, int(entry.get("Phase", 1) or 1)) + 1)
    return start_growth_entry(entry, row, now=now, phase=phase)


def finish_growth(entry, row, now=None):
    now = now_seconds() if now is None else int(now)
    if entry is None or row is None:
        return None
    count = max(1, fruit_count(row, entry))
    entry["Fruits"] = [True] * count
    entry.pop("GrowTimer", None)
    entry.pop("_ReadyAt", None)
    entry.pop("_TotalSeconds", None)
    entry["_CompletedAt"] = now
    return entry
