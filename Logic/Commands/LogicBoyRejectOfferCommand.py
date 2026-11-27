from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand


class LogicBoyRejectOfferCommand(LogicCommand):
    """Handler for LogicBoyRejectOfferCommand."""

    NAME = "LogicBoyRejectOfferCommand"
    TYPE = 72
    ACTION = "boy_reject"
    FIELDS = ['tick']

    def execute(self, state):
        return super().execute(state)
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
