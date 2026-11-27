from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import HomeObjects


class LogicStoreObjectCommand(LogicCommand):
    """Move a placed object into storage without paying coins."""

    NAME = "LogicStoreObjectCommand"
    TYPE = 93
    FIELDS = ['int', 'tick']

    def execute(self, state):
        found = HomeObjects.remove(state.home.data, self.f0)
        if found is None:
            state.save()
            return False
        self.give(state, found.get("ID"), 1)
        state.save()
        return True
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
