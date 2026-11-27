from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand


class LogicCallBoyCommand(LogicCommand):
    """Handler for LogicCallBoyCommand."""

    NAME = "LogicCallBoyCommand"
    TYPE = 74
    ACTION = "boy_call"
    FIELDS = ['tick']

    def execute(self, state):
        return super().execute(state)
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
