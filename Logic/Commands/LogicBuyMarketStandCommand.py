from Utils.Logging import logger
from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import RoadsideStand

# roadside_shop.csv, table 35, instance 0 -> 35 * 100000 + 0.  The client
# splits an object id into class = id / 100000 and instance = id % 100000, so
# the missing zero used to decode to class 3 instance 50000 and abort the
# game while loading home ("Unable to load object 350000 class:3
# instance:50000").  ROADSIDE_SHOP_ID now lives in Logic.Home so the state
# helpers and this command cannot drift apart again.


class LogicBuyMarketStandCommand(LogicCommand):
    """Buy a roadside shop stand (no payload fields).

    The diamond price comes from ``game_config.csv``
    (``RoadsideShopStandDiamondPrice``).
    """

    NAME = "LogicBuyMarketStandCommand"
    TYPE = 30
    FIELDS = ['tick']

    def execute(self, state):
        if not RoadsideStand.is_unlocked(state.account.exp_level):
            return False
        cost = self.data.config_int("RoadsideShopStandDiamondPrice", 5)
        shop = RoadsideStand.ensure(
            state.home.data, state.account.exp_level)
        stand_count = shop["count"]
        if stand_count >= 500:
            logger.info("[CMD] roadside shop already has 500 stands")
            return False
        if not self.spend_diamonds(state, cost):
            state.save()
            return False
        RoadsideStand.add_resource(
            state.home.data, RoadsideStand.STAND_COUNT_ITEM, 1)
        shop = RoadsideStand.ensure(
            state.home.data, state.account.exp_level)
        logger.info("[CMD] buy roadside stand for {} diamonds".format(cost))
        logger.info("[CMD] roadside stand count {} -> {}".format(
            stand_count, shop["count"]))
        state.save()
        return True

    def decode(self):
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
