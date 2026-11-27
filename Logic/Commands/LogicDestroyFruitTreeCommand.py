from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import FruitTrees, HomeObjects


class LogicDestroyFruitTreeCommand(LogicCommand):
    """Handler for LogicDestroyFruitTreeCommand."""

    NAME = "LogicDestroyFruitTreeCommand"
    TYPE = 60
    ACTION = "fruit_destroy"
    FIELDS = ['int', 'tick']

    def execute(self, state):
        entry = FruitTrees.entry_for(state.home.data, self.f0)
        row = FruitTrees.data_row(entry)
        if entry is None or row is None:
            state.save()
            return False
        tool = self.item(row.s("Tool"))
        if tool is not None and not self.take(state, tool.global_id, 1):
            state.save()
            return False
        HomeObjects.remove(state.home.data, self.f0)
        state.home.data.setdefault("FruitTrees", {}).pop(str(self.f0), None)
        self.earn_exp(state, row.i("ExpClear", 0))
        state.save()
        return True
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
