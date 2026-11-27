from Utils.Logging import logger
from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import Achievements, HomeObjects, Storage


class LogicCollectProductionsCommand(LogicCommand):
    """Collect finished goods from a building.

    Args (best guess): building_x, building_y
    """

    NAME = "LogicCollectProductionsCommand"
    TYPE = 13
    FIELDS = ['int', 'tick']

    def execute(self, state):
        # Real layout: f0 = building object id.
        building = self.f0
        _idx, entry = HomeObjects.find_by_runtime_id(
            state.home.data, building)
        if entry is None or HomeObjects.object_type(entry) != 6:
            logger.info("[CMD] collect building {}: invalid building".format(
                building))
            state.save()
            return False
        now = self.now
        ready = state.home.productions.ready_for(building, now)
        units = self.good_units(
            self.data_row(ready[0][1].good)) if ready else 1
        if ready and not Storage.can_store(
                state.home.data, ready[0][1].good, units):
            logger.info("[CMD] collect building {}: storage full".format(
                building))
            state.save()
            return False
        production = state.home.productions.complete_next(
            building, now)
        if production is None:
            logger.info("[CMD] collect building {}: nothing ready".format(building))
            state.save()
            return False
        units = 1
        if production.good:
            row = self.data_row(production.good)
            units = self.good_units(row)
            self.give(state, production.good, units)
            if int(production.good) // 100000 == 65:
                Achievements.record(state, "CollectFromSmelter")
        else:
            row = None
        exp = row.i("ExpCollect", 0) if row is not None else 2
        if exp:
            self.earn_exp(state, exp)
        logger.info("[CMD] collect building {}: {} x{}".format(
            building, production.good, units))
        state.save()
        return True
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
