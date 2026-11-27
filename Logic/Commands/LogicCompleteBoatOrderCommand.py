from Utils.Logging import logger
from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import Achievements


class LogicCompleteBoatOrderCommand(LogicCommand):
    """Complete a boat order (no payload fields).

    Boat payouts come from ``exp_levels.csv``: ``MinBoatOrderValue`` /
    ``MaxBoatOrderValue`` bound the crate value and ``BoatRewardMultiplier``
    scales the reward (1000 = 1.0 in the client's fixed-point math).
    """

    NAME = "LogicCompleteBoatOrderCommand"
    TYPE = 55
    FIELDS = ['tick']

    def execute(self, state):
        level = int(getattr(state.account, "exp_level", 1) or 1)
        row = self.data.level_row(level)
        low = row.i("MinBoatOrderValue", 0) if row is not None else 0
        high = row.i("MaxBoatOrderValue", 0) if row is not None else 0
        multiplier = row.i("BoatRewardMultiplier", 1000) if row is not None else 1000

        value = (low + high) // 2 if high > low else 200
        cash = max(1, value * max(1, multiplier) // 1000)
        exp = max(1, cash // 2)

        boats = state.home.data.setdefault("Boats", {})
        record = boats.setdefault("active", {})
        record.update({"Completed": True, "Cash": cash, "Exp": exp})
        self.earn_cash(state, cash)
        self.earn_exp(state, exp)
        Achievements.record(state, "BoatOrders")
        Achievements.record(state, "EarnCoinsFromBoat", amount=cash)
        Achievements.record(state, "CompleteConsecutiveBoatOrders")
        logger.info("[CMD] complete boat order -> cash {}, exp {}".format(cash, exp))
        state.save()
        return True

    def decode(self):
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
