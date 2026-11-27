from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand


class LogicDiscardBoyCommand(LogicCommand):
    """Handler for LogicDiscardBoyCommand."""

    NAME = "LogicDiscardBoyCommand"
    TYPE = 69
    ACTION = "boy_discard"
    FIELDS = ['tick']

    def execute(self, state):
        return super().execute(state)
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
