from Utils.Reader import Reader
from Utils.Logging import logger
from Logic.Commands.LogicCommand import LogicCommand
from Logic import Storage


class LogicBuySeedCommand(LogicCommand):
    """Buy one seed (f0 = crop data global id).

    ``LogicBuySeedCommand::execute`` charges ``getShopDiamondPrice`` first
    and falls back to ``getShopPrice`` when there is no diamond price, so
    the real price comes from the row's ``DiamondPrice``/``Price`` columns.
    """

    NAME = "LogicBuySeedCommand"
    TYPE = 8
    FIELDS = ['int', 'tick']

    def execute(self, state):
        seed = self.f0
        row = self.data_row(seed)
        if row is None or row.tid != 4 or seed == 400000:
            logger.info("[CMD] buy seed {}: unknown crop".format(seed))
            state.save()
            return False
        if not self.require_unlock(state, row):
            state.save()
            return False
        if not Storage.can_store(state.home.data, seed, 1):
            logger.info("[CMD] buy seed {}: silo full".format(seed))
            state.save()
            return False
        currency, cost = self.data.shop_price(row)
        if not self.spend_price(state, row):
            state.save()
            return False
        self.give(state, seed, 1)
        logger.info("[CMD] buy seed {} for {} {}".format(
            seed, cost, currency))
        state.save()
        return True

    def decode(self):
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
