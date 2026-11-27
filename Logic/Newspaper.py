"""Newspaper advertisements and cross-farm roadside-shop purchases.

The client never buys directly from the advertisement list.  Selecting an
advertisement first sends ``VisitHomeMessage`` with only the seller id.  The
server answers with that farm (``OtherHomeDataMessage``), and the buy button
then sends the stand slot in that visited home.
"""
import copy
import json
import random
import time
from contextlib import ExitStack
from pathlib import Path

from Logic import RoadsideStand, Storage
from Logic.Device import Device
from Logic.GameData import GameData
from Logic.GameState import GameState
from Utils.Database import Database
from Utils.Logging import logger
from Utils.Storage import load_config


ADS_KEY = "_NewspaperAds"
REFRESH_KEY = "_NewspaperRefreshAt"
SEQUENCE_KEY = "_NewspaperSyntheticSequence"

AI_HOME_PATH = Path(__file__).resolve().parent.parent / "JSON" / "ai.json"
SYNTHETIC_LOW_BASE = 0x70000000
SYNTHETIC_STANDS_PER_SELLER = 5

_AI_DOCUMENT = None


def _price(item_id, amount):
    row = GameData.instance().row_for(item_id)
    if row is None:
        return 0
    unit = 0
    for column in ("OrderValue", "Value", "DumbValue", "OrderPrice"):
        unit = row.i(column, 0)
        if unit > 0:
            break
    return max(1, unit * max(1, int(amount or 1)))


def _ai_document():
    """Read-only template shared by synthetic newspaper farms."""
    global _AI_DOCUMENT
    if _AI_DOCUMENT is None:
        with open(AI_HOME_PATH, "r", encoding="utf-8") as handle:
            document = json.load(handle)
        if not isinstance(document, dict):
            raise ValueError("JSON/ai.json must contain an object")
        _AI_DOCUMENT = document
    return _AI_DOCUMENT


def _synthetic_seller(sequence):
    seller_number, slot = divmod(
        max(0, int(sequence)), SYNTHETIC_STANDS_PER_SELLER)
    return 0, SYNTHETIC_LOW_BASE + seller_number, slot


def _synthetic_offer(sequence):
    table = GameData.instance().named_table("ai_roadside_shop")
    if table is None or not table.rows:
        return None
    weighted = []
    for row in table.rows:
        weighted.extend([row] * max(1, row.i("Probability", 1)))
    source = random.choice(weighted)
    item = GameData.instance().item(source.s("Good"))
    if item is None:
        return None
    amount = max(1, source.i("Amount", 1))
    price = _price(item.global_id, amount)
    seller_high, seller_low, slot = _synthetic_seller(sequence)
    return {
        "SellerHigh": seller_high,
        "SellerLow": seller_low,
        "Slot": slot,
        "Data": item.global_id,
        "Price": price,
        "Count": amount,
        "Synthetic": True,
    }


def _player_ads(state, now):
    db = Database.instance()
    buyer_key = (state.high_id, state.low_id)
    result = []
    for account in db.list_accounts():
        seller_key = (int(account["high_id"]), int(account["low_id"]))
        if seller_key == buyer_key:
            continue
        try:
            raw = db.get_home(*seller_key)
            if not raw:
                continue
            import json
            data = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            continue
        for ad in RoadsideStand.active_ads(
                data, int(account.get("exp_level", 1) or 1), now):
            result.append({
                "SellerHigh": seller_key[0],
                "SellerLow": seller_key[1],
                "Slot": ad["slot"],
                "Data": ad["Data"],
                "Price": ad["Price"],
                "Count": ad["Count"],
                "Synthetic": False,
            })
    return result


def _cache_compatible(entries):
    """Reject caches written by the old advertisement-index implementation."""
    if not isinstance(entries, list):
        return False
    for entry in entries:
        if not isinstance(entry, dict):
            return False
        try:
            if int(entry.get("Slot")) < 0:
                return False
            if entry.get("Synthetic"):
                if int(entry.get("SellerLow") or 0) < SYNTHETIC_LOW_BASE:
                    return False
        except (TypeError, ValueError):
            return False
    return True


def refresh(state, required_count=None, now=None, force=False):
    """Return and persist the advertisement list for this player."""
    now = int(time.time()) if now is None else int(now)
    try:
        required_count = max(1, int(required_count or 20))
    except (TypeError, ValueError):
        required_count = 20
    data = state.home.data
    current = data.get(ADS_KEY)
    refresh_at = int(data.get(REFRESH_KEY, 0) or 0)
    if (not force and _cache_compatible(current)
            and len(current) >= required_count and now < refresh_at):
        return current[:required_count]

    entries = _player_ads(state, now)
    sequence = int(data.get(SEQUENCE_KEY, 0) or 0)
    while len(entries) < required_count:
        offer = _synthetic_offer(sequence)
        sequence += 1
        if offer is None:
            break
        entries.append(offer)
    entries = entries[:required_count]
    data[ADS_KEY] = entries
    data[SEQUENCE_KEY] = sequence
    interval = max(1, GameData.instance().config_int(
        "NewspaperRefreshSeconds", 120))
    data[REFRESH_KEY] = now + interval
    state.save()
    return entries


def _real_seller(high, low):
    key = (int(high), int(low))
    if key == (0, 0):
        return None
    row = Database.instance().get_account(*key)
    if not row:
        return None
    return GameState.for_account(*key)


def _seller_ads(state, high, low):
    ads = state.home.data.get(ADS_KEY)
    if not isinstance(ads, list):
        return []
    result = []
    for ad in ads:
        if not isinstance(ad, dict) or not ad.get("Synthetic"):
            continue
        try:
            if (int(ad.get("SellerHigh") or 0) == int(high)
                    and int(ad.get("SellerLow") or 0) == int(low)):
                result.append(ad)
        except (TypeError, ValueError):
            continue
    return result


def _synthetic_name(high, low):
    base = str(load_config().get("AIName", "Greg"))
    seller_number = max(0, int(low) - SYNTHETIC_LOW_BASE)
    return base if seller_number == 0 else "{} {}".format(
        base, seller_number + 1)


def synthetic_home(ads):
    """Build a complete AI-style farm with the cached offers in its stands."""
    document = _ai_document()
    home = copy.deepcopy(document)
    avatar = home.setdefault("Avatar", {})
    if not isinstance(avatar, dict):
        avatar = {}
        home["Avatar"] = avatar
    roadside = avatar.setdefault("roadside_shop", {})
    if not isinstance(roadside, dict):
        roadside = {}
        avatar["roadside_shop"] = roadside
    stands = roadside.setdefault("Stands", [])
    if not isinstance(stands, list):
        stands = []
        roadside["Stands"] = stands

    required_stands = max(len(stands), SYNTHETIC_STANDS_PER_SELLER)
    for ad in ads:
        try:
            required_stands = max(
                required_stands, int(ad.get("Slot") or 0) + 1)
        except (TypeError, ValueError):
            continue
    while len(stands) < required_stands:
        stands.append({
            "Data": 0,
            "Price": 0,
            "Count": 0,
            "Advertised": False,
        })

    for ad in ads:
        try:
            slot = int(ad.get("Slot"))
        except (TypeError, ValueError):
            continue
        if slot < 0 or slot >= len(stands):
            continue
        stand = stands[slot]
        if not isinstance(stand, dict):
            stand = {}
            stands[slot] = stand
        stand.clear()
        stand.update({
            "Data": int(ad.get("Data") or 0),
            "Price": int(ad.get("Price") or 0),
            "Count": int(ad.get("Count") or 0),
            "Advertised": True,
        })

    building = next((
        entry for entry in home.setdefault("Objects", [])
        if isinstance(entry, dict)
        and entry.get("ID") == RoadsideStand.SHOP_ID
    ), None)
    if building is None:
        building = {
            "ID": RoadsideStand.SHOP_ID,
            "X": RoadsideStand.SPAWN_X,
            "Y": RoadsideStand.SPAWN_Y,
        }
        home["Objects"].append(building)
    ai_timers = building.get("AITimer")
    if not isinstance(ai_timers, list):
        ai_timers = []
        building["AITimer"] = ai_timers
    ad_timers = building.get("AdTimers")
    if not isinstance(ad_timers, list):
        ad_timers = []
        building["AdTimers"] = ad_timers
    del ai_timers[len(stands):]
    del ad_timers[len(stands):]
    ai_timers.extend([0] * (len(stands) - len(ai_timers)))
    ad_timers.extend([0] * (len(stands) - len(ad_timers)))
    return json.dumps(home, ensure_ascii=False, separators=(",", ":"))


def synthetic_avatar():
    """Template consumed by ``Logic.AIAvatar.encode`` for fake sellers."""
    avatar = _ai_document().get("Avatar")
    return avatar if isinstance(avatar, dict) else {}


def visit_home(state, seller_high, seller_low, now=None):
    """Resolve a real or synthetic seller home for ``VisitHomeMessage``."""
    high, low = int(seller_high), int(seller_low)
    seller = _real_seller(high, low)
    if seller is not None:
        return {
            "High": high,
            "Low": low,
            "Name": seller.account.name,
            "State": seller,
            "Ads": None,
        }
    with state.lock:
        ads = _seller_ads(state, high, low)
    if not ads:
        return None
    return {
        "High": high,
        "Low": low,
        "Name": _synthetic_name(high, low),
        "State": None,
        "Ads": [dict(ad) for ad in ads],
    }


def _response(code, stand, data_id, amount, price, seller_high=0,
              seller_low=0, buyer_high=0, buyer_low=0):
    return {
        "Response": code,
        "Data": data_id,
        "Price": price,
        "Amount": amount,
        "Stand": stand,
        "SellerHigh": seller_high,
        "SellerLow": seller_low,
        "BuyerHigh": buyer_high,
        "BuyerLow": buyer_low,
        "DiamondPrice": 0,
    }


def _validate(ad, data_id, amount, price):
    return (
        ad is not None
        and int(ad.get("Data") or 0) == int(data_id)
        and int(ad.get("Count") or 0) == int(amount)
        and int(ad.get("Price") or 0) == int(price)
        and int(data_id or 0) > 0
        and int(amount or 0) > 0
        and int(price or 0) > 0
    )


def buy(state, seller_high, seller_low, stand_index, data_id, amount, price,
        hybrid=False, now=None):
    """Buy the advertisement for one stand in the currently visited home.

    Returns ``(success, response_fields)``.  The buyer pays the advertised
    total price now; a real seller's stand is marked with the buyer and paid
    out when that seller uses ``LogicClaimRoadsideShopStandCommand``.
    """
    now = int(time.time()) if now is None else int(now)
    try:
        seller_high = int(seller_high)
        seller_low = int(seller_low)
        stand_index = int(stand_index)
    except (TypeError, ValueError):
        return False, _response(1, -1, data_id, amount, price)
    seller_key = (seller_high, seller_low)
    if seller_key == state.key:
        return False, _response(
            3, stand_index, data_id, amount, price, seller_high, seller_low)

    seller = _real_seller(seller_high, seller_low)
    states = {state.key: state}
    if seller is not None:
        states[seller.key] = seller
    with ExitStack() as stack:
        for key in sorted(states):
            stack.enter_context(states[key].lock)
        success, response = _buy_locked(
            state, seller, seller_high, seller_low, stand_index,
            data_id, amount, price, hybrid, now)
    if success and seller is not None:
        _notify_sale(
            seller_high, seller_low, stand_index, data_id, amount, price)
    return success, response


def _notify_sale(seller_high, seller_low, stand_index, data_id, amount,
                 price):
    from Packets.Messages.Server.NotifyOnSaleMessage import (
        NotifyOnSaleMessage,
    )
    for device in Device.online_for_account(seller_high, seller_low):
        try:
            NotifyOnSaleMessage.from_sale(
                device, seller_high, seller_low, stand_index,
                amount, price, data_id).Send()
        except Exception:
            logger.exception(
                "[NEWSPAPER] could not notify seller {}:{}".format(
                    seller_high, seller_low))


def _buy_locked(state, seller, seller_high, seller_low, stand_index,
                data_id, amount, price, hybrid, now):
    ads = state.home.data.get(ADS_KEY)
    if not isinstance(ads, list):
        return False, _response(
            1, stand_index, data_id, amount, price, seller_high, seller_low)
    ad_index = None
    ad = None
    for index, candidate in enumerate(ads):
        if not isinstance(candidate, dict):
            continue
        try:
            same_seller = (
                int(candidate.get("SellerHigh") or 0) == seller_high
                and int(candidate.get("SellerLow") or 0) == seller_low
                and int(candidate.get("Slot")) == stand_index)
            same_kind = bool(candidate.get("Synthetic")) == (seller is None)
        except (TypeError, ValueError):
            continue
        if same_seller and same_kind:
            ad_index = index
            ad = candidate
            break
    if ad is None:
        return False, _response(
            1, stand_index, data_id, amount, price, seller_high, seller_low)
    if not _validate(ad, data_id, amount, price):
        logger.info(
            "[NEWSPAPER] verification mismatch seller {}:{} stand {}"
            .format(seller_high, seller_low, stand_index))
        return False, _response(
            2, stand_index, data_id, amount, price, seller_high, seller_low)
    if not Storage.can_store(state.home.data, data_id, amount):
        return False, _response(
            4, stand_index, data_id, amount, price, seller_high, seller_low)
    if not state.account_spend("cash", price):
        return False, _response(
            5, stand_index, data_id, amount, price, seller_high, seller_low)

    if seller is not None:
        stand = RoadsideStand.stand_at(
            seller.home.data, stand_index, seller.account.exp_level, now)
        if (stand is None or RoadsideStand.is_claimed(stand)
                or not stand.get("Advertised")
                or int(stand.get("Data") or 0) != int(data_id)
                or int(stand.get("Count") or 0) != int(amount)
                or int(stand.get("Price") or 0) != int(price)):
            state.account_delta(cash=price)
            state.account_stat("cash_earned", price)
            return False, _response(
                6, stand_index, data_id, amount, price,
                seller_high, seller_low)
        RoadsideStand.set_buyer(
            seller.home.data, stand_index,
            state.high_id, state.low_id, seller.account.exp_level, now)
        seller.save()

    state.account_stat("cash_spent", price)
    Storage.store(
        state.home.data, state.home.inventory, data_id, amount)
    ads.pop(ad_index)
    sequence = int(state.home.data.get(SEQUENCE_KEY, 0) or 0)
    replacement = _synthetic_offer(sequence)
    if replacement is not None:
        ads.insert(ad_index, replacement)
        state.home.data[SEQUENCE_KEY] = sequence + 1
    state.save()
    if seller is not None:
        seller.flush()
    state.flush()
    logger.info(
        "[NEWSPAPER] buy seller {}:{} stand {} -> {} x{} for {}".format(
            seller_high, seller_low, stand_index,
            data_id, amount, price))
    return True, _response(
        0, stand_index, data_id, amount, price,
        seller_high, seller_low, state.high_id, state.low_id)
