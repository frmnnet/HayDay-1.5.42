from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import Achievements


class LogicDiscardBoatOrderCommand(LogicCommand):
    """Handler for LogicDiscardBoatOrderCommand."""

    NAME = "LogicDiscardBoatOrderCommand"
    TYPE = 57
    ACTION = "order_discard"
    FIELDS = ['tick']

    def execute(self, state):
        result = super().execute(state)
        if result:
            Achievements.set_progress(state, "CompleteConsecutiveBoatOrders", 0)
        return result
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
