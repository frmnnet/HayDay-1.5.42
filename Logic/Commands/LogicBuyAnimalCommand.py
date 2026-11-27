from Utils.Reader import Reader
from Utils.Logging import logger
from Logic.Commands.LogicCommand import LogicCommand
from Logic import Achievements, HomeAnimals, HomeObjects, Pets


class LogicBuyAnimalCommand(LogicCommand):
    """Buy an animal (f0 = animals.csv global id, f1 = object id, ...).

    ``LogicBuyAnimalCommand::execute`` uses the object's diamond price when
    present and otherwise the coin price, which increases every
    ``DoPriceIncreaseEveryNObject`` animals owned (``animals.csv``).
    """

    NAME = "LogicBuyAnimalCommand"
    TYPE = 5
    FIELDS = ['int', 'int', 'int', 'int', 'bool', 'tick']

    def execute(self, state):
        animal_id = self.f0
        row = self.data_row(animal_id)
        if row is None:
            logger.info("[CMD] buy animal {}: unknown data id".format(animal_id))
            state.save()
            return False
        if row.tid not in (HomeAnimals.ANIMAL_TYPE, Pets.PET_TYPE):
            logger.info("[CMD] buy animal {}: unsupported data class".format(
                animal_id))
            state.save()
            return False
        if not self.require_unlock(state, row):
            state.save()
            return False

        owned = sum(
            1 for entry in state.home.data.get("Objects", [])
            if HomeObjects.object_type(entry) in (
                HomeAnimals.ANIMAL_TYPE, 78)
            and str(entry.get("ID")) == str(animal_id)
        )
        if not self.spend_price(state, row, count=owned):
            state.save()
            return False
        price = self.data.shop_price(row, count=owned)[1]

        if int(animal_id) // 100000 == 78:
            Pets.add(
                state.home.data, animal_id, self.f1, self.f2,
                habitat_id=self.f3, mirrored=bool(self.f4))
            Achievements.record(state, "BuyPet")
        elif int(animal_id) // 100000 == HomeAnimals.ANIMAL_TYPE:
            HomeAnimals.add(
                state.home.data, animal_id, self.f1, self.f2,
                habitat_id=self.f3, mirrored=bool(self.f4))
        state.save()
        logger.info("[CMD] buy animal {} for {}".format(animal_id, price))
        return True

    def decode(self):
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
