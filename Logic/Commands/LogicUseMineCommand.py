from Utils.Logging import logger
import random

from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import Achievements, Storage


class LogicUseMineCommand(LogicCommand):
    """Use a mine hit: yields ore.

    Args (best guess): mine position, tool_id
    """

    NAME = "LogicUseMineCommand"
    TYPE = 64
    FIELDS = ['int', 'tick']
    def execute(self, state):
        mine = self.data_row(self.f0)
        if mine is None:
            mine = self.data.row(63, 1)
        hits = max(1, mine.i("NumOres", 1) if mine is not None else 1)
        tool = self.item(mine.s("Tool")) if mine is not None else None
        if mine is None or tool is None or not self.take(
                state, tool.global_id, 1):
            logger.info("[CMD] use mine: missing tool")
            state.save()
            return False
        ores = [
            row for row in self.data.rows(64)
            if row.i("Probability", 0) > 0
        ]
        if not ores:
            state.save()
            return False
        weighted = []
        for row in ores:
            weighted.extend([row] * row.i("Probability", 1))
        chosen = [random.choice(weighted) for _ in range(hits)]
        if not Storage.can_store_many(
                state.home.data, [(row.global_id, 1) for row in chosen]):
            logger.info("[CMD] use mine: barn full")
            state.save()
            return False
        for row in chosen:
            self.give(state, row.global_id, 1)
            exp = row.i("ExpCollect", 0)
            if exp:
                self.earn_exp(state, exp)
            Achievements.record(
                state, "CollectMineGood", action_data=row.s("Name"))
        logger.info("[CMD] use mine -> {} hits".format(hits))
        state.save()
        return True
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
