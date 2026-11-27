from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import Forests


class LogicDestructForestCommand(LogicCommand):
    """Handler for LogicDestructForestCommand."""

    NAME = "LogicDestructForestCommand"
    TYPE = 18
    ACTION = "forest_destroy"
    FIELDS = ['int', 'tick']

    def execute(self, state):
        entry = Forests.entry_for(state.home.data, self.f0)
        row = Forests.data_row(entry)
        if entry is None or row is None:
            state.save()
            return False
        tool = self.item(row.s("Tool"))
        if tool is None or not self.take(state, tool.global_id, 1):
            state.save()
            return False
        Forests.begin(state.home.data, self.f0, row, now=self.now)
        state.save()
        return True
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
