from Utils.Reader import Reader
from Utils.Logging import logger
from Logic.Commands.LogicCommand import LogicCommand
from Logic.Fields import Field
from Logic import HomeFields


class LogicHarvestFieldOverCommand(LogicCommand):
    """Harvest finished for a field (f0 = field object id)."""

    NAME = "LogicHarvestFieldOverCommand"
    TYPE = 23
    FIELDS = ['int', 'tick']

    def execute(self, state):
        field_id = self.f0
        field = state.home.fields.get(field_id)
        entry = HomeFields.entry_for(state.home.data, field_id)
        if (entry is None or not entry.get("_HarvestStarted")
                or not entry.get("_ResourceGained")):
            logger.info(
                "[CMD] harvest over field {}: harvest sequence invalid"
                .format(field_id))
            state.save()
            return False
        field.state = Field.EMPTY
        field.crop = 0
        field.planted = 0
        field.ready = 0
        state.home.fields.set(field_id, field)
        HomeFields.set_empty(state.home.data, field_id)
        logger.info("[CMD] harvest over field {}".format(field_id))
        state.save()
        return True

    def decode(self):
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
