from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import Forests, HomeObjects


class LogicCollectForestCommand(LogicCommand):
    """Handler for LogicCollectForestCommand."""

    NAME = "LogicCollectForestCommand"
    TYPE = 20
    ACTION = "forest_collect"
    FIELDS = ['int', 'tick']

    def execute(self, state):
        entry = Forests.entry_for(state.home.data, self.f0)
        if entry is None:
            state.save()
            return False
        record = Forests.record(state.home.data, self.f0)
        if int(record.get("Ready") or 0) > self.now:
            state.save()
            return False
        exp = int(record.get("Exp") or 0)
        HomeObjects.remove(state.home.data, self.f0)
        state.home.data.get(Forests.KEY, {}).pop(str(self.f0), None)
        if exp:
            self.earn_exp(state, exp)
        state.save()
        return True
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
