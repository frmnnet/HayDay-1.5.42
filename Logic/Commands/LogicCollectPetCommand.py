from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import Pets, Storage


class LogicCollectPetCommand(LogicCommand):
    """Handler for LogicCollectPetCommand."""

    NAME = "LogicCollectPetCommand"
    TYPE = 87
    ACTION = "pet_collect"
    FIELDS = ['int', 'tick']

    def execute(self, state):
        entry = Pets.entry_for(state.home.data, self.f0)
        row = Pets.data_row(entry)
        if (entry is None or row is None
                or not Pets.is_ready(state.home.data, self.f0, self.now)):
            state.save()
            return False
        rewards = []
        for source in [row.values] + row.subs:
            name = source.get("Vouchers")
            if not name:
                continue
            item = self.item(name)
            if item is not None:
                try:
                    amount = int(source.get("VoucherCount") or 1)
                except (TypeError, ValueError):
                    amount = 1
                rewards.append((item.global_id, max(1, amount)))
        if not Storage.can_store_many(state.home.data, rewards):
            state.save()
            return False
        exp = row.i("Exp", 0)
        if exp:
            self.earn_exp(state, exp)
        for item_id, amount in rewards:
            self.give(state, item_id, amount)
        Pets.clear(state.home.data, self.f0)
        state.save()
        return True
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
