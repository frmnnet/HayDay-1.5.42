from Utils.Logging import logger
from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import HomeTimers


class LogicUpdateTimersCommand(LogicCommand):
    """Advance all farm timers (fields, productions, animals)."""

    NAME = "LogicUpdateTimersCommand"
    TYPE = 38
    FIELDS = ['int', 'tick']

    def execute(self, state):
        now = self.now
        result = HomeTimers.sync(
            state, now=now, spawn_mystery=True)
        logger.info(
            "[CMD] update timers: {} field(s) ready, {} production(s) ready"
            .format(
                result["fields_ready"],
                result["productions_ready"]))
        state.save()
        return True
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
