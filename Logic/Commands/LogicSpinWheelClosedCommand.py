from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import Wheel


class LogicSpinWheelClosedCommand(LogicCommand):
    """Handler for LogicSpinWheelClosedCommand."""

    NAME = "LogicSpinWheelClosedCommand"
    TYPE = 81
    ACTION = "wheel_closed"
    FIELDS = ['tick']

    def execute(self, state):
        entry = Wheel.ensure(state.home.data, state.account.exp_level)
        if entry is None:
            state.save()
            return False
        Wheel.close_wheel(entry)
        state.save()
        return True
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
