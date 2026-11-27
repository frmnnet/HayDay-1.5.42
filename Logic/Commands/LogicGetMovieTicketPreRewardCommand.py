from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand


class LogicGetMovieTicketPreRewardCommand(LogicCommand):
    """Handler for LogicGetMovieTicketPreRewardCommand."""

    NAME = "LogicGetMovieTicketPreRewardCommand"
    TYPE = 76
    ACTION = "movie_pre"
    FIELDS = ['tick']

    def execute(self, state):
        return super().execute(state)
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
