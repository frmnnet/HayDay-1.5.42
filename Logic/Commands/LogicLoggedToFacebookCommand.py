from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand


class LogicLoggedToFacebookCommand(LogicCommand):
    """Handler for LogicLoggedToFacebookCommand."""

    NAME = "LogicLoggedToFacebookCommand"
    TYPE = 67
    ACTION = "facebook"
    FIELDS = ['bool', 'tick']

    def execute(self, state):
        result = super().execute(state)
        state.save()
        return result
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)