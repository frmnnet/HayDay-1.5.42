"""Truck order lifecycle and event journal."""
import time

from Logic.GameTime import seconds_to_ticks
from Logic.GameData import TABLE_IDS

MAX_EVENTS = 100
ORDER_TABLE_ID = TABLE_IDS["order_tables"] * 100000
CAR_ID = TABLE_IDS["cars"] * 100000
ORDER_SLOTS = 9
ORDER_TABLE_POSITION = (14, 19)
CAR_POSITION = (17, 21)


def _orders(data):
    orders = data.setdefault("Orders", {})
    if not isinstance(orders, dict):
        orders = {}
        data["Orders"] = orders
    return orders


def _events(data):
    events = data.setdefault("TruckEvents", [])
    if not isinstance(events, list):
        events = []
        data["TruckEvents"] = events
    return events


def _find_object(data, data_id):
    for entry in data.setdefault("Objects", []):
        if not isinstance(entry, dict):
            continue
        try:
            if int(entry.get("ID")) == int(data_id):
                return entry
        except (TypeError, ValueError):
            continue
    return None


def ensure_client_objects(data):
    """Ensure the order board and truck exist in the serialized home.

    Both are level ``SpecialObjects``.  A home received without their dynamic
    state makes the client rebuild them from defaults, which is why completed
    orders and the returning truck disappeared after Visit Other Home.
    """
    table = _find_object(data, ORDER_TABLE_ID)
    if table is None:
        x, y = ORDER_TABLE_POSITION
        table = {"ID": ORDER_TABLE_ID, "X": x, "Y": y, "Orders": []}
        data["Objects"].append(table)
    elif not isinstance(table.get("Orders"), list):
        table["Orders"] = []

    car = _find_object(data, CAR_ID)
    if car is None:
        x, y = CAR_POSITION
        car = {"ID": CAR_ID, "X": x, "Y": y, "State": 1}
        data["Objects"].append(car)
    return table, car


def _order_slot(data, slot, level=1):
    table, _car = ensure_client_objects(data)
    orders = table["Orders"]
    slot = int(slot)
    while len(orders) <= slot:
        orders.append({"Lvl": max(1, int(level))})
    order = orders[slot]
    if not isinstance(order, dict):
        order = {"Lvl": max(1, int(level))}
        orders[slot] = order
    return order


def _finish_order(data, slot, level=1, cooldown_seconds=0, now=None):
    """Serialize the exact ``LogicOrder::save`` empty/cooldown shape."""
    now = int(time.time()) if now is None else int(now)
    order = _order_slot(data, slot, level)
    order.clear()
    order["Lvl"] = max(1, int(level))
    seconds = max(0, int(cooldown_seconds or 0))
    order["Timer"] = {
        "StartSeconds": seconds,
        "TicksLeft": seconds_to_ticks(seconds),
    }
    return order


def _set_car_reward(data, cash=0, exp=0, bonus_cash=0, bonus_exp=0,
                    item_global_id=0):
    """Write the fields consumed by ``LogicCar::load``.

    ``LogicCar::save`` persists in-memory state 2 as JSON state 3.  State 3
    is therefore the returning/reward-collectable state after a home reload.
    """
    _table, car = ensure_client_objects(data)
    x, y = CAR_POSITION
    for key in ("Cash", "Exp", "BonusCash", "BonusExp", "ItemGlobalID"):
        car.pop(key, None)
    if int(cash):
        car["Cash"] = int(cash)
    if int(exp):
        car["Exp"] = int(exp)
    if int(bonus_cash):
        car["BonusCash"] = int(bonus_cash)
    if int(bonus_exp):
        car["BonusExp"] = int(bonus_exp)
    if int(item_global_id):
        car["ItemGlobalID"] = int(item_global_id)
    car["X"] = x
    car["Y"] = y
    car["State"] = 3
    return car


def _reset_car(data):
    _table, car = ensure_client_objects(data)
    for key in ("Cash", "Exp", "BonusCash", "BonusExp", "ItemGlobalID"):
        car.pop(key, None)
    x, y = CAR_POSITION
    car["X"] = x
    car["Y"] = y
    car["State"] = 1
    return car


def record(data, slot):
    return _orders(data).setdefault(str(int(slot)), {})


def add_event(data, name, slot, **fields):
    events = _events(data)
    event = {
        "Event": name,
        "Order": int(slot),
        "Time": int(time.time()),
    }
    event.update(fields)
    events.append(event)
    if len(events) > MAX_EVENTS:
        del events[:-MAX_EVENTS]
    return event


def pending_reward(data):
    reward = data.get("CarReward")
    return reward if isinstance(reward, dict) else None


def take_pending_reward(data):
    reward = pending_reward(data)
    data.pop("CarReward", None)
    return reward


def grant_reward(command, state, reward):
    """Apply one collected car reward through LogicCommand helpers."""
    if not isinstance(reward, dict):
        return
    cash = int(reward.get("cash") or 0)
    exp = int(reward.get("exp") or 0)
    voucher = int(reward.get("voucher") or 0)
    if cash:
        command.earn_cash(state, cash)
    if exp:
        command.earn_exp(state, exp)
    if voucher:
        item = command.data.gid(19, "Voucher") or 1900052
        command.give(state, item, voucher)


def complete(data, slot, cash, exp, voucher=0, now=None, level=1):
    now = int(time.time()) if now is None else int(now)
    slot = int(slot)
    entry = record(data, slot)
    entry.update({
        "State": "returning",
        "Completed": True,
        "Collected": False,
        "Cash": int(cash),
        "Exp": int(exp),
        "Voucher": int(voucher),
        "CompletedAt": now,
        "Ready": now,
    })
    reward = {
        "order": slot,
        "cash": int(cash),
        "exp": int(exp),
        "voucher": int(voucher),
        "ready": now,
    }
    data["CarReward"] = reward
    _finish_order(data, slot, level=level)
    _set_car_reward(
        data, cash=int(cash), exp=int(exp), item_global_id=int(voucher))
    add_event(
        data, "OrderCompleted", slot, Cash=int(cash), Exp=int(exp))
    return reward


def collect(data, slot=None, now=None):
    reward = take_pending_reward(data)
    if reward is None:
        return None
    if slot is not None and int(reward.get("order", -1)) != int(slot):
        data["CarReward"] = reward
        return None
    slot = int(reward.get("order", 0))
    entry = record(data, slot)
    entry.update({
        "State": "collected",
        "Completed": True,
        "Collected": True,
        "CollectedAt": int(time.time()) if now is None else int(now),
    })
    _reset_car(data)
    add_event(
        data, "CarRewarded", slot,
        Cash=int(reward.get("cash") or 0),
        Exp=int(reward.get("exp") or 0),
        Voucher=int(reward.get("voucher") or 0),
    )
    return reward


def discard(data, slot, cooldown_seconds=0, now=None):
    now = int(time.time()) if now is None else int(now)
    slot = int(slot)
    entry = record(data, slot)
    entry.update({
        "State": "discarded",
        "Discarded": True,
        "DiscardedAt": now,
        "Ready": now + max(0, int(cooldown_seconds)),
    })
    _finish_order(
        data, slot, cooldown_seconds=max(0, int(cooldown_seconds)), now=now)
    reward = pending_reward(data)
    if reward is not None and int(reward.get("order", -1)) == slot:
        data.pop("CarReward", None)
    add_event(data, "OrderDiscarded", slot)
    return entry


def speed_up(data, slot, now=None):
    now = int(time.time()) if now is None else int(now)
    slot = int(slot)
    entry = record(data, slot)
    entry["Ready"] = now
    entry["SpeededUp"] = True
    _finish_order(data, slot, now=now)
    reward = pending_reward(data)
    if reward is not None and int(reward.get("order", -1)) == slot:
        reward["ready"] = now
    add_event(data, "OrderSpeedUp", slot)
    return entry


def clear_new_flags(data):
    for entry in _orders(data).values():
        if isinstance(entry, dict):
            entry["New"] = False
    table, _car = ensure_client_objects(data)
    for entry in table.get("Orders", []):
        if isinstance(entry, dict):
            entry.pop("New", None)
    add_event(data, "OrdersViewed", -1)


def normalize(data):
    """Repair legacy reward rows and mirror them into client object state."""
    ensure_client_objects(data)
    reward = pending_reward(data)
    if reward is None:
        car = _find_object(data, CAR_ID)
        if car is not None and int(car.get("State", 1) or 1) == 3:
            _reset_car(data)
        return
    slot = reward.get("order", 0)
    entry = _orders(data).get(str(slot))
    if isinstance(entry, dict) and entry.get("Collected"):
        data.pop("CarReward", None)
        _reset_car(data)
        return
    _set_car_reward(
        data,
        cash=int(reward.get("cash") or 0),
        exp=int(reward.get("exp") or 0),
        item_global_id=int(reward.get("voucher") or 0),
    )
