from Utils.Logging import logger
from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import HomeObjects
from Logic.GameData import GOODS_TABLES
from Logic.Productions import slot_count


class LogicStartProductionCommand(LogicCommand):
    """Start producing a good in a processing building.

    Real layout (``LogicStartProductionCommand::execute``)::

        f0 = good global id (the ``*_goods.csv`` table row)
        f1 = building game object id

    Time, unlocked level and the recipe inputs are read from that CSV row;
    ``Requirement``/``RequirementAmount`` continuation rows are extra inputs.
    """

    NAME = "LogicStartProductionCommand"
    TYPE = 10
    FIELDS = ['int', 'int', 'tick']
    def execute(self, state):
        now = self.now
        good = self.f0
        building = self.f1
        row = self.data_row(good)

        if row is None or row.tid not in GOODS_TABLES:
            logger.info("[CMD] start production {}: unknown good".format(good))
            state.save()
            return False
        if not self.require_unlock(state, row):
            state.save()
            return False

        _idx, building_entry = HomeObjects.find_by_runtime_id(
            state.home.data, building)
        if building_entry is None or HomeObjects.object_type(
                building_entry) != 6:
            logger.info("[CMD] start production {}: building {} not found"
                        .format(good, building))
            state.save()
            return False
        building_row = self.data_row(building_entry.get("ID"))
        if building_row is None:
            state.save()
            return False
        producer = row.s("ProcessingBuilding").strip().lower()
        if producer and producer != building_row.s("Name").strip().lower():
            logger.info("[CMD] start production {}: requires {}, got {}".format(
                good, row.s("ProcessingBuilding"), building_row.name))
            state.save()
            return False

        queue = state.home.productions.get_queue(building)
        active_count = state.home.productions.active_count(
            building, now)
        slots = slot_count(building_row, building_entry.get("Rank", 1))
        if active_count >= slots:
            logger.info(
                "[CMD] start production {}: queue full ({}/{}), rank={}"
                .format(good, active_count, slots,
                        building_entry.get("Rank", 1)))
            state.save()
            return False

        required = []
        for name, amount in row.requirements():
            item = self.item(name)
            if item is None or amount <= 0:
                logger.info("[CMD] start production {} -> unknown requirement "
                            "{!r}".format(good, name))
                state.save()
                return False
            item_id = item.global_id
            if not state.home.inventory.has(item_id, amount):
                logger.info("[CMD] start production {} -> missing {} x{} "
                            "(have {})".format(
                                good, name, amount,
                                state.home.inventory.amount(item_id)))
                state.save()
                return False
            required.append((item_id, amount))

        produce_time = row.seconds()
        if produce_time <= 0:
            logger.info("[CMD] start production {}: invalid duration".format(good))
            state.save()
            return False
        for item_id, amount in required:
            self.take(state, item_id, amount)

        state.home.productions.start(
            building, good, produce_time=produce_time, now=now)
        logger.info("[CMD] start production good={} at building {} "
                    "time={}s".format(good, building, produce_time))
        state.save()
        return True

    def decode(self):
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
