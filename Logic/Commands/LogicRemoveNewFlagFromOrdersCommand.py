from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import TruckOrders


class LogicRemoveNewFlagFromOrdersCommand(LogicCommand):
    """Handler for LogicRemoveNewFlagFromOrdersCommand."""

    NAME = "LogicRemoveNewFlagFromOrdersCommand"
    TYPE = 26
    FIELDS = ['int', 'tick']

    def execute(self, state):
        # The payload is the order-table data id, not one order slot.
        TruckOrders.clear_new_flags(state.home.data)
        state.save()
        return True
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
