from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand


class LogicDiscardPeopleOrderCommand(LogicCommand):
    """Handler for LogicDiscardPeopleOrderCommand."""

    NAME = "LogicDiscardPeopleOrderCommand"
    TYPE = 43
    ACTION = "order_discard"
    FIELDS = ['int', 'tick']

    def execute(self, state):
        return super().execute(state)
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
