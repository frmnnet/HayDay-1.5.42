from Utils.Logging import logger
from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import Achievements, HomeAnimals, Storage


class LogicCollectAnimalCommand(LogicCommand):
    """Collect the product of a fed animal (f0 = animal data global id).

    The produced good and its exp reward come from ``animals.csv`` ->
    ``animal_goods.csv``; a payload never carries them.
    """

    NAME = "LogicCollectAnimalCommand"
    TYPE = 14
    FIELDS = ['int', 'tick']

    def execute(self, state):
        target = self.arg(0, 0)
        key = str(target)
        entry = HomeAnimals.entry_for(state.home.data, target)
        if entry is None:
            logger.info("[CMD] collect animal {}: not ready".format(key))
            state.save()
            return False
        row = self.data_row(entry.get("ID"))
        product = self.item_id(row.s("Good")) if row is not None else None
        if product is None:
            product = self.arg(1, 0)
        if product and not Storage.can_store(state.home.data, product, 1):
            logger.info("[CMD] collect animal {}: barn full for {}".format(
                key, product))
            state.save()
            return False
        entry = HomeAnimals.collect(state.home.data, target, self.now)
        if entry is None:
            logger.info("[CMD] collect animal {}: not ready".format(key))
            state.save()
            return False
        if product:
            self.give(state, product, 1)
        product_row = self.data_row(product)
        exp = product_row.i("ExpCollect", 3) if product_row is not None else 3
        if exp:
            self.earn_exp(state, exp)
        Achievements.record(state, "TurboCollectAnimalGoods", now=self.now)
        if product_row is not None:
            Achievements.record(
                state, "CollectAnimalProduct",
                action_data=product_row.s("Name"), now=self.now)
        logger.info("[CMD] collect animal {} -> product {} (+{} exp)".format(
            key, product, exp))
        state.save()
        return True

    def decode(self):
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
