from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import Wheel
from Utils.Logging import logger


class LogicBuyWheelSpinWithDiamondsCommand(LogicCommand):
    """Handler for LogicBuyWheelSpinWithDiamondsCommand."""

    NAME = "LogicBuyWheelSpinWithDiamondsCommand"
    TYPE = 82
    ACTION = "wheel_spin"
    FIELDS = ['tick']

    def execute(self, state):
        entry = Wheel.ensure(state.home.data, state.account.exp_level)
        if entry is None:
            state.save()
            return False
        cost = Wheel.buy_spin(entry)
        if not self.spend_diamonds(state, cost):
            state.save()
            return False
        Wheel.record_bought_spin(entry)
        logger.info("[CMD] bought wheel spin for {} diamonds".format(cost))
        state.save()
        return True
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
