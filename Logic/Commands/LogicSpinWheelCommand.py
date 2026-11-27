from Utils.Logging import logger
from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import Wheel


class LogicSpinWheelCommand(LogicCommand):
    """Store the client's wheel result until ``SpinWheelEnded``."""

    NAME = "LogicSpinWheelCommand"
    TYPE = 79
    FIELDS = ['int', 'int', 'int', 'int', 'int', 'tick']

    def execute(self, state):
        entry = Wheel.ensure(state.home.data, state.account.exp_level)
        if entry is not None:
            Wheel.ensure_day(entry, self.f0, state.account.exp_level)
        if entry is None or not Wheel.prepare_spin(
                entry, self.f0, self.f1, self.f2, self.f3, self.f4):
            logger.info(
                "[CMD] wheel spin rejected: type={} data={} count={}".format(
                    self.f1, self.f2, self.f3))
            state.save()
            return False
        logger.info("[CMD] wheel pending: type={} data={} count={}".format(
            self.f1, self.f2, self.f3))
        state.save()
        return True
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
