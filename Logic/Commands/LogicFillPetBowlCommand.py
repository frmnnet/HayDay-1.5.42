from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import Achievements, Pets


class LogicFillPetBowlCommand(LogicCommand):
    """Handler for LogicFillPetBowlCommand."""

    NAME = "LogicFillPetBowlCommand"
    TYPE = 86
    ACTION = "pet_bowl"
    FIELDS = ['int', 'tick']

    def execute(self, state):
        entry, feed, amount = Pets.feed_pet(
            state.home.data, self.f0, self.now)
        if entry is None or feed is None or not self.take(
                state, feed.global_id, amount):
            state.save()
            return False
        Achievements.record(state, "FeedPet")
        state.save()
        return True
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
