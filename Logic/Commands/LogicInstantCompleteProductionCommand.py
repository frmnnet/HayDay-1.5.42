from Utils.Logging import logger
from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import Storage


class LogicInstantCompleteProductionCommand(LogicCommand):
    """Finish one production queue slot instantly with diamonds.

    Binary layout is ``production index, building game-object id``.
    """

    NAME = "LogicInstantCompleteProductionCommand"
    TYPE = 12
    FIELDS = ['int', 'int', 'tick']

    def execute(self, state):
        now = self.now
        index = int(self.f0)
        building = self.f1
        state.home.productions.advance(building, now)
        queue = state.home.productions.get_queue(building)
        active = [
            production for production in queue
            if not production.finished
        ]
        if index < 0 or index >= len(active):
            logger.info(
                "[CMD] instant production building={} slot={} not found"
                .format(building, index))
            state.save()
            return False
        production = active[index]
        good_row = self.data_row(production.good)
        base_price = good_row.i("InstantComplete", 0) \
            if good_row is not None else 0
        units = self.good_units(good_row)
        remaining = (
            max(1, int(production.duration))
            if production.queued
            else max(0, int(production.ready) - int(now))
        )
        cost = self.instant_complete_price(
            base_price, remaining, production.duration)
        if cost <= 0:
            state.save()
            return False
        if not self.spend_diamonds(state, cost):
            state.save()
            return False
        collect = Storage.can_store(state.home.data, production.good, units)
        if state.home.productions.finish_active(
                building, index, now, auto_collect=collect) is None:
            state.save()
            return False
        if collect:
            self.give(state, production.good, units)
        logger.info(
            "[CMD] instant complete production building={} slot={}{}"
            .format(
                building, index,
                " -> collected {} x{}".format(production.good, units)
                if collect else " -> ready to collect"))
        state.save()
        return True
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
