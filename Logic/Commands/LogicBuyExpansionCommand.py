from Utils.Logging import logger
from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import Achievements


class LogicBuyExpansionCommand(LogicCommand):
    """Buy a land expansion (f0 = expansions.csv global id).

    ``LogicBuyExpansionCommand::execute`` does *not* charge coins: it spends
    the expansion materials listed in ``expansions.csv`` (``CollectionTool``
    / ``CollectionToolAmount`` on the row and its continuation rows).
    """

    NAME = "LogicBuyExpansionCommand"
    TYPE = 90
    FIELDS = ['int', 'tick']

    def execute(self, state):
        expansion = self.arg(0, 0)
        row = self.data_row(expansion)
        if row is None or row.tid != 80:
            logger.info("[CMD] buy expansion {}: unknown row".format(expansion))
            state.save()
            return False
        if not self.require_unlock(state, row):
            state.save()
            return False

        required = []
        for source in [row.values] + row.subs:
            name = source.get("CollectionTool")
            if not name:
                continue
            try:
                amount = int(str(
                    source.get("CollectionToolAmount") or 0).strip() or 0)
            except (TypeError, ValueError):
                amount = 0
            item = self.item(name)
            if item is None or amount <= 0:
                continue
            if not self.require_unlock(state, item):
                state.save()
                return False
            required.append((item.global_id, amount, name))
        if not required:
            logger.info("[CMD] buy expansion {}: no materials in CSV".format(
                expansion))
            state.save()
            return False
        missing = [
            (name, amount, state.home.inventory.amount(item))
            for item, amount, name in required
            if not state.home.inventory.has(item, amount)
        ]
        if missing:
            logger.info(
                "[CMD] buy expansion {}: missing {}".format(
                    expansion,
                    ", ".join("{} {}/{}".format(name, have, amount)
                              for name, amount, have in missing)))
            state.save()
            return False

        spent = 0
        for item, amount, _name in required:
            self.take(state, item, amount)
            spent += amount

        expansions = state.home.data.setdefault("Expansions", [])
        if expansion not in expansions:
            expansions.append(expansion)
            Achievements.record(state, "Expansion")
        logger.info("[CMD] buy expansion {} for {} material(s)".format(
            expansion, spent))
        state.save()
        return True

    def decode(self):
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
