from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import MysteryBoxes


class LogicOpenMysteryBoxCommand(LogicCommand):
    """Handler for LogicOpenMysteryBoxCommand."""

    NAME = "LogicOpenMysteryBoxCommand"
    TYPE = 44
    FIELDS = ['int', 'tick']

    def execute(self, state):
        return MysteryBoxes.open_box(self, state)
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
