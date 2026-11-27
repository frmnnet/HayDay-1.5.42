from Utils.Logging import logger
from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import HomeAnimals


class LogicFeedAnimalCommand(LogicCommand):
    """Feed an animal (f0 = animal data global id / animal object id).

    ``LogicFeedAnimalCommand::execute`` spends one unit of the animal's
    ``Feed`` good and starts a timer equal to the produced good's
    ``TimeMin``/``TimeSec``.  Both come from ``animals.csv`` /
    ``animal_feed.csv`` / ``animal_goods.csv``.
    """

    NAME = "LogicFeedAnimalCommand"
    TYPE = 9
    FIELDS = ['int', 'tick']

    def execute(self, state):
        target = self.arg(0, 0)
        entry = HomeAnimals.entry_for(state.home.data, target)
        row = self.data_row(entry.get("ID")) if entry is not None else None
        key = str(target)

        if entry is None:
            logger.info("[CMD] feed animal {}: no such animal object".format(key))
            state.save()
            return False
        if entry.get("Fed"):
            logger.info("[CMD] feed animal {}: already fed".format(key))
            state.save()
            return False
        if row is None:
            logger.info("[CMD] feed animal {}: unknown animal data".format(key))
            state.save()
            return False
        feed = self.item_id(row.s("Feed"))
        if feed is None or not state.home.inventory.has(feed, 1):
            logger.info("[CMD] feed animal {}: missing {} ".format(
                key, row.s("Feed")))
            state.save()
            return False
        product = self.item(row.s("Good"))
        produce_time = product.seconds() if product is not None else 0
        if produce_time <= 0:
            logger.info("[CMD] feed animal {}: invalid product {}".format(
                key, row.s("Good")))
            state.save()
            return False
        self.take(state, feed, 1)
        HomeAnimals.feed(
            state.home.data, target, produce_time, self.now + produce_time,
            now=self.now)
        logger.info("[CMD] feed animal {} (ready in {}s)".format(
            key, produce_time))
        state.save()
        return True

    def decode(self):
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
