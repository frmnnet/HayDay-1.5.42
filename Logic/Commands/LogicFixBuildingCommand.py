from Utils.Logging import logger
from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import HomeObjects


class LogicFixBuildingCommand(LogicCommand):
    """Repair one broken part of a building (f0=object id, f1=part index).

    ``LogicFixBuildingCommand::execute`` calls ``fixPart(f1)``; once
    ``isBroken()`` returns false the building switches to its finished,
    coloured export (the house "achievement" appearance).  The saved farm
    stores this as the ``BrokenParts`` list on the placed object.
    """

    NAME = "LogicFixBuildingCommand"
    TYPE = 25
    FIELDS = ['int', 'byte', 'tick']

    def execute(self, state):
        obj = self.f0
        part = int(self.f1)
        _index, target = HomeObjects.find_by_runtime_id(state.home.data, obj)
        if target is None:
            logger.info("[CMD] fix building {}: object not found".format(obj))
            state.save()
            return False

        parts = target.get("BrokenParts")
        fixed = False
        if isinstance(parts, list) and 0 <= part < len(parts):
            fixed = bool(parts[part])
            parts[part] = False
            target["BrokenParts"] = parts
            if not any(bool(p) for p in parts):
                # Nothing broken -> the client uses the completed (coloured)
                # export name for this building.
                target.pop("BrokenParts", None)
        if fixed:
            # LogicFixBuildingCommand::execute adds one unit of the
            # building-fix EXP resource after a successful fixPart.
            self.earn_exp(
                state, max(1, self.data.config_int("BuildingFixExp", 1)))

        complete = "BrokenParts" not in target
        if complete:
            state.home.data.setdefault(
                "BuildingUpgrades", {}).setdefault(
                    str(obj), {})["Fixed"] = True
        logger.info("[CMD] fix building {} part {} (complete={})".format(
            obj, part, "BrokenParts" not in target))
        state.save()
        return True

    def decode(self):
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
