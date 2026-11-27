from Utils.Logging import logger
from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic.Fields import Field
from Logic import HomeFields


class LogicInstantCompleteFieldCommand(LogicCommand):
    """Instantly grow a field with diamonds.

    Args (best guess): x, y
    """

    NAME = "LogicInstantCompleteFieldCommand"
    TYPE = 24
    FIELDS = ['int', 'tick']

    def execute(self, state):
        # Real layout: f0 = field object id.
        field_id = self.f0
        now = self.now
        HomeFields.advance(state.home.data, state.home.fields, now=now)
        crop = HomeFields.crop_for(state.home.data, field_id)
        if not crop:
            logger.info("[CMD] instant complete field {}: empty".format(
                field_id))
            state.save()
            return False
        if HomeFields.is_ready(state.home.data, field_id, now):
            logger.info("[CMD] instant complete field {}: already ready".format(
                field_id))
            state.save()
            return False
        row = self.data_row(crop)
        base_price = row.i("InstantComplete", 0) if row is not None else 0
        grow_time = row.seconds() if row is not None else 0
        cost = self.instant_complete_price(
            base_price, HomeFields.seconds_left(
                state.home.data, field_id, now), grow_time)
        if cost <= 0:
            state.save()
            return False
        if not self.spend_diamonds(state, cost):
            state.save()
            return False
        HomeFields.set_ready(state.home.data, field_id, crop)
        state.home.fields.set(
            field_id, Field(crop=crop, state=Field.READY,
                            planted=0, ready=0))
        logger.info("[CMD] instant complete field {}".format(field_id))
        state.save()
        return True
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
