"""The truck wheel of fortune backed by ``wheel_cars.csv``."""
import random
from Logic.GameData import GameData, TABLE_IDS, GOODS_TABLES

WHEEL_TABLE = TABLE_IDS["wheel_cars"]
WHEEL_ID = WHEEL_TABLE * 100000
WHEEL_POSITION = (17, 37)

STATE_OPEN = 1
STATE_IDLE = 4
STATE_CLOSED = 6

FREE_SPIN = -1
JACKPOT = -2


def _config():
    row = GameData.instance().row(WHEEL_TABLE, 0)
    if row is None:
        raise ValueError("wheel_cars.csv has no row 0")
    return row


def _item_pool(level):
    game_data = GameData.instance()
    decos = [
        row for row in game_data.rows(TABLE_IDS["decorations"])
        if row.b("SpinWheelPrize") and row.i("UnlockLevel", 0) <= level
    ]
    goods = []
    for tid in GOODS_TABLES + [TABLE_IDS["fields"]]:
        for row in game_data.rows(tid):
            if row.i("UnlockLevel", 0) <= level:
                goods.append(row)
    return decos, goods


def _randomize_prizes(entry, level):
    config = _config()
    slots = max(1, config.i("WheelNumSlots", 12))
    jackpot_slot = config.i("WheelJackpotSlot", 0)
    free_slot = config.i("WheelFreeSpinSlot", 6)
    expensive_count = max(0, config.i("WheelNumExpensiveItems", 0))
    deco_count = max(0, config.i("WheelNumDecoItems", 0))

    decos, goods = _item_pool(level)
    goods.sort(
        key=lambda row: (
            row.i("OrderValue", 0),
            row.i("DumbValue", 0),
            row.i("OrderPrice", 0),
        ),
        reverse=True,
    )
    candidates = []
    candidates.extend(decos[:deco_count])
    candidates.extend(goods[:expensive_count])
    for row in decos[deco_count:] + goods[expensive_count:]:
        if row not in candidates:
            candidates.append(row)

    prize_ids = [row.global_id for row in candidates]
    while len(prize_ids) < slots:
        # Never emit an invalid data id if the content tables are unusually
        # small; repeat an existing valid prize instead.
        prize_ids.append(prize_ids[-1] if prize_ids else 400001)
    prize_ids = prize_ids[:slots]
    if 0 <= jackpot_slot < slots:
        prize_ids[jackpot_slot] = JACKPOT
    if 0 <= free_slot < slots:
        prize_ids[free_slot] = FREE_SPIN

    for index, prize in enumerate(prize_ids):
        entry["WheelPrize{}".format(index)] = int(prize)
    entry["NumWheelPrizes"] = slots
    return prize_ids


def ensure(data, level=1):
    """Return the wheel object, creating and daily-normalizing it."""
    if int(level or 1) < _config().i("RequiredLevel", 0):
        return None
    # Earlier server builds kept this unrelated metadata key, which the
    # client never reads for LogicSpinWheelCar.
    data.pop("SpinWheel", None)
    objects = data.setdefault("Objects", [])
    entry = next(
        (obj for obj in objects
         if isinstance(obj, dict) and int(obj.get("ID", -1)) == WHEEL_ID),
        None,
    )
    if entry is None:
        x, y = WHEEL_POSITION
        entry = {
            "ID": WHEEL_ID,
            "X": x,
            "Y": y,
            "State": STATE_OPEN,
            "LastInitDayIndex": 0,
            "LastSpinDayIndex": 0,
            "ConsecutiveSpinDays": 0,
            "NumSpins": 1,
            "JackpotCount": 0,
            "BoughtSpins": 0,
            "BoughtSpinsDaily": 0,
        }
        objects.append(entry)
    entry.setdefault("State", STATE_OPEN)
    entry.setdefault("NumSpins", 1)
    entry.setdefault("JackpotCount", 0)
    entry.setdefault("BoughtSpins", 0)
    entry.setdefault("BoughtSpinsDaily", 0)
    entry.setdefault("LastSpinDayIndex", 0)
    entry.setdefault("ConsecutiveSpinDays", 0)
    if int(entry.get("NumWheelPrizes", 0) or 0) != _config().i(
            "WheelNumSlots", 12):
        _randomize_prizes(entry, int(level or 1))
    return entry


def reset_daily(entry, day_index, level):
    """Apply ``LogicSpinWheelCar::dailyReset``."""
    if int(entry.get("LastInitDayIndex", -1) or -1) == int(day_index):
        return False
    entry["LastInitDayIndex"] = int(day_index)
    entry["NumSpins"] = 1
    entry["JackpotCount"] = 0
    entry["BoughtSpins"] = 0
    entry["BoughtSpinsDaily"] = 0
    entry["State"] = STATE_OPEN
    _randomize_prizes(entry, level)
    return True


def ensure_day(entry, day_index, level):
    if entry is None:
        return
    if int(entry.get("LastInitDayIndex", 0) or 0) != int(day_index):
        reset_daily(entry, day_index, level)


def open_wheel(entry):
    entry["State"] = STATE_OPEN


def close_wheel(entry):
    entry["State"] = STATE_CLOSED


def prepare_spin(entry, day_index, prize_type, data_id, count, velocity):
    """Store the client-selected prize without granting it yet."""
    prize_type = int(prize_type)
    data_id = int(data_id)
    count = int(count)
    if prize_type < 1 or prize_type > 4 or count <= 0:
        return False
    available = max(0, int(entry.get("NumSpins", 0) or 0))
    bought = max(0, int(entry.get("BoughtSpins", 0) or 0))
    if available <= 0 and bought <= 0:
        return False
    if prize_type == 1:
        # The client maintains the animated slot ordering locally and may
        # finish on a valid randomized item that is not one of the snapshot
        # ids saved in ``WheelPrizeN``.  Validate the resource itself instead
        # of rejecting an otherwise valid completed spin.
        if data_id <= 0 or GameData.instance().row_for(data_id) is None:
            return False
    if available > 0:
        entry["NumSpins"] = available - 1
    else:
        entry["BoughtSpins"] = bought - 1
    entry["LastSpinDayIndex"] = int(day_index)
    entry["PrizeType"] = prize_type
    entry["PrizeGlobalID"] = data_id
    entry["PrizeCount"] = count
    entry["_LastVelocity"] = int(velocity)
    entry["State"] = STATE_OPEN
    return True


def jackpot_cash(entry, state):
    config = _config()
    level = state.account.exp_level
    level_row = GameData.instance().level_row(level)
    rate = level_row.i("DiamondsToCoinsRate", 1) if level_row else 1
    cash = max(0, config.i("WheelJackpotAsDiamonds", 0)) * max(1, rate)
    remainder = cash % 100
    rounded = cash if remainder < 50 else cash + 100 - remainder
    multiplier = min(3, int(entry.get("JackpotCount", 0) or 0) + 1)
    return rounded * multiplier


def grant_pending(command, state):
    entry = ensure(state.home.data, state.account.exp_level)
    prize_type = int(entry.get("PrizeType", 0) or 0)
    data_id = int(entry.get("PrizeGlobalID", 0) or 0)
    count = int(entry.get("PrizeCount", 0) or 0)
    if prize_type <= 0 or count <= 0:
        return None
    result = {"Type": prize_type, "Data": data_id, "Count": count}
    if prize_type == 1:
        if command.data_row(data_id) is None:
            return None
        from Logic import Storage
        if not Storage.can_store(state.home.data, data_id, count):
            return None
        command.give(state, data_id, count)
    elif prize_type == 2:
        entry["NumSpins"] = 1
        result["FreeSpins"] = 1
    elif prize_type == 3:
        cash = jackpot_cash(entry, state)
        command.earn_cash(state, cash)
        entry["JackpotCount"] = (
            int(entry.get("JackpotCount", 0) or 0) + 1) % 3
        result["Cash"] = cash
    # Type 4 is the wheel's no-prize result.
    entry["PrizeType"] = 0
    entry["PrizeGlobalID"] = 0
    entry["PrizeCount"] = 0
    entry["State"] = STATE_IDLE
    today = int(entry.get("LastSpinDayIndex", 0) or 0)
    last_day = int(entry.get("_ServerLastSpinDay", 0) or 0)
    if today != last_day:
        consecutive = int(entry.get("ConsecutiveSpinDays", 0) or 0)
        entry["ConsecutiveSpinDays"] = (
            consecutive + 1 if last_day and today == last_day + 1 else 1)
        entry["_ServerLastSpinDay"] = today
        from Logic import Achievements
        Achievements.set_progress(
            state, "SpinTheWheel", entry["ConsecutiveSpinDays"])
    return result


def buy_spin(entry):
    config = _config()
    multiplier = max(1, config.i("WheelSpinPriceMultiplier", 1))
    bought_today = max(0, int(entry.get("BoughtSpinsDaily", 0) or 0))
    cost = multiplier * (bought_today + 1)
    return cost


def record_bought_spin(entry):
    entry["BoughtSpins"] = int(entry.get("BoughtSpins", 0) or 0) + 1
    entry["BoughtSpinsDaily"] = int(
        entry.get("BoughtSpinsDaily", 0) or 0) + 1
