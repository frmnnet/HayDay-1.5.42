import time

from Utils.Logging import logger
from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import Achievements, TruckOrders


class LogicCompleteOrderCommand(LogicCommand):
    """Complete a farm order (f0 = order index).

    ``LogicOrder::countCashAndExp`` sums each requested good's ``OrderPrice``
    and ``OrderExp`` values.  The server does not model generated order
    contents, so the payout is derived from the level's
    ``OrderMinValue``/``OrderMaxValue`` window in ``exp_levels.csv``.

    The client does not pay out immediately: it sends the truck away and the
    reward is claimed by ``LogicCollectCarCommand``.  The pending reward is
    stored in the farm state so both commands stay in sync.
    """

    NAME = "LogicCompleteOrderCommand"
    TYPE = 28
    FIELDS = ['byte', 'int', 'tick']

    def execute(self, state):
        order = self.f1
        level = int(getattr(state.account, "exp_level", 1) or 1)
        level_row = self.data.level_row(level)
        cooldown = (
            level_row.i("OrderCancelTimeMin", 0) * 60
            if level_row is not None else 120
        )
        current = TruckOrders.record(state.home.data, order)
        last_completed = int(current.get("CompletedAt") or 0)
        if last_completed and self.now - last_completed < max(1, cooldown):
            logger.info(
                "[CMD] complete order {} rejected: cooldown {}s".format(
                    order, max(0, cooldown - (self.now - last_completed))))
            state.save()
            return False

        previous = TruckOrders.take_pending_reward(state.home.data)
        if previous is not None:
            TruckOrders.grant_reward(self, state, previous)
            logger.info("[CMD] auto-collected previous car reward for order {}".format(
                previous.get("order")))

        cash, exp = self.order_reward(state, order)
        TruckOrders.complete(
            state.home.data, order, cash, exp, voucher=0,
            now=self.now, level=level)
        Achievements.record(state, "CarOrders", now=self.now)
        Achievements.record(state, "TurboCarOrders", now=self.now)
        state.account_stat("truck_orders_completed", 1)
        day = time.strftime("%Y%m%d")
        state.account_stat("truck_orders_" + day, 1)
        logger.info("[CMD] complete order {} -> pending cash {}, exp {}".format(
            order, cash, exp))
        state.save()
        return True

    def decode(self):
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
