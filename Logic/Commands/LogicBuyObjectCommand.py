from Utils.Reader import Reader
from Utils.Logging import logger
from Logic.Commands.LogicCommand import LogicCommand
from Logic import Achievements, FruitTrees, HomeBuildings


class LogicBuyObjectCommand(LogicCommand):
    """Buy an object (f0=data id, f1=object id, f2/f3=1/512 tile pos, f4=bool).

    Price and the exp granted on purchase are read from the object's CSV
    row (``Price``/``PriceIncrease``/``DiamondPrice``/``BuyExp``), following
    ``LogicBuyObjectCommand::execute`` in the client.

    ``f2``/``f3`` are *accurate* coordinates.  The saved tile uses the
    client's ASRS #9 conversion, equivalent to Python's ``value >> 9``.
    Storing the raw values produces objects outside the tilemap.
    """

    NAME = "LogicBuyObjectCommand"
    TYPE = 4
    FIELDS = ['int', 'int', 'int', 'int', 'bool', 'tick']

    def execute(self, state):
        data_id = self.f0
        row = self.data_row(data_id)

        # Never place an object with an invalid data id: the client throws
        # "Unable to load object -1 class:0 instance:-1" while loading home.
        if row is None:
            logger.info("[CMD] buy object {}: unknown data id, ignored".format(
                data_id))
            state.save()
            return False
        if "CanBuy" in row.values and not row.b("CanBuy", True):
            logger.info("[CMD] buy object {}: row is not purchasable".format(
                data_id))
            state.save()
            return False
        if not self.require_unlock(state, row):
            state.save()
            return False
        if data_id // 100000 == 6 and HomeBuildings.construction_id_for(
                data_id) is None:
            logger.info("[CMD] buy object {}: no construction site".format(
                data_id))
            state.save()
            return False

        objects = state.home.data.get("Objects", [])
        owned = sum(1 for o in objects
                    if o.get("ID") == data_id or str(o.get("ID")) == str(data_id))
        currency, price = self.data.shop_price(row, count=owned)
        if not self.spend_price(state, row, count=owned):
            state.save()
            return False
        if int(data_id) // 100000 in (3, 48):
            if currency == "cash" and price > 0:
                Achievements.record(state, "DecosWorth", amount=price)
        buy_exp = row.i("BuyExp", 0)
        if buy_exp:
            self.earn_exp(state, buy_exp)

        if data_id // 100000 == 6:
            HomeBuildings.place(
                state.home.data, data_id, self.f2, self.f3,
                total_seconds=row.seconds() or 1, mirrored=bool(self.f4),
                now=self.now)
            logger.info("[CMD] start construction {} at {:.1f},{:.1f}".format(
                data_id, int(self.f2) >> 9, int(self.f3) >> 9))
            state.save()
            return True

        # The placed object must be the *data* id, never f1 (a game object
        # id that changes every session).
        entry = {"ID": data_id,
                 "X": int(self.f2) >> 9,
                 "Y": int(self.f3) >> 9,
                 "_AccurateX": int(self.f2),
                 "_AccurateY": int(self.f3),
                 "_PendingRuntime": True}
        if self.f4:
            entry["Mirrored"] = True
        objects.append(entry)
        state.home.data["Objects"] = objects
        if row.tid == FruitTrees.TREE_TYPE:
            FruitTrees.start_growth_entry(
                entry, row, now=self.now, phase=1)
        state.save()
        return True

    def decode(self):
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
