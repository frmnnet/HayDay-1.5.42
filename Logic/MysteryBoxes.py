"""Mystery-box spawner, object state and reward handling.

The 1.5.42 client persists mystery boxes as normal entries in ``Objects``.
``LogicMysteryBox::save/load`` writes the JSON keys mirrored here, while
``LogicMysteryBoxSpawner::save/load`` owns the home spawn timer.  The old
private ``MysteryBoxes`` dictionary was never read by the client and lost both
the visible box and its reward.
"""
import random
import time

from Logic import HomeObjects, Storage
from Logic.GameData import GameData, TABLE_IDS
from Logic.GameTime import seconds_to_ticks, ticks_to_seconds
from Utils.Logging import logger


BOX_TABLE = TABLE_IDS["mystery_boxes"]
SPAWNER_TABLE = TABLE_IDS["mystery_box_spawners"]
BOX_TYPE = BOX_TABLE
SPAWNER_TYPE = SPAWNER_TABLE
SPAWNER_ID = SPAWNER_TABLE * 100000
SPAWNER_UNLOCK_LEVEL = 5
OPEN_TIMER_SECONDS = 24 * 60 * 60

CASH_GLOBAL_ID = 1900000
DIAMONDS_GLOBAL_ID = 1900001
FREE_DIAMONDS_GLOBAL_ID = 1900015
VOUCHER_GLOBAL_ID = 1900052


def _objects(data):
    objects = data.setdefault("Objects", [])
    if not isinstance(objects, list):
        objects = []
        data["Objects"] = objects
    return objects


def boxes(data):
    return [
        entry for entry in _objects(data)
        if isinstance(entry, dict)
        and HomeObjects.object_type(entry) == BOX_TYPE
    ]


def spawner(data):
    for entry in _objects(data):
        if (isinstance(entry, dict)
                and HomeObjects.object_type(entry) == SPAWNER_TYPE):
            return entry
    return None


def find_box(data, runtime_id):
    index, entry = HomeObjects.find_by_runtime_id(data, runtime_id)
    if entry is None or HomeObjects.object_type(entry) != BOX_TYPE:
        return None, None
    return index, entry


def _remove(data, entry):
    objects = _objects(data)
    try:
        objects.remove(entry)
    except ValueError:
        return False
    return True


def _duration_timer(total_seconds, seconds_left):
    seconds_left = max(0, int(seconds_left))
    if seconds_left <= 0:
        return None
    return {
        "StartSeconds": max(1, int(total_seconds)),
        "TicksLeft": seconds_to_ticks(seconds_left),
    }


def _seconds_left(timer):
    if not isinstance(timer, dict):
        return 0
    try:
        return ticks_to_seconds(timer.get("TicksLeft", 0))
    except (TypeError, ValueError):
        return 0


def _spawn_interval(last_opened):
    row = GameData.instance().row(SPAWNER_TABLE, 0)
    if row is None:
        return (30, 400) if last_opened else (300, 28800)
    if last_opened:
        low, high = row.i("MinSpawnTimeOpened", 30), row.i(
            "MaxSpawnTimeOpened", 400)
    else:
        low, high = row.i("MinSpawnTimeClosed", 300), row.i(
            "MaxSpawnTimeClosed", 28800)
    low, high = max(1, low), max(1, high)
    if high < low:
        low, high = high, low
    return low, high


def _next_interval(last_opened):
    low, high = _spawn_interval(bool(last_opened))
    return random.randint(low, high)


def _new_spawner(now):
    return {
        "ID": SPAWNER_ID,
        "Timer": 0,
        "LastOpened": False,
        "TimerFriend": 0,
        "LastOpenedFriend": False,
        "_SpawnStartedAt": int(now),
        "_SpawnInterval": _next_interval(False),
    }


def _set_next_spawn(entry, now):
    entry["Timer"] = 0
    entry["_SpawnStartedAt"] = int(now)
    entry["_SpawnInterval"] = _next_interval(
        bool(entry.get("LastOpened")))
    entry["_NextSpawnAt"] = int(now) + entry["_SpawnInterval"]


def _opened_seconds_since(entry, now):
    started = entry.get("_OpenedAt")
    if started is None:
        return max(
            0,
            OPEN_TIMER_SECONDS - _seconds_left(entry.get("OpenedBoxTimer")))
    try:
        return min(
            OPEN_TIMER_SECONDS,
            max(0, int(now) - int(started)))
    except (TypeError, ValueError):
        return OPEN_TIMER_SECONDS


def _refresh_timers(entry, now, has_box):
    opened_at = entry.get("_OpenedAt")
    if opened_at is not None:
        try:
            left = max(0, int(opened_at) + OPEN_TIMER_SECONDS - int(now))
        except (TypeError, ValueError):
            left = 0
        timer = _duration_timer(OPEN_TIMER_SECONDS, left)
        if timer is None:
            entry.pop("OpenedBoxTimer", None)
        else:
            entry["OpenedBoxTimer"] = timer

    if has_box:
        return
    next_at = entry.get("_NextSpawnAt")
    if next_at is None:
        started = int(entry.get("_SpawnStartedAt", now) or now)
        interval = max(1, int(entry.get("_SpawnInterval", 1) or 1))
        next_at = started + interval
        entry["_NextSpawnAt"] = next_at
    try:
        interval = max(1, int(entry.get("_SpawnInterval", 1) or 1))
        elapsed = max(0, min(interval, int(now) - int(next_at) + interval))
    except (TypeError, ValueError):
        elapsed = 0
    entry["Timer"] = elapsed


def _occupied_cells(data):
    occupied = set()
    game_data = GameData.instance()
    for entry in _objects(data):
        if not isinstance(entry, dict):
            continue
        data_type = HomeObjects.object_type(entry)
        if data_type in (BOX_TYPE, SPAWNER_TYPE):
            continue
        try:
            x = int(entry.get("X") or 0)
            y = int(entry.get("Y") or 0)
        except (TypeError, ValueError):
            continue
        row = game_data.row_for(entry.get("ID"))
        width = max(1, row.i("TileWidth", 1)) if row is not None else 1
        height = max(1, row.i("TileHeight", 1)) if row is not None else 1
        for tile_x in range(x, x + width):
            for tile_y in range(y, y + height):
                occupied.add((tile_x, tile_y))
    return occupied


def _box_position(data):
    try:
        width = max(1, int(data.get("TileMapWidth", 48) or 48))
        height = max(1, int(data.get("TileMapHeight", 32) or 32))
    except (TypeError, ValueError):
        width, height = 48, 32
    min_x, min_y = 6, 6
    max_x, max_y = max(min_x, width - 8), max(min_y, height - 8)
    occupied = _occupied_cells(data)
    candidates = [
        (x, y)
        for y in range(min_y, max_y + 1)
        for x in range(min_x, max_x + 1)
        if all((x + dx, y + dy) not in occupied
               for dx in range(2) for dy in range(2))
    ]
    if not candidates:
        return min(max(1, width // 2), width - 2), min(
            max(1, height // 2), height - 2)
    return random.choice(candidates)


def _reward_global_id(name):
    key = (name or "").strip().lower()
    if key == "freediamonds":
        return FREE_DIAMONDS_GLOBAL_ID
    if key == "cashingems":
        return CASH_GLOBAL_ID
    if key == "voucher":
        return VOUCHER_GLOBAL_ID
    row = GameData.instance().item(name)
    return row.global_id if row is not None else None


def _random_voucher(level):
    rows = []
    for row in GameData.instance().rows(TABLE_IDS["vouchers"]):
        if row.i("UnlockLevel", 0) <= int(level or 1):
            rows.append(row)
    if not rows:
        rows = list(GameData.instance().rows(TABLE_IDS["vouchers"]))
    if not rows:
        return None
    total = sum(max(1, row.i("Probability", 1)) for row in rows)
    pick = random.randrange(max(1, total))
    for row in rows:
        pick -= max(1, row.i("Probability", 1))
        if pick < 0:
            return row
    return rows[-1]


def _cash_value(amount, level):
    row = GameData.instance().level_row(int(level or 1))
    rate = row.i("DiamondsToCoinsRate", 1) if row is not None else 1
    return max(1, (max(1, int(amount or 0)) * max(1, rate)) // 100)


def _reward_for_box(entry, level):
    """Return ``(global_id, amount)`` for an opened box."""
    reward_id = int(entry.get("GoodGlobalId", -1) or -1)
    amount = max(0, int(entry.get("GoodAmount", 0) or 0))
    if reward_id == CASH_GLOBAL_ID:
        return CASH_GLOBAL_ID, _cash_value(amount, level)
    if reward_id == VOUCHER_GLOBAL_ID:
        voucher = _random_voucher(level)
        if voucher is None:
            return None, 0
        return voucher.global_id, max(1, amount)
    return reward_id, amount


def _grant(state, reward_id, amount):
    if reward_id is None or amount <= 0:
        return False
    if reward_id == CASH_GLOBAL_ID:
        state.account_delta(cash=amount)
        state.account_stat("cash_earned", amount)
        return True
    if reward_id in (DIAMONDS_GLOBAL_ID, FREE_DIAMONDS_GLOBAL_ID):
        state.account_delta(diamonds=amount)
        state.account_stat("diamonds_earned", amount)
        return True
    if GameData.instance().row_for(reward_id) is None:
        return False
    if (Storage.storage_kind(reward_id) is not None
            and not Storage.can_store(state.home.data, reward_id, amount)):
        return False
    accepted = Storage.store(
        state.home.data, state.home.inventory, reward_id, amount)
    if accepted != amount:
        logger.info(
            "[MYSTERY_BOX] storage accepted {}/{} for reward {}".format(
                accepted, amount, reward_id))
    return accepted == amount


def _drop_box(state, entry, opened, now):
    data = state.home.data
    _remove(data, entry)
    sp = spawner(data)
    if sp is None:
        return
    now = int(now)
    sp["LastOpened"] = bool(opened)
    sp["Timer"] = 0
    sp["_SpawnStartedAt"] = now
    if opened:
        sp["_OpenedAt"] = now
        sp["OpenedBoxTimer"] = _duration_timer(
            OPEN_TIMER_SECONDS, OPEN_TIMER_SECONDS)
    _set_next_spawn(sp, now)


def ensure_spawner(data, level, now=None):
    """Create/repair the invisible spawner and return it."""
    now = int(time.time()) if now is None else int(now)
    level = int(level or 1)
    if level < SPAWNER_UNLOCK_LEVEL:
        return None
    entry = spawner(data)
    if entry is None:
        entry = _new_spawner(now)
        _objects(data).append(entry)
    entry["ID"] = SPAWNER_ID
    entry.setdefault("Timer", 0)
    entry.setdefault("LastOpened", False)
    entry.setdefault("TimerFriend", 0)
    entry.setdefault("LastOpenedFriend", False)
    return entry


def spawn_box(data, level, now=None):
    """Spawn one weighted, level-valid box and return its object entry."""
    now = int(time.time()) if now is None else int(now)
    if boxes(data):
        return boxes(data)[0]
    game_data = GameData.instance()
    rows = [
        row for row in game_data.rows(BOX_TABLE)
        if row.i("UnlockLevel", 0) <= int(level or 1)
    ]
    if not rows:
        return None
    total = sum(max(1, row.i("Probability", 1)) for row in rows)
    pick = random.randrange(max(1, total))
    box_row = None
    for row in rows:
        pick -= max(1, row.i("Probability", 1))
        if pick < 0:
            box_row = row
            break
    box_row = box_row or rows[-1]
    reward_id = _reward_global_id(box_row.s("GoodReward"))
    if reward_id is None:
        logger.info("[MYSTERY_BOX] unknown reward {!r}".format(
            box_row.s("GoodReward")))
        return None
    x, y = _box_position(data)
    entry = {
        "X": x,
        "Y": y,
        "GoodGlobalId": reward_id,
        "GoodAmount": max(1, box_row.i("GoodAmount", 1)),
        "DiamondCost": max(0, box_row.i("DiamondPrice", 0)),
        "GoodGlobalIdToReward": -1,
        "ID": box_row.global_id,
        "_AccurateX": x * 512,
        "_AccurateY": y * 512,
    }
    _objects(data).append(entry)
    logger.info("[MYSTERY_BOX] spawned {} at {},{}".format(
        box_row.global_id, x, y))
    return entry


def sync(state, level=None, now=None):
    """Repair persisted state and advance spawner timers."""
    now = int(time.time()) if now is None else int(now)
    level = int(level or getattr(state.account, "exp_level", 1) or 1)
    data = state.home.data
    changed = False

    # Migrate the old bookkeeping bucket: it never represented a client box.
    legacy = data.get("MysteryBoxes")
    if legacy:
        data["MysteryBoxes"] = {}
        changed = True

    # The client supports one box at a time.  Resolve accidental duplicates
    # from earlier server revisions while retaining the first real box.
    existing = boxes(data)
    if len(existing) > 1:
        for duplicate in existing[1:]:
            _remove(data, duplicate)
        changed = True
        logger.info("[MYSTERY_BOX] removed {} duplicate objects".format(
            len(existing) - 1))

    sp = ensure_spawner(data, level, now)
    if sp is None:
        for entry in boxes(data):
            _remove(data, entry)
        return changed

    current = boxes(data)
    next_at = sp.get("_NextSpawnAt")
    _refresh_timers(sp, now, bool(current))
    if not current:
        if next_at is None:
            # Existing installs have been played for a long time and should
            # receive their overdue box immediately after this migration.
            if "_SpawnStartedAt" not in sp:
                sp["_SpawnStartedAt"] = now
            if spawn_box(data, level, now) is not None:
                sp.pop("_NextSpawnAt", None)
                changed = True
        else:
            try:
                due = int(next_at) <= now
            except (TypeError, ValueError):
                due = True
            if due and spawn_box(data, level, now) is not None:
                sp.pop("_NextSpawnAt", None)
                changed = True
    if current:
        sp.pop("_NextSpawnAt", None)
    return changed


def check(command, state, now=None):
    now = int(time.time()) if now is None else int(now)
    _, entry = find_box(state.home.data, command.f0)
    if entry is None:
        return False
    if entry.get("LockedChecked"):
        return False
    sp = ensure_spawner(
        state.home.data, state.account.exp_level, now)
    if sp is None:
        return False
    seconds = _opened_seconds_since(sp, now)
    box = GameData.instance().row_for(entry.get("ID"))
    maximum = box.i("RandomNumberMax", 16) if box is not None else 16
    entry["LockedChecked"] = True
    entry["Locked"] = random.randrange(max(1, maximum + 1)) - (
        seconds // 3600) > 0
    state.save()
    logger.info("[MYSTERY_BOX] checked box {}: locked={} age={}s".format(
        command.f0, entry["Locked"], seconds))
    return True


def open_box(command, state, now=None):
    now = int(time.time()) if now is None else int(now)
    _, entry = find_box(state.home.data, command.f0)
    if entry is None:
        logger.info("[MYSTERY_BOX] open {}: box missing".format(command.f0))
        return False
    if not entry.get("LockedChecked"):
        logger.info("[MYSTERY_BOX] open {}: check command missing".format(
            command.f0))
        return False

    locked = bool(entry.get("Locked"))
    diamond_cost = max(0, int(entry.get("DiamondCost", 0) or 0))
    reward_id, amount = _reward_for_box(entry, state.account.exp_level)
    if reward_id is None or amount <= 0:
        logger.info("[MYSTERY_BOX] open {}: invalid reward".format(
            command.f0))
        return False
    if (Storage.storage_kind(reward_id) is not None
            and not Storage.can_store(state.home.data, reward_id, amount)):
        logger.info("[MYSTERY_BOX] open {}: storage full for {} x{}".format(
            command.f0, reward_id, amount))
        return False
    if locked and diamond_cost and not command.spend_diamonds(
            state, diamond_cost):
        return False
    if not _grant(state, reward_id, amount):
        return False

    _drop_box(state, entry, opened=True, now=now)
    state.account_stat("mystery_boxes_opened", 1)
    state.save()
    logger.info(
        "[MYSTERY_BOX] opened {} -> reward {} x{} (locked={}, cost={})"
        .format(command.f0, reward_id, amount, locked,
                diamond_cost if locked else 0))
    return True


def discard(command, state):
    _, entry = find_box(state.home.data, command.f0)
    if entry is None:
        return True
    if not entry.get("LockedChecked"):
        return False
    _drop_box(state, entry, opened=False, now=int(time.time()))
    state.save()
    logger.info("[MYSTERY_BOX] discarded {}".format(command.f0))
    return True


def fade_away(command, state):
    _, entry = find_box(state.home.data, command.f0)
    if entry is None:
        return True
    reward_id = int(entry.get("GoodGlobalIdToReward", -1) or -1)
    amount = max(0, int(entry.get("GoodAmountToReward", 0) or 0))
    if reward_id >= 0 and amount > 0:
        if not _grant(state, reward_id, amount):
            return False
    _drop_box(
        state, entry, opened=reward_id >= 0, now=int(time.time()))
    state.save()
    logger.info("[MYSTERY_BOX] faded away {}".format(command.f0))
    return True
