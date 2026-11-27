from Utils.Reader import Reader
from Utils.Logging import logger
from Logic.Commands.LogicCommand import LogicCommand
from Logic.Fields import Field
from Logic import HomeFields


class LogicHarvestFieldGainCommand(LogicCommand):
    """Harvest gain for a field (f0 = field object id)."""

    NAME = "LogicHarvestFieldGainCommand"
    TYPE = 22
    FIELDS = ['int', 'tick']

    def execute(self, state):
        field_id = self.f0
        entry = HomeFields.entry_for(state.home.data, field_id)
        if entry is None or not entry.get("_HarvestStarted"):
            logger.info(
                "[CMD] harvest gain field {}: harvest was not started"
                .format(field_id))
            state.save()
            return False
        if entry.get("_ResourceGained"):
            state.save()
            return False
        crop = int(entry.get("_HarvestStarted") or 0)
        entry["_ResourceGained"] = True
        logger.info(
            "[CMD] harvest gain confirmed field {} crop={}".format(
                field_id, crop))
        state.save()
        return True

    def decode(self):
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
