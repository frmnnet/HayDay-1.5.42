from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import Forests, HomeObjects


class LogicInstantDestructForestCommand(LogicCommand):
    """Handler for LogicInstantDestructForestCommand."""

    NAME = "LogicInstantDestructForestCommand"
    TYPE = 19
    ACTION = "forest_destroy"
    FIELDS = ['int', 'tick']

    def execute(self, state):
        entry = Forests.entry_for(state.home.data, self.f0)
        row = Forests.data_row(entry)
        if entry is None or row is None:
            state.save()
            return False
        cost = row.i("InstantComplete", 0)
        if cost <= 0 or not self.spend_diamonds(state, cost):
            state.save()
            return False
        HomeObjects.remove(state.home.data, self.f0)
        state.home.data.get(Forests.KEY, {}).pop(str(self.f0), None)
        exp = row.i("ExpClear", 0)
        if exp:
            self.earn_exp(state, exp)
        state.save()
        return True
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
