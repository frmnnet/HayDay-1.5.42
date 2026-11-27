from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand


class LogicSelectItemToBuyFromBoyCommand(LogicCommand):
    """Handler for LogicSelectItemToBuyFromBoyCommand."""

    NAME = "LogicSelectItemToBuyFromBoyCommand"
    TYPE = 70
    ACTION = "boy_select"
    FIELDS = ['int', 'tick']

    def execute(self, state):
        return super().execute(state)
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
