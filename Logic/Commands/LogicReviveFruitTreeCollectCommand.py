from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import Achievements, FruitTrees


class LogicReviveFruitTreeCollectCommand(LogicCommand):
    """Handler for LogicReviveFruitTreeCollectCommand."""

    NAME = "LogicReviveFruitTreeCollectCommand"
    TYPE = 66
    ACTION = "fruit_revive"
    FIELDS = ['int', 'tick']

    def execute(self, state):
        entry = FruitTrees.entry_for(state.home.data, self.f0)
        row = FruitTrees.data_row(entry)
        if entry is None or row is None:
            state.save()
            return False
        entry.pop("Dead", None)
        entry.pop("HelpRequested", None)
        FruitTrees.start_growth_entry(
            entry, row, now=self.now, phase=1)
        Achievements.record(state, "ReviveFruitTrees")
        state.save()
        return True
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
