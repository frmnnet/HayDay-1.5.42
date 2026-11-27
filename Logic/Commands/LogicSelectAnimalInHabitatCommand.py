from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand


class LogicSelectAnimalInHabitatCommand(LogicCommand):
    """Handler for LogicSelectAnimalInHabitatCommand."""

    NAME = "LogicSelectAnimalInHabitatCommand"
    TYPE = 21
    ACTION = "animal_select"
    FIELDS = ['int', 'int', 'tick']

    def execute(self, state):
        return super().execute(state)
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
