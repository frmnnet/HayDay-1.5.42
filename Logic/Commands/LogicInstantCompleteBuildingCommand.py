from Utils.Logging import logger
from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import Achievements, HomeBuildings, HomeObjects


class LogicInstantCompleteBuildingCommand(LogicCommand):
    """Finish a building upgrade instantly with diamonds.

    Args (best guess): building_id, diamond_cost
    """

    NAME = "LogicInstantCompleteBuildingCommand"
    TYPE = 16
    FIELDS = ['int', 'tick']
    def execute(self, state):
        building = self.arg(0, 0)
        _index, entry = HomeObjects.find_by_runtime_id(
            state.home.data, building)
        if entry is None:
            logger.info("[CMD] instant complete building {}: not found".format(
                building))
            state.save()
            return False
        target_data = entry.get("TargetData", entry.get("ID"))
        row = self.data_row(target_data)
        cost = row.i("InstantComplete", 0) if row is not None else 0
        if cost <= 0:
            logger.info(
                "[CMD] instant complete building {}: no diamond price in CSV"
                .format(building))
            state.save()
            return False
        if not self.spend_diamonds(state, cost):
            state.save()
            return False
        target_data = HomeBuildings.complete(
            state.home.data, building, self.now, force=True)
        if target_data is not None:
            row = self.data_row(target_data)
            exp = row.i("ExpToBuild", 0) if row is not None else 0
            if exp:
                self.earn_exp(state, exp)
            Achievements.record(state, "BuildBuildings")
            logger.info("[CMD] completed construction {} -> {}".format(
                building, target_data))
            state.save()
            return True

        # Instant completion also finishes damaged/renovated buildings.
        entry.pop("BrokenParts", None)
        logger.info("[CMD] instant complete building {} for {} diamonds".format(
            building, cost))
        state.save()
        return True
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
