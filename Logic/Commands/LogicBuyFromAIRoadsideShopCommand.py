from Utils.Logging import logger
from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import AIRoadsideShop, Storage


class LogicBuyFromAIRoadsideShopCommand(LogicCommand):
    """Buy one offer (``f0`` = stand slot) from Greg's roadside shop."""

    NAME = "LogicBuyFromAIRoadsideShopCommand"
    TYPE = 47
    FIELDS = ['int', 'tick']

    def execute(self, state):
        slot = int(self.f0)
        offer = AIRoadsideShop.offer_at(state.home.data, slot)
        if not offer:
            logger.info("[CMD] AI roadside slot {}: no offer".format(slot))
            state.save()
            return False
        item = int(offer.get("Data") or 0)
        amount = max(1, int(offer.get("Amount") or 1))
        price = max(0, int(offer.get("Price") or 0))
        if self.data_row(item) is None:
            state.save()
            return False
        if not Storage.can_store(state.home.data, item, amount):
            state.save()
            return False
        if not self.spend_cash(state, price):
            state.save()
            return False
        AIRoadsideShop.replace_offer(state.home.data, slot)
        self.give(state, item, amount)
        logger.info("[CMD] buy AI stand slot {} -> {} x{} for {}".format(
            slot, offer.get("Name"), amount, price))
        state.save()
        return True

    def decode(self):
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
