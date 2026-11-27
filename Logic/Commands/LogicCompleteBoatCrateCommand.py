from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import Achievements


class LogicCompleteBoatCrateCommand(LogicCommand):
    """Handler for LogicCompleteBoatCrateCommand."""

    NAME = "LogicCompleteBoatCrateCommand"
    TYPE = 56
    ACTION = "boat_crate"
    FIELDS = ['byte', 'bool', 'tick']

    def execute(self, state):
        result = super().execute(state)
        if result:
            Achievements.record(state, "BoatCrates")
        state.save()
        return result
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
