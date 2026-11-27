from Utils.Logging import logger
"""Registry and dispatcher for Logic*Command handlers.

All command modules under ``Logic/Commands`` are discovered dynamically.
Classes that declare a numeric ``TYPE`` are registered by id; ``dispatch``
falls back to a generic logging handler for ids we have not seen yet, so
unknown commands are captured (payload hex) instead of crashing.
"""
import importlib
import pkgutil

from Logic import Commands as _cmd_pkg
from Logic.Commands.LogicCommand import LogicCommand

COMMANDS = {}       # command_type -> handler class
BY_NAME = {}        # command name -> handler class


class _GenericCommand(LogicCommand):
    """Fallback for command ids that are not registered yet."""

    NAME = "GenericCommand"

    def __init__(self, payload=b"", cmd_type=None):
        super().__init__(payload)
        self.cmd_type = cmd_type

    def execute(self, state):
        logger.info("[CMD] unknown command type={} args={} raw={}".format(
            self.cmd_type, self.args, self.raw))
        return False


def register(command_type, handler):
    COMMANDS[command_type] = handler
    BY_NAME[getattr(handler, "NAME", handler.__name__)] = handler


def get(command_type):
    return COMMANDS.get(command_type)


def get_by_name(name):
    return BY_NAME.get(name)


def dispatch(command_type, payload, state):
    """Decode + execute the handler for ``command_type`` (or the fallback)."""
    handler = COMMANDS.get(command_type)
    if handler is not None:
        cmd = handler(payload)
    else:
        cmd = _GenericCommand(payload, cmd_type=command_type)
    try:
        cmd.decode()
    except Exception as e:
        logger.info("[CMD] decode error for type={}: {}".format(command_type, e))
    try:
        return cmd.execute(state)
    except Exception as e:
        logger.info("[CMD] execute error for type={}: {}".format(command_type, e))
        return False


# ------------------------------------------------------------------ #
# Dynamic discovery of all command modules
# ------------------------------------------------------------------ #
for _modinfo in pkgutil.iter_modules(_cmd_pkg.__path__):
    if _modinfo.name == "LogicCommand":
        continue
    _module = importlib.import_module(
        "{}.{}".format(_cmd_pkg.__name__, _modinfo.name)
    )
    for _attr in dir(_module):
        _obj = getattr(_module, _attr)
        if (isinstance(_obj, type) and issubclass(_obj, LogicCommand)
                and _obj is not LogicCommand):
            register(_obj.TYPE if _obj.TYPE is not None else None, _obj)
            BY_NAME[_obj.NAME] = _obj

# TYPE is None for most commands until confirmed from logs; drop those from
# the id index but keep them in BY_NAME.
COMMANDS = {k: v for k, v in COMMANDS.items() if k is not None}
