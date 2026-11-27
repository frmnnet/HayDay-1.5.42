from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import FruitTrees


class LogicInstantCompleteFruitTreeCommand(LogicCommand):
    """Handler for LogicInstantCompleteFruitTreeCommand."""

    NAME = "LogicInstantCompleteFruitTreeCommand"
    TYPE = 59
    ACTION = "fruit_instant"
    FIELDS = ['int', 'tick']

    def execute(self, state):
        entry = FruitTrees.entry_for(state.home.data, self.f0)
        row = FruitTrees.data_row(entry)
        if entry is None or row is None:
            state.save()
            return False
        count = FruitTrees.fruit_count(row, entry)
        cost = row.i("InstantComplete", 0)
        if count <= 0 or cost <= 0 or not self.spend_diamonds(state, cost):
            state.save()
            return False
        FruitTrees.finish_growth(entry, row, self.now)
        state.save()
        return True
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
