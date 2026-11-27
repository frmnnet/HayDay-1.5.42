from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand


class LogicClaimBoyBoxCommand(LogicCommand):
    """Handler for LogicClaimBoyBoxCommand."""

    NAME = "LogicClaimBoyBoxCommand"
    TYPE = 73
    ACTION = "boy_claim"
    FIELDS = ['tick']

    def execute(self, state):
        return super().execute(state)
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
