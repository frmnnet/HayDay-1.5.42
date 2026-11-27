from Utils.Logging import logger
from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic.Fields import Field
from Logic import Achievements, HomeFields, Storage


class LogicHarvestFieldCommand(LogicCommand):
    """Harvest a grown crop from a field tile.

    ``LogicHarvestFieldCommand::execute`` reads two columns from
    ``fields.csv``: ``Harvest`` (how many crops are added) and
    ``ExpCollect`` (the exp added with them).
    """

    NAME = "LogicHarvestFieldCommand"
    TYPE = 2
    FIELDS = ['int', 'tick']

    def execute(self, state):
        field_id = self.f0
        fields = state.home.fields
        now = self.now
        HomeFields.advance(state.home.data, fields, now=now)
        crop = HomeFields.crop_for(state.home.data, field_id)
        if not crop or not HomeFields.is_ready(
                state.home.data, field_id, now):
            logger.info("[CMD] harvest field {}: nothing ready".format(
                field_id))
            state.save()
            return False
        row = self.data_row(crop)
        amount = row.i("Harvest", 1) if row is not None else 1
        exp = row.i("ExpCollect", 0) if row is not None else 0
        # Validate capacity before mutating the field.  Otherwise a full silo
        # rejects the grant after the crop has already been cleared.
        if not Storage.can_store(state.home.data, crop, amount):
            logger.info("[CMD] harvest field {}: silo full for {} x{}".format(
                field_id, crop, amount))
            state.save()
            return False
        field = Field(crop=0, state=Field.EMPTY, planted=0, ready=0)
        fields.set(field_id, field)
        entry = HomeFields.set_empty(state.home.data, field_id)
        self.give(state, crop, amount)
        if exp:
            self.earn_exp(state, exp)
        if entry is not None:
            entry["_HarvestStarted"] = int(crop)
            entry.pop("_ResourceGained", None)
        Achievements.record(state, "TurboHarvest", now=self.now)
        logger.info("[CMD] harvest field {} -> {} x{} (+{} exp)".format(
            field_id, crop, amount, exp))
        state.save()
        return True

    def decode(self):
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
