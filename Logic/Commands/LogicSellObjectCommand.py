from Utils.Logging import logger
from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import HomeObjects


class LogicSellObjectCommand(LogicCommand):
    """Store/sell an object back into inventory (f0 = runtime object id).

    In the client this command calls ``removeGameObject`` and a vtable
    "store object" method; no coins are paid by the command itself.
    """

    NAME = "LogicSellObjectCommand"
    TYPE = 54
    FIELDS = ['int', 'tick']

    def execute(self, state):
        obj = self.arg(0, 0)
        found = HomeObjects.remove(state.home.data, obj)
        if found is None:
            logger.info("[CMD] sell object {}: not placed on farm".format(obj))
            state.save()
            return False
        self.give(state, found.get("ID", obj), 1)
        logger.info("[CMD] sell/stored object {} ({} left placed)".format(
            obj, len(state.home.data.get("Objects", []))))
        state.save()
        return True

    def decode(self):
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
