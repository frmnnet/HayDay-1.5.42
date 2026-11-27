from Utils.Logging import logger
from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import HomeFields


class LogicPlantSeedsCommand(LogicCommand):
    """Plant a crop on a field tile.

    Real layout (``LogicPlantSeedsCommand::execute``)::

        f0 = field game object id
        f1 = crop data global id (fields.csv instance)

    Grow time, unlock level and the seed consumed all come from the game's
    ``fields.csv`` table.
    """

    NAME = "LogicPlantSeedsCommand"
    TYPE = 1
    FIELDS = ['int', 'int', 'tick']

    def execute(self, state):
        now = self.now
        field_id = self.f0
        crop = self.f1
        row = self.data_row(crop)

        if row is None or HomeFields.entry_for(
                state.home.data, field_id) is None:
            logger.info("[CMD] plant field={} crop={}: invalid field/crop".format(
                field_id, crop))
            state.save()
            return False
        if not self.require_unlock(state, row):
            state.save()
            return False
        if HomeFields.crop_for(state.home.data, field_id):
            logger.info("[CMD] plant field={}: field is occupied".format(
                field_id))
            state.save()
            return False

        if not state.home.inventory.has(crop, 1):
            logger.info("[CMD] plant field={}: crop {} not in inventory"
                        .format(field_id, crop))
            state.save()
            return False
        self.take(state, crop, 1)

        grow_time = row.seconds()
        if grow_time <= 0:
            logger.info("[CMD] plant field={}: invalid grow time".format(
                field_id))
            state.save()
            return False
        field = state.home.fields.plant(
            field_id, crop, grow_time=grow_time, now=now)
        HomeFields.set_growing(
            state.home.data, field_id, crop,
            total_seconds=grow_time, ready_at=field.ready, now=now)
        logger.info("[CMD] plant field={} crop={} grow={}s".format(
            field_id, crop, grow_time))
        state.save()
        return True

    def decode(self):
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
