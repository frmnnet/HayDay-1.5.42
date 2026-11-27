from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand


class LogicTapAmbientAnimalCommand(LogicCommand):
    """Handler for LogicTapAmbientAnimalCommand."""

    NAME = "LogicTapAmbientAnimalCommand"
    TYPE = 42
    ACTION = "ambient_tap"
    FIELDS = ['int', 'tick']

    def execute(self, state):
        return super().execute(state)
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
