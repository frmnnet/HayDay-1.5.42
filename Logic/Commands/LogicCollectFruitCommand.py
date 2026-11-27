from Utils.Logging import logger
from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import Achievements, FruitTrees, Storage


class LogicCollectFruitCommand(LogicCommand):
    """Collect one fruit slot from a placed tree/bush."""

    NAME = "LogicCollectFruitCommand"
    TYPE = 62
    FIELDS = ['int', 'short', 'tick']

    def execute(self, state):
        tree_id = self.f0
        index = int(self.f1)
        entry = FruitTrees.entry_for(state.home.data, tree_id)
        row = FruitTrees.data_row(entry)
        fruit = FruitTrees.fruit_item(row)
        fruits = entry.get("Fruits") if entry is not None else None
        if (entry is None or row is None or fruit is None
                or not isinstance(fruits, list)
                or index < 0 or index >= len(fruits)
                or not fruits[index]):
            logger.info("[CMD] collect fruit tree={} slot={}: nothing ready"
                        .format(tree_id, index))
            state.save()
            return False
        if not Storage.can_store(state.home.data, fruit.global_id, 1):
            logger.info("[CMD] collect fruit tree={} slot={}: barn full"
                        .format(tree_id, index))
            state.save()
            return False
        fruits[index] = False
        entry["Fruits"] = fruits
        if not any(fruits):
            FruitTrees.start_next_growth(entry, row, self.now)
        self.give(state, fruit.global_id, 1)
        self.earn_exp(state, fruit.i("ExpCollect", 0))
        action = "PickFruits" if row.b("IsFruit") else "PickBerries"
        Achievements.record(state, action, now=self.now)
        logger.info("[CMD] collect fruit tree={} slot={} -> {}".format(
            tree_id, index, fruit.name))
        state.save()
        return True
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
