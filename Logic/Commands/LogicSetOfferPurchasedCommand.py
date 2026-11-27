from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand


class LogicSetOfferPurchasedCommand(LogicCommand):
    """Handler for LogicSetOfferPurchasedCommand."""

    NAME = "LogicSetOfferPurchasedCommand"
    TYPE = 94
    ACTION = "offer_purchased"
    FIELDS = ['tick']

    def execute(self, state):
        return super().execute(state)
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
