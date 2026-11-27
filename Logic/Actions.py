"""Generic, persistent game actions used by the simpler command stubs.

Every action writes into ``state.home.data`` (and the account where relevant),
so progress is persisted by ``GameState.save()`` (a dirty flag) and written out
by ``GameState.flush()``, which ``Main`` calls after every packet.

These are best-effort simulations: exact reward amounts / validation would
need the game's packed CSV tables, but all actions mutate state consistently
and are safe to replay on reconnect.
"""
import time

TUTORIAL_TABLE = 36


def _bucket(state, key, default=None):
    """Get a persistent bucket from home data."""
    if default is None:
        default = {}
    return state.home.data.setdefault(key, default)


def _f(cmd, i=0, default=0):
    """Safe field accessor (f0, f1, ... set by decode_fields)."""
    return getattr(cmd, "f%d" % i, default)


def _record(state, key, entry_id, **fields):
    bucket = _bucket(state, key)
    k = str(entry_id)
    entry = bucket.get(k)
    if not isinstance(entry, dict):
        entry = {}
    bucket[k] = entry
    entry.update(fields)
    entry["LastAction"] = int(time.time())
    return entry


def perform_action(cmd, state):
    """Run a generic action for ``cmd.ACTION``. Returns bool success."""
    action = cmd.ACTION
    now = int(time.time())

    # ---------------------------------------------------------------- #
    # Fields / crops
    # ---------------------------------------------------------------- #
    if action == "field_boost":
        field = state.home.fields.get(_f(cmd))
        field.ready = min(field.ready, now)
        state.home.fields.set(_f(cmd), field)
        return True

    # ---------------------------------------------------------------- #
    # Animals
    # ---------------------------------------------------------------- #
    if action == "animal_buy":
        animal_id = _f(cmd, 1) or _f(cmd)
        row = cmd.data_row(_f(cmd)) or cmd.data_row(animal_id)
        if row is not None and not cmd.require_unlock(state, row):
            return False
        _record(state, "Animals", animal_id, DataId=_f(cmd), Fed=False,
                Produced=False)
        if row is not None:
            return cmd.spend_price(state, row)
        return cmd.spend_cash(state, 100)
    if action == "animal_feed":
        _record(state, "Animals", _f(cmd), Fed=True)
        animal = cmd.data_row(_f(cmd))
        feed = cmd.item_id(animal.s("Feed")) if animal is not None else None
        return cmd.take(state, feed or 100, 1)
    if action == "animal_collect":
        animal = _record(state, "Animals", _f(cmd), Produced=False)
        row = cmd.data_row(_f(cmd))
        product = cmd.item(row.s("Good")) if row is not None else None
        item = product.global_id if product is not None else animal.get("Product", 0)
        cmd.give(state, item, 1)
        exp = product.i("ExpCollect", 2) if product is not None else 2
        if exp:
            cmd.earn_exp(state, exp)
        return True
    if action == "animal_instant":
        animal = cmd.data_row(_f(cmd))
        product = cmd.item(animal.s("Good")) if animal is not None else None
        cost = product.i("InstantComplete", 1) if product is not None else 1
        if not cmd.spend_diamonds(state, cost):
            return False
        _record(state, "Animals", _f(cmd), Ready=now)
        return True
    if action == "animal_select":
        _record(state, "Animals", _f(cmd), Selected=True)
        return True

    # ---------------------------------------------------------------- #
    # Orders (truck / people / boat)
    # ---------------------------------------------------------------- #
    if action == "order_complete":
        order = _record(state, "Orders", _f(cmd), Completed=True)
        cash, exp = cmd.order_reward(state, _f(cmd))
        cash = int(order.get("Cash") or cash)
        exp = int(order.get("Exp") or exp)
        order["Cash"], order["Exp"] = cash, exp
        cmd.earn_cash(state, cash)
        cmd.earn_exp(state, exp)
        return True
    if action == "order_discard":
        _record(state, "Orders", _f(cmd), Discarded=True)
        return True
    if action == "order_speedup":
        level = int(getattr(state.account, "exp_level", 1) or 1)
        level_row = cmd.data.level_row(level)
        price = level_row.i("OrderSpeedUpPrice", 1) if level_row else 1
        if not cmd.spend_diamonds(state, max(1, price)):
            return False
        _record(state, "Orders", _f(cmd), Ready=now)
        return True
    if action == "order_newflag":
        _record(state, "Orders", _f(cmd), New=False)
        return True
    if action == "order_people":
        _record(state, "PeopleOrders", _f(cmd), Completed=True)
        level = int(getattr(state.account, "exp_level", 1) or 1)
        level_row = cmd.data.level_row(level)
        guest = level_row.i("GuestOrderValue", 10) if level_row else 10
        cash, exp = max(1, guest * 2), max(1, guest)
        cmd.earn_cash(state, cash)
        cmd.earn_exp(state, exp)
        return True
    if action == "boat_order":
        level = int(getattr(state.account, "exp_level", 1) or 1)
        level_row = cmd.data.level_row(level)
        low = level_row.i("MinBoatOrderValue", 0) if level_row else 0
        high = level_row.i("MaxBoatOrderValue", 0) if level_row else 0
        cash = (low + high) // 2 if high > low else 200
        _record(state, "Boats", _f(cmd), Completed=True, Cash=cash)
        cmd.earn_cash(state, cash)
        return True
    if action == "boat_crate":
        level = int(getattr(state.account, "exp_level", 1) or 1)
        level_row = cmd.data.level_row(level)
        lo = level_row.i("MinCrateAmountInBoatOrder", 0) if level_row else 0
        hi = level_row.i("MaxCrateAmountInBoatOrder", 0) if level_row else 0
        _record(state, "Boats", _f(cmd, 1) or 0,
                Crates=_f(cmd), MinCrates=lo, MaxCrates=hi)
        return True
    if action == "boat_speedup":
        boat = cmd.data.row(58, 0)  # boats.csv
        cost = boat.i("InstantComplete", 1) if boat else 1
        if not cmd.spend_diamonds(state, max(1, cost)):
            return False
        _bucket(state, "Boats", {})["Ready"] = now
        return True
    if action == "boat_help":
        _record(state, "Boats", _f(cmd), HelpRequested=True)
        return True

    # ---------------------------------------------------------------- #
    # Fruit trees / forests
    # ---------------------------------------------------------------- #
    if action == "fruit_collect":
        tree_state = _record(state, "FruitTrees", _f(cmd), Collected=True)
        tree = cmd.data_row(_f(cmd)) or cmd.data.find(62, tree_state.get("Tree"))
        name = (tree.s("Name") if tree is not None else "") \
            or str(tree_state.get("Tree") or "")
        fruit_name = name[:-4] if name.endswith("Tree") else (
            name[:-4] if name.endswith("Bush") else name)
        fruit = cmd.item(fruit_name)
        amount = tree.i("FruitCount", 1) if tree is not None else 1
        exp = fruit.i("ExpCollect", 1) if fruit is not None else 1
        if fruit is not None:
            cmd.give(state, fruit.global_id, amount)
        else:
            cmd.give(state, tree_state.get("Fruit", 0), amount)
        cmd.earn_exp(state, exp)
        return True
    if action == "fruit_revive":
        tree = cmd.data_row(_f(cmd))
        tool = cmd.item_id(tree.s("Tool")) if tree is not None else None
        if tool is not None and not cmd.take(state, tool, 1):
            return False
        exp = tree.i("ExpClear", 0) if tree is not None else 0
        _record(state, "FruitTrees", _f(cmd), Revived=True, Tool=tool or 0)
        if exp:
            cmd.earn_exp(state, exp)
        return True
    if action == "fruit_destroy":
        bucket = _bucket(state, "FruitTrees")
        bucket.pop(str(_f(cmd)), None)
        return True
    if action == "fruit_instant":
        tree = cmd.data_row(_f(cmd))
        cost = tree.i("InstantComplete", 1) if tree is not None else 1
        if not cmd.spend_diamonds(state, max(1, cost)):
            return False
        _record(state, "FruitTrees", _f(cmd), Ready=now)
        return True
    if action == "forest_collect":
        forest = _record(state, "Forests", _f(cmd), Collected=True)
        cmd.give(state, forest.get("Product", 0), 1)
        row = cmd.data_row(_f(cmd))
        exp = row.i("ExpClear", 0) if row is not None else 0
        if exp:
            cmd.earn_exp(state, exp)
        return True
    if action == "forest_destroy":
        row = cmd.data_row(_f(cmd))
        exp = row.i("ExpClear", 0) if row is not None else 0
        _bucket(state, "Forests").pop(str(_f(cmd)), None)
        if exp:
            cmd.earn_exp(state, exp)
        return True

    # ---------------------------------------------------------------- #
    # Boy / visitors
    # ---------------------------------------------------------------- #
    if action == "boy_call":
        _record(state, "Boy", 1, Active=True)
        return True
    if action == "boy_hire":
        boy = cmd.data.row(70, 0)  # boy.csv
        price = boy.i("HirePrice", 50) if boy else 50
        if not cmd.spend_cash(state, price):
            return False
        _record(state, "Boy", 1, Hired=True, HirePrice=price,
                HireDays=boy.i("HireDays", 1) if boy else 1)
        return True
    if action == "boy_discard":
        _bucket(state, "Boy", {})["Active"] = False
        return True
    if action == "boy_stop":
        _bucket(state, "Boy", {})["Happy"] = False
        return True
    if action == "boy_reject":
        _bucket(state, "Boy", {})["Offer"] = None
        return True
    if action == "boy_search":
        _record(state, "Boy", 1, Searching=_f(cmd))
        return True
    if action == "boy_select":
        _record(state, "Boy", 1, Selected=_f(cmd))
        return True
    if action == "boy_claim":
        boy = cmd.data.row(70, 0)
        count = boy.i("ItemCountMin", 1) if boy else 1
        cmd.give(state, _f(cmd) or 0, max(1, count))
        return True

    # ---------------------------------------------------------------- #
    # Pets
    # ---------------------------------------------------------------- #
    if action == "pet_call":
        _record(state, "Pets", _f(cmd), Active=True)
        return True
    if action == "pet_tap":
        _record(state, "Pets", _f(cmd), Tapped=now)
        return True
    if action == "pet_collect":
        pet = _record(state, "Pets", _f(cmd), Collected=True)
        cmd.give(state, pet.get("Product", 0), 1)
        row = cmd.data_row(_f(cmd))
        if row is not None:
            exp = row.i("Exp", 0)
            if exp:
                cmd.earn_exp(state, exp)
            voucher = cmd.item_id(row.get("Vouchers"))
            if voucher is not None:
                cmd.give(state, voucher, row.i("VoucherCount", 0) or 1)
        return True
    if action == "pet_bowl":
        pet = cmd.data_row(_f(cmd))
        habitat = cmd.data.find(79, pet.s("Habitat")) if pet is not None else None
        feed = cmd.item_id(habitat.s("Feed")) if habitat is not None else None
        amount = habitat.i("FeedAmount", 1) if habitat is not None else 1
        if not cmd.take(state, feed or 100, max(1, amount)):
            return False
        _record(state, "Pets", _f(cmd), Bowl=now, Feed=feed or 100)
        return True

    # ---------------------------------------------------------------- #
    # Buildings / mine / decorations
    # ---------------------------------------------------------------- #
    if action == "building_fix":
        _record(state, "BuildingUpgrades", _f(cmd), Fixed=True)
        return True
    if action == "building_exp":
        exp = cmd.data.config_int("BuildingFixExp", 10)
        cmd.earn_exp(state, max(1, exp))
        return True
    if action == "mine_use":
        mine = cmd.data_row(_f(cmd)) or cmd.data.row(63, 1)  # repaired mine
        ores = [r for r in cmd.data.rows(64) if r.i("Probability", 0) > 0]
        count = mine.i("NumOres", 1) if mine is not None else 1
        product = None
        if ores:
            total = sum(r.i("Probability", 0) for r in ores)
            pick = int(_f(cmd)) % total
            for ore in ores:
                pick -= ore.i("Probability", 0)
                if pick < 0:
                    product = ore
                    break
        item = product.global_id if product else _f(cmd)
        record = _record(state, "MineProducts", _f(cmd),
                         Product=item, Collected=True)
        cmd.give(state, item, max(1, count))
        exp = product.i("ExpCollect", 0) if product else 0
        if exp:
            cmd.earn_exp(state, exp)
        return True

    # ---------------------------------------------------------------- #
    # Spin wheel / movie tickets
    # ---------------------------------------------------------------- #
    if action.startswith("wheel_"):
        w = _bucket(state, "SpinWheel", {"Spins": 0})
        if action == "wheel_spin":
            # LogicBuyWheelSpinWithDiamondsCommand::getCurrentDiamondPrice:
            # (spins bought today + 1) * WheelSpinPriceMultiplier.
            wheel = cmd.data.row(74, 0)
            multiplier = wheel.i("WheelSpinPriceMultiplier", 1) if wheel else 1
            today = int(w.get("SpinsToday", 0) or 0)
            cost = (today + 1) * max(1, multiplier)
            if not cmd.spend_diamonds(state, cost):
                return False
            w["SpinsToday"] = today + 1
            w["Spins"] = w.get("Spins", 0) + 1
            w["LastCost"] = cost
        elif action == "wheel_open":
            w["open"] = True
        elif action == "wheel_closed":
            w["open"] = False
        elif action == "wheel_end":
            w["ended"] = True
        return True
    if action.startswith("movie_"):
        ticket = cmd.data.row(73, 0)  # movie_tickets.csv
        t = _bucket(state, "MovieTickets", {})
        if action == "movie_pre":
            t["pre_reward"] = True
            exp = ticket.i("PreExpReward", 0) if ticket else 0
            diamonds = ticket.i("PreDiamondReward", 0) if ticket else 0
            if exp:
                cmd.earn_exp(state, exp)
            if diamonds:
                cmd.earn_diamonds(state, diamonds)
        elif action == "movie_finished":
            t["final_reward"] = True
            exp = ticket.i("FinishedExpReward", 0) if ticket else 0
            diamonds = ticket.i("FinishedDiamondReward", 0) if ticket else 0
            if exp:
                cmd.earn_exp(state, exp)
            if diamonds:
                cmd.earn_diamonds(state, diamonds)
        elif action == "movie_discard":
            t["ticket"] = 0
        return True

    # ---------------------------------------------------------------- #
    # Misc client / social / meta actions (no gameplay effect, but tracked)
    # ---------------------------------------------------------------- #
    if action in ("app_rate", "facebook", "fb_popup", "offer_purchased",
                  "secure", "debug", "ad_click", "advertisement_speedup",
                  "ambient_spawn", "ambient_tap", "mirror", "store_object",
                  "animal_panic", "ignore_popup"):
        record = _record(state, "ClientEvents", cmd.NAME, value=_f(cmd))
        if action in ("facebook", "fb_popup") and not record.get("rewarded"):
            reward = cmd.data.config_int("FacebookLoginDiamondReward", 5)
            if reward:
                cmd.earn_diamonds(state, reward)
            record["rewarded"] = True
        if action == "advertisement_speedup":
            life = cmd.data.config_int("RoadsideShopStandAdvertisementLifeMinutes", 180)
            cooldown = cmd.data.config_int(
                "RoadSideShopStandAdvertisementCooldownMinutes", 30)
            record["life_minutes"] = life
            record["cooldown_minutes"] = cooldown
        return True

    logger.info("[CMD] no generic action for %s (ACTION=%s)" % (cmd.NAME, action))
    return False
