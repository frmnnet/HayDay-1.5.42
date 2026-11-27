from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand


class LogicSpawnAmbientAnimalCommand(LogicCommand):
    """Handler for LogicSpawnAmbientAnimalCommand."""

    NAME = "LogicSpawnAmbientAnimalCommand"
    TYPE = 50
    ACTION = "ambient_spawn"
    FIELDS = ['int', 'int', 'int', 'int', 'int', 'bool', 'tick']

    def execute(self, state):
        result = super().execute(state)
        state.save()
        return result
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)