from Utils.Logging import logger
from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import Achievements, RoadsideStand


class LogicPutStuffToRoadsideShopStandCommand(LogicCommand):
    """Put items up for sale on the roadside shop stand.

    Wire layout (from ``createAndDecode`` in the client binary)::

        short slot, int data_global_id, short count, int price, bool, tick

    The boolean is stored by the client but its meaning is not used by the
    server yet; the first four fields are enough to reproduce the stand's
    saved state (``Data``/``Count``/``Price``/``Advertised``).
    """

    NAME = "LogicPutStuffToRoadsideShopStandCommand"
    TYPE = 32
    FIELDS = ['short', 'int', 'short', 'int', 'bool', 'tick']

    def execute(self, state):
        slot = self.arg(0, 0)
        item = self.arg(1, 0)
        count = max(1, self.arg(2, 1))
        price = max(0, self.arg(3, 0))
        advertise = bool(self.arg(4, 0))
        row = self.data_row(item)
        if row is None or not RoadsideStand.can_put(state.home.data, item):
            logger.info("[CMD] roadside stand unknown item {}".format(item))
            state.save()
            return False
        max_stack = max(
            1, self.data.config_int("RoadsideShopMaxStackAmount", count))
        if count > max_stack:
            logger.info("[CMD] roadside stand item {} count {} > {}".format(
                item, count, max_stack))
            state.save()
            return False
        maximum = RoadsideStand.max_price(item, count)
        if price <= 0 or (maximum > 0 and price > maximum):
            logger.info("[CMD] roadside stand item {} price {} exceeds max {}"
                        .format(item, price, maximum))
            state.save()
            return False
        stand = RoadsideStand.stand_at(
            state.home.data, slot, state.account.exp_level)
        if stand is None or not RoadsideStand.is_clear(stand):
            state.save()
            return False
        if advertise:
            free = RoadsideStand.free_advertisement_available(
                state.home.data, state.account.exp_level)
            if not free and RoadsideStand.amount(
                    state.home.data, RoadsideStand.AD_PURCHASES_ITEM) <= 0:
                state.save()
                return False
        if not self.take(state, item, count):
            state.save()
            return False
        RoadsideStand.put(
            state.home.data, slot, item, count, price,
            level=state.account.exp_level)
        if advertise and not RoadsideStand.advertise(
                state.home.data, slot, state.account.exp_level):
            state.save()
            return False
        if advertise:
            Achievements.record(state, "PlaceNewspaperAd", amount=1)
        state.save()
        logger.info("[CMD] roadside stand slot {} <- {} x{} total price {}"
                    .format(slot, item, count, price))
        return True

    def decode(self):
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
