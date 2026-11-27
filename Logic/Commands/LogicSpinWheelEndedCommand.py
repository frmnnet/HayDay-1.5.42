from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import Wheel
from Utils.Logging import logger


class LogicSpinWheelEndedCommand(LogicCommand):
    """Handler for LogicSpinWheelEndedCommand."""

    NAME = "LogicSpinWheelEndedCommand"
    TYPE = 80
    ACTION = "wheel_end"
    FIELDS = ['tick']

    def execute(self, state):
        reward = Wheel.grant_pending(self, state)
        if reward is None:
            state.save()
            return False
        logger.info("[CMD] wheel ended -> {}".format(reward))
        state.save()
        return True
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
