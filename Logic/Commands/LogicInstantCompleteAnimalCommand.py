from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import HomeAnimals


class LogicInstantCompleteAnimalCommand(LogicCommand):
    """Handler for LogicInstantCompleteAnimalCommand."""

    NAME = "LogicInstantCompleteAnimalCommand"
    TYPE = 15
    FIELDS = ['int', 'tick']

    def execute(self, state):
        animal = HomeAnimals.entry_for(state.home.data, self.f0)
        if animal is None:
            state.save()
            return False
        row = self.data_row(animal.get("ID"))
        product = self.item(row.s("Good")) if row is not None else None
        if row is None or product is None or not animal.get("Fed"):
            state.save()
            return False
        cost = product.i("InstantComplete", 0)
        if cost <= 0:
            state.save()
            return False
        if not self.spend_diamonds(state, max(1, cost)):
            state.save()
            return False
        HomeAnimals.instant(state.home.data, self.f0)
        state.save()
        return True
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
