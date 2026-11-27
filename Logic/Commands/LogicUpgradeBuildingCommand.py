from Utils.Logging import logger
from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import HomeObjects, Storage


class LogicUpgradeBuildingCommand(LogicCommand):
    """Upgrade a placed building using its CSV price/material requirements."""

    NAME = "LogicUpgradeBuildingCommand"
    TYPE = 11
    FIELDS = ['int', 'tick']

    def execute(self, state):
        building = self.f0
        _index, entry = HomeObjects.find_by_runtime_id(
            state.home.data, building)
        row = self.data_row(entry.get("ID")) if entry is not None else None
        if entry is None or row is None:
            logger.info("[CMD] upgrade building {}: unknown object".format(
                building))
            state.save()
            return False

        upgrades = state.home.data.setdefault("BuildingUpgrades", {})
        key = str(entry.get("ID"))
        record = upgrades.setdefault(key, {})
        if not isinstance(record, dict):
            record = {"Level": int(record or 0)}
            upgrades[key] = record
        current = max(
            1,
            int(entry.get("Rank", 0) or 0),
            int(record.get("Level", 0) or 0),
        )
        sources = [row.values] + list(row.subs)
        if current >= len(sources):
            logger.info("[CMD] upgrade building {}: already maximum".format(
                key))
            state.save()
            return False

        source = sources[current]
        try:
            price = int(source.get("Price") or row.i("Price", 0) or 0)
        except (TypeError, ValueError):
            price = 0
        tools = []
        for column in ("CollectionTool1", "CollectionTool2", "CollectionTool3"):
            item = self.item(row.s(column))
            if item is not None:
                tools.append(item.global_id)

        if price > 0:
            if not self.spend_cash(state, price):
                state.save()
                return False
        elif tools:
            missing = [
                item_id for item_id in tools
                if not state.home.inventory.has(item_id, 1)
            ]
            if missing:
                logger.info("[CMD] upgrade building {}: missing materials {}"
                            .format(key, missing))
                state.save()
                return False
            for item_id in tools:
                self.take(state, item_id, 1)
        else:
            logger.info("[CMD] upgrade building {}: CSV has no upgrade cost"
                        .format(key))
            state.save()
            return False

        record["Level"] = current + 1
        entry["Rank"] = current + 1
        if row.tid == Storage.WAREHOUSE_TABLE:
            Storage.sync_rank_resources(state.home.data)
            record["Capacity"] = Storage.capacity(
                state.home.data, "warehouse")
            logger.info(
                "[CMD] upgrade warehouse {} -> rank {}, capacity {}".format(
                    key, current + 1, record["Capacity"]))
        elif row.tid == Storage.SILO_TABLE:
            Storage.sync_rank_resources(state.home.data)
            record["Capacity"] = Storage.capacity(state.home.data, "silo")
            logger.info(
                "[CMD] upgrade silo {} -> rank {}, capacity {}".format(
                    key, current + 1, record["Capacity"]))
        else:
            logger.info("[CMD] upgrade building {} -> rank {}".format(
                key, current + 1))
        state.save()
        return True
    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
