from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import Achievements, FruitTrees


class LogicReviveFruitTreeCommand(LogicCommand):
    """Handler for LogicReviveFruitTreeCommand."""

    NAME = "LogicReviveFruitTreeCommand"
    TYPE = 63
    ACTION = "fruit_revive"
    FIELDS = ['int', 'tick']

    def execute(self, state):
        entry = FruitTrees.entry_for(state.home.data, self.f0)
        row = FruitTrees.data_row(entry)
        if entry is None or row is None:
            state.save()
            return False
        tool = self.item(row.s("Tool"))
        if tool is None or not self.take(state, tool.global_id, 1):
            state.save()
            return False
        entry.pop("Dead", None)
        FruitTrees.start_growth_entry(
            entry, row, now=self.now, phase=1)
        Achievements.record(state, "ReviveFruitTrees")
        state.save()
        return True
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
