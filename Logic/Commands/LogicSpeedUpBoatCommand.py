from Utils.Logging import logger
from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand


class LogicSpeedUpBoatCommand(LogicCommand):
    """Speed up the boat with diamonds.

    Args (best guess): diamond_cost
    """

    NAME = "LogicSpeedUpBoatCommand"
    TYPE = 58
    FIELDS = ['tick']
    DEFAULT_COST = 5

    def execute(self, state):
        boats = state.home.data.get("Boats", {})
        active = boats.get("active") if isinstance(boats, dict) else None
        if not isinstance(active, dict) or active.get("Completed"):
            logger.info("[CMD] speed up boat: no active boat")
            state.save()
            return False
        cost = self.DEFAULT_COST
        if not self.spend_diamonds(state, cost):
            state.save()
            return False
        active["Ready"] = self.now
        active["SpeededUp"] = True
        logger.info("[CMD] speed up boat for {} diamonds".format(cost))
        state.save()
        return True
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
