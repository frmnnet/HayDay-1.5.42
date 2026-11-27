from Utils.Logging import logger
from Utils.Reader import Reader
from Logic.GameState import GameState
from Packets.Messages.Server.ChangeHomeNameResponseMessage import ChangeHomeNameResponseMessage


class ChangeHomeNameMessage(Reader):
    """Client changes the farm name (id 14109).

    Wire layout: one string (int32 byte length + UTF-8 bytes) -- see
    ``ChangeHomeNameMessage::decode`` in the client binary.
    """

    ID = 14109

    def __init__(self, data, device):
        super().__init__(data)
        self.device = device
        self.home_name = ""

    def decode(self):
        try:
            self.home_name = self.readString()
        except Exception as exc:
            logger.info("[MSG] ChangeHomeName decode: {}".format(exc))

    def process(self):
        name = (self.home_name or "").strip()[:50]
        if name:
            state = GameState.for_device(self.device)
            with state.lock:
                state.account_set(name=name)
                avatar = state.home.data.setdefault("Avatar", {})
                if isinstance(avatar, dict):
                    avatar["name"] = name
                state.save()  # flushed with the rest of the turn
            logger.info("[MSG] farm renamed to {!r}".format(name))
        ChangeHomeNameResponseMessage(self.device, 0 if name else 1).Send()
