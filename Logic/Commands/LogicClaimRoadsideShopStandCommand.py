from Utils.Logging import logger
from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import Achievements, RoadsideStand


class LogicClaimRoadsideShopStandCommand(LogicCommand):
    """Claim/clear a roadside shop stand slot (sold or cancelled).

    Wire layout (from ``createAndDecode``): ``short slot, int, tick``.
    """

    NAME = "LogicClaimRoadsideShopStandCommand"
    TYPE = 31
    FIELDS = ['short', 'int', 'tick']

    def execute(self, state):
        slot = self.arg(0, 0)
        stand = RoadsideStand.stand_at(
            state.home.data, slot, state.account.exp_level)
        if stand is None or not RoadsideStand.is_claimed(stand):
            logger.info("[CMD] roadside stand slot {} is not claimable"
                        .format(slot))
            state.save()
            return False
        data_id = int(self.arg(1, 0) or 0)
        if data_id and int(stand.get("Data") or 0) != data_id:
            logger.info(
                "[CMD] roadside stand slot {} data id mismatch ({}/{})"
                .format(slot, data_id, stand.get("Data")))
            state.save()
            return False
        entry = RoadsideStand.clear(
            state.home.data, slot, state.account.exp_level)
        payout = max(0, int(entry.get("Price") or 0))
        self.earn_cash(state, payout)
        state.home.inventory.give(RoadsideStand.SOLD_VALUE_ITEM, payout)
        Achievements.record(
            state, "RoadsideShopSalesWorth", amount=payout)
        logger.info("[CMD] roadside stand slot {} sold -> cash {}".format(
            slot, payout))
        state.save()
        return True

    def decode(self):
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
