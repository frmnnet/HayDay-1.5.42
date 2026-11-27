from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Utils.Logging import logger
from Logic import RoadsideStand


class LogicDiscardRoadsideShopStandCommand(LogicCommand):
    """Handler for LogicDiscardRoadsideShopStandCommand."""

    NAME = "LogicDiscardRoadsideShopStandCommand"
    TYPE = 37
    FIELDS = ['int', 'tick']

    def execute(self, state):
        slot = int(self.f0)
        stand = RoadsideStand.stand_at(
            state.home.data, slot, state.account.exp_level)
        if stand is None or not RoadsideStand.is_on_sale(stand):
            return False
        if RoadsideStand.is_claimed(stand):
            return False
        cost = max(0, self.data.config_int(
            "RoadsideShopDiscardDiamondPrice", 1))
        if cost and not self.spend_diamonds(state, cost):
            return False
        RoadsideStand.clear(
            state.home.data, slot, state.account.exp_level)
        state.save()
        logger.info("[CMD] discarded roadside stand slot {} for {} diamonds"
                    .format(slot, cost))
        return True
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
