from Utils.Logging import logger
from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import TruckOrders


class LogicDiscardOrderCommand(LogicCommand):
    """Discard a farm order (no reward).

    Args (best guess): order_id
    """

    NAME = "LogicDiscardOrderCommand"
    TYPE = 27
    FIELDS = ['byte', 'tick']

    def execute(self, state):
        order = self.arg(0, 0)
        level = int(getattr(state.account, "exp_level", 1) or 1)
        level_row = self.data.level_row(level)
        cooldown = (
            level_row.i("OrderCancelTimeMin", 0) * 60
            if level_row is not None else 0
        )
        TruckOrders.discard(state.home.data, order, cooldown, self.now)
        logger.info("[CMD] discard order {}".format(order))
        state.save()
        return True
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
