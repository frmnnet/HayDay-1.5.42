from Utils.Logging import logger
from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import TruckOrders


class LogicCollectCarCommand(LogicCommand):
    """Claim the cash/exp brought back by a completed truck order.

    This is the second half of ``LogicCompleteOrderCommand`` in the client
    (``LogicCar::hasRewardCollectable`` / ``giveAvatarReward``).  No payload
    fields are sent; the pending reward lives in the farm state.
    """

    NAME = "LogicCollectCarCommand"
    TYPE = 41
    FIELDS = ['tick']

    def execute(self, state):
        reward = TruckOrders.collect(state.home.data, now=self.now)
        if reward is None:
            logger.info("[CMD] collect car: nothing to claim")
            state.save()
            return False
        cash = int(reward.get("cash") or 0)
        exp = int(reward.get("exp") or 0)
        voucher = int(reward.get("voucher") or 0)
        TruckOrders.grant_reward(self, state, reward)

        logger.info("[CMD] collect car -> cash {}, exp {}, voucher {}".format(
            cash, exp, voucher))
        state.save()
        return True

    def decode(self):
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
