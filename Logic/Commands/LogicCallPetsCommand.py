from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand


class LogicCallPetsCommand(LogicCommand):
    """Handler for LogicCallPetsCommand."""

    NAME = "LogicCallPetsCommand"
    TYPE = 89
    ACTION = "pet_call"
    FIELDS = ['int', 'tick']

    def execute(self, state):
        return super().execute(state)
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
