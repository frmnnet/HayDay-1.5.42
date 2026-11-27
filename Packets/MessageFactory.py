import importlib
import os
import pkgutil

from Packets.Messages import Client as _client_pkg

availablePackets = {}

# Dynamically discover all client message modules and register any that
# declare a (non-None) integer ``ID`` class attribute. This keeps the
# factory in sync with the message modules without manual edits.
for _modinfo in pkgutil.iter_modules(_client_pkg.__path__):
    _module = importlib.import_module(
        "{}.{}".format(_client_pkg.__name__, _modinfo.name)
    )
    for _attr in dir(_module):
        _obj = getattr(_module, _attr)
        if isinstance(_obj, type) and getattr(_obj, "ID", None) is not None:
            try:
                availablePackets[int(_obj.ID)] = _obj
            except (TypeError, ValueError):
                pass

# Backwards-compatible explicit names (optional convenience).
try:
    from Packets.Messages.Client.StartSecureConnectionMessage import StartSecureConnectionMessage
    from Packets.Messages.Client.LoginMessage import LoginMessage
    from Packets.Messages.Client.GoHomeMessage import GoHomeMessage
    from Packets.Messages.Client.EndClientTurnMessage import EndClientTurnMessage
    from Packets.Messages.Client.VisitAIMessage import VisitAIMessage
except Exception:
    pass
