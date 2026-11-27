from Utils.Logging import logger
from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import HomeObjects


class LogicMirrorObjectCommand(LogicCommand):
    """Mirror/rotate an object in place.

    Args (best guess): object_id, orientation
    """

    NAME = "LogicMirrorObjectCommand"
    TYPE = 53
    FIELDS = ['int', 'tick']

    def execute(self, state):
        obj = self.arg(0, 0)
        entry = HomeObjects.mirror(state.home.data, obj)
        if entry is None:
            logger.info("[CMD] mirror object {}: no such runtime object".format(obj))
            return False
        logger.info("[CMD] mirror object {} -> {}".format(
            obj, bool(entry.get("Mirrored"))))
        state.save()
        return True
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
