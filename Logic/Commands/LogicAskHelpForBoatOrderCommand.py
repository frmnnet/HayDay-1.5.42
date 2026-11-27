from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import Achievements


class LogicAskHelpForBoatOrderCommand(LogicCommand):
    """Handler for LogicAskHelpForBoatOrderCommand."""

    NAME = "LogicAskHelpForBoatOrderCommand"
    TYPE = 91
    ACTION = "boat_help"
    FIELDS = ['short', 'tick']

    def execute(self, state):
        result = super().execute(state)
        if result:
            Achievements.record(state, "SocialBoat")
        return result
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
