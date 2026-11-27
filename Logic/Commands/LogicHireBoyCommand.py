from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand


class LogicHireBoyCommand(LogicCommand):
    """Handler for LogicHireBoyCommand."""

    NAME = "LogicHireBoyCommand"
    TYPE = 68
    ACTION = "boy_hire"
    FIELDS = ['int', 'tick']

    def execute(self, state):
        return super().execute(state)
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
