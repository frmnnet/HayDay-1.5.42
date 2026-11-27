from Utils.Logging import logger
from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import Achievements, FruitTrees, Storage


class LogicCollectFruitTreeCommand(LogicCommand):
    """Collect every ready fruit from one placed tree/bush."""

    NAME = "LogicCollectFruitTreeCommand"
    TYPE = 61
    FIELDS = ['int', 'tick']
    def execute(self, state):
        tree_id = self.f0
        entry = FruitTrees.entry_for(state.home.data, tree_id)
        row = FruitTrees.data_row(entry)
        fruit = FruitTrees.fruit_item(row)
        fruits = entry.get("Fruits") if entry is not None else None
        if entry is None or row is None or fruit is None:
            state.save()
            return False
        if not isinstance(fruits, list) or not any(bool(v) for v in fruits):
            logger.info("[CMD] collect fruit tree {}: nothing ready".format(
                tree_id))
            state.save()
            return False
        amount = min(
            sum(1 for value in fruits if value),
            FruitTrees.fruit_count(row, entry))
        if not Storage.can_store(state.home.data, fruit.global_id, amount):
            logger.info("[CMD] collect fruit tree {}: barn full for {}".format(
                tree_id, fruit.name))
            state.save()
            return False
        entry["Fruits"] = [False] * len(fruits)
        FruitTrees.start_next_growth(entry, row, self.now)
        self.give(state, fruit.global_id, amount)
        self.earn_exp(state, row.i("ExpClear", 0))
        action = "PickFruits" if row.b("IsFruit") else "PickBerries"
        Achievements.record(state, action, amount=amount, now=self.now)
        logger.info("[CMD] collect fruit tree {} -> {} x{}".format(
            tree_id, fruit.name, amount))
        state.save()
        return True
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
