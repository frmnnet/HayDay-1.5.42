from Utils.Logging import logger
from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import HomeFields
from Logic.Fields import Field


class LogicBoostFieldCommand(LogicCommand):
    """Apply a ``boosters.csv`` booster to a field.

    The wire fields are ``booster data id, field game-object id``.
    """

    NAME = "LogicBoostFieldCommand"
    TYPE = 7
    FIELDS = ['int', 'int', 'tick']
    def execute(self, state):
        booster = self.data_row(self.f0)
        field_id = self.f1
        entry = HomeFields.entry_for(state.home.data, field_id)
        field = state.home.fields.get(field_id)
        if (booster is None or booster.tid != 17 or entry is None
                or not field.crop or field.state == Field.EMPTY):
            state.save()
            return False
        field.state = Field.READY
        field.ready = self.now
        state.home.fields.set(field_id, field)
        HomeFields.set_ready(state.home.data, field_id, field.crop)
        logger.info("[CMD] boost field {} with {}".format(
            field_id, booster.name))
        state.save()
        return True
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
