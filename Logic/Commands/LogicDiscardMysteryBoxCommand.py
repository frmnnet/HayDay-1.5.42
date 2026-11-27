from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import MysteryBoxes


class LogicDiscardMysteryBoxCommand(LogicCommand):
    """Handler for LogicDiscardMysteryBoxCommand."""

    NAME = "LogicDiscardMysteryBoxCommand"
    TYPE = 45
    FIELDS = ['int', 'tick']

    def execute(self, state):
        return MysteryBoxes.discard(self, state)
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
