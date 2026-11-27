from Utils.Logging import logger
from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import HomeObjects


class LogicMoveObjectCommand(LogicCommand):
    """Move an object (f0=object id, f1/f2=delta in 1/512 tile units, tick).

    ``LogicMoveObjectCommand::execute`` calls
    ``moveTo(accurateX + f1, accurateY + f2)`` and the game then divides by
    512 to get a tile.  Storing the raw values produced bogus positions like
    ``[3, 4227858452]`` in the saved farm.
    """

    NAME = "LogicMoveObjectCommand"
    TYPE = 3
    FIELDS = ['int', 'int', 'int', 'tick']

    def execute(self, state):
        obj = self.f0
        entry = HomeObjects.move(state.home.data, obj, self.f1, self.f2)
        if entry is None:
            logger.info("[CMD] move object {}: no such runtime object".format(obj))
            return False
        logger.info(
            "[CMD] move object runtime={} delta=({},{}) "
            "accurate=({},{}) tile=({},{})".format(
                obj, self.f1, self.f2,
                entry.get("_AccurateX"), entry.get("_AccurateY"),
                entry.get("X"), entry.get("Y")))
        state.save()
        return True

    def decode(self):
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
