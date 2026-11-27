from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import FruitTrees


class LogicReviveFruitTreeRequestCommand(LogicCommand):
    """Handler for LogicReviveFruitTreeRequestCommand."""

    NAME = "LogicReviveFruitTreeRequestCommand"
    TYPE = 65
    ACTION = "fruit_revive"
    FIELDS = ['int', 'tick']

    def execute(self, state):
        entry = FruitTrees.entry_for(state.home.data, self.f0)
        if entry is None or FruitTrees.data_row(entry) is None:
            state.save()
            return False
        entry["HelpRequested"] = True
        state.save()
        return True
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
