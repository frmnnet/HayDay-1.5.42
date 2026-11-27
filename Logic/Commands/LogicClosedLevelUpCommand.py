from Utils.Logging import logger
from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand


class LogicClosedLevelUpCommand(LogicCommand):
    """Acknowledge a level-up popup.

    Level rewards are already emitted from ``exp_levels.csv`` by
    ``LogicCommand.earn_exp``.  The old fixed 500-cash/10-diamond payment here
    duplicated those rewards and allowed repeated profitability.
    """

    NAME = "LogicClosedLevelUpCommand"
    TYPE = 33
    FIELDS = ['short', 'tick']

    def execute(self, state):
        level = int(self.arg(0, 0))
        current = int(getattr(state.account, "exp_level", 1) or 1)
        if level <= 0 or level > current:
            logger.info("[CMD] level-up acknowledgement {} invalid (level {})"
                        .format(level, current))
            return False
        state.home.data["LastClosedLevelUp"] = level
        logger.info("[CMD] acknowledged level {}".format(level))
        state.save()
        return True
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
