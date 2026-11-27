from Utils.Logging import logger
from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import RoadsideStand


class LogicSpeedUpAdvertisementCommand(LogicCommand):
    """Buy one newspaper advertisement token with diamonds."""

    NAME = "LogicSpeedUpAdvertisementCommand"
    TYPE = 52
    FIELDS = ['tick']

    def execute(self, state):
        if not RoadsideStand.buy_advertisement(
                state.home.data, state.account.exp_level):
            logger.info(
                "[CMD] advertisement purchase unavailable (free ad ready "
                "or token already owned)")
            return False
        cost = max(1, self.data.config_int(
            "RoadsideShopStandAdvertisementDiamondPrice", 1))
        if not self.spend_diamonds(state, cost):
            RoadsideStand.take_resource(
                state.home.data, RoadsideStand.AD_PURCHASES_ITEM, 1)
            return False
        state.save()
        logger.info(
            "[CMD] bought advertisement token for {} diamonds".format(cost))
        return True

    def decode(self):
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
