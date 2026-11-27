from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import Wheel


class LogicSpinWheelOpenedCommand(LogicCommand):
    """Handler for LogicSpinWheelOpenedCommand."""

    NAME = "LogicSpinWheelOpenedCommand"
    TYPE = 83
    ACTION = "wheel_open"
    FIELDS = ['int', 'tick']

    def execute(self, state):
        entry = Wheel.ensure(state.home.data, state.account.exp_level)
        if entry is None:
            state.save()
            return False
        Wheel.ensure_day(entry, self.f0, state.account.exp_level)
        Wheel.open_wheel(entry)
        state.save()
        return True
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
