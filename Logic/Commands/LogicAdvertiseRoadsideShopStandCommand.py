from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Utils.Logging import logger
from Logic import Achievements, RoadsideStand


class LogicAdvertiseRoadsideShopStandCommand(LogicCommand):
    """Handler for LogicAdvertiseRoadsideShopStandCommand."""

    NAME = "LogicAdvertiseRoadsideShopStandCommand"
    TYPE = 36
    FIELDS = ['int', 'tick']

    def execute(self, state):
        slot = int(self.f0)
        stand = RoadsideStand.stand_at(
            state.home.data, slot, state.account.exp_level)
        if stand is None or not RoadsideStand.is_on_sale(stand):
            return False
        if not RoadsideStand.advertise(
                state.home.data, slot, state.account.exp_level):
            return False
        Achievements.record(state, "PlaceNewspaperAd", amount=1)
        state.save()
        logger.info("[CMD] advertised roadside stand slot {}".format(slot))
        return True
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
