from Utils.Logging import logger
from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import TruckOrders


class LogicSpeedUpOrderCommand(LogicCommand):
    """Speed up an order refresh with diamonds.

    Args (best guess): order_id, diamond_cost
    """

    NAME = "LogicSpeedUpOrderCommand"
    TYPE = 29
    FIELDS = ['int', 'tick']

    def execute(self, state):
        order = self.arg(0, 0)
        level = int(getattr(state.account, "exp_level", 1) or 1)
        level_row = self.data.level_row(level)
        if level_row is None:
            state.save()
            return False
        cost = max(1, level_row.i("OrderSpeedUpPrice", 1))
        if not self.spend_diamonds(state, cost):
            state.save()
            return False
        TruckOrders.speed_up(state.home.data, order, self.now)
        logger.info("[CMD] speed up order {} for {} diamonds".format(order, cost))
        state.save()
        return True
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
