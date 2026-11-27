from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand


class LogicGetMovieTicketFinishedRewardCommand(LogicCommand):
    """Handler for LogicGetMovieTicketFinishedRewardCommand."""

    NAME = "LogicGetMovieTicketFinishedRewardCommand"
    TYPE = 77
    ACTION = "movie_finished"
    FIELDS = ['tick']

    def execute(self, state):
        return super().execute(state)
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
