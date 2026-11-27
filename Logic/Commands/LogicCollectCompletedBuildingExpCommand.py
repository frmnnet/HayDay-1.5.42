from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import Achievements, HomeBuildings


class LogicCollectCompletedBuildingExpCommand(LogicCommand):
    """Handler for LogicCollectCompletedBuildingExpCommand."""

    NAME = "LogicCollectCompletedBuildingExpCommand"
    TYPE = 17
    FIELDS = ['int', 'tick']

    def execute(self, state):
        target_data = HomeBuildings.complete(state.home.data, self.f0, self.now)
        if target_data is not None:
            row = self.data_row(target_data)
            exp = row.i("ExpToBuild", 0) if row is not None else 0
            if exp:
                self.earn_exp(state, exp)
            Achievements.record(state, "BuildBuildings")
            state.save()
            return True
        return super().execute(state)
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
