"""Greg's roadside-shop offers backed by ``ai_roadside_shop.csv``."""
import random

from Logic.GameData import GameData

KEY = "AIRoadsideShopOffers"
DEFAULT_SLOTS = 6


def _price(row):
    if row is None:
        return 0
    for column in ("Value", "OrderValue", "DumbValue", "OrderPrice"):
        value = row.i(column, 0)
        if value > 0:
            return value
    return 0


def _random_offer():
    game_data = GameData.instance()
    table = game_data.named_table("ai_roadside_shop")
    if table is None or not table.rows:
        return None
    weighted = []
    for row in table.rows:
        weighted.extend([row] * max(1, row.i("Probability", 1)))
    source = random.choice(weighted)
    item = game_data.item(source.s("Good"))
    if item is None:
        return None
    return {
        "Data": item.global_id,
        "Name": item.name,
        "Amount": max(1, source.i("Amount", 1)),
        "Price": _price(item),
    }


def offers(data, create=False):
    values = data.setdefault(KEY, [])
    if not isinstance(values, list):
        values = []
        data[KEY] = values
    if create:
        while len(values) < DEFAULT_SLOTS:
            offer = _random_offer()
            if offer is None:
                break
            values.append(offer)
    return values


def offer_at(data, slot):
    slot = int(slot)
    values = offers(data, create=True)
    if slot < 0 or slot >= len(values):
        return None
    offer = values[slot]
    return offer if isinstance(offer, dict) and offer else None


def replace_offer(data, slot):
    slot = int(slot)
    values = offers(data, create=True)
    if slot < 0 or slot >= len(values):
        return
    values[slot] = _random_offer() or {}
