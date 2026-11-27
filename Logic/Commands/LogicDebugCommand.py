from Utils.Logging import logger
from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Utils.Storage import load_config


class LogicDebugCommand(LogicCommand):
    """Developer/debug command.

    Best guess: args are raw values applied as cheats, e.g.
    [diamonds, cash] or [diamonds, cash, exp]. Logged verbatim so the
    real format can be learned from captures.
    """

    NAME = "LogicDebugCommand"
    TYPE = 85
    FIELDS = ['int', 'int', 'tick']

    def execute(self, state):
        logger.warning(
            "[CMD] ignored destructive debug command args={} raw={}".format(
                self.args, self.raw))
        if not load_config().get("AllowDebugCommands", False):
            return False
        logger.warning(
            "[CMD] debug commands are enabled, but currency replacement is "
            "not permitted")
        return False
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
