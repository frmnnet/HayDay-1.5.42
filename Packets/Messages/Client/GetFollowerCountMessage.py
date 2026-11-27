from Utils.Logging import logger
from Utils.Reader import Reader
from Packets.Messages.Server.FollowerCountMessage import FollowerCountMessage


class GetFollowerCountMessage(Reader):
    """Client asks for the follower count of an avatar (id 14120).

    Payload is a ``LogicLong`` serialized as two int32 values (high, low)
    -- see ``LogicLong::decode`` in the client binary.
    """

    ID = 14120

    def __init__(self, data, device):
        super().__init__(data)
        self.device = device
        self.high = 0
        self.low = 0

    def decode(self):
        try:
            self.high = self.readInt()
            self.low = self.readInt()
        except Exception as exc:
            logger.info("[MSG] GetFollowerCount decode: {}".format(exc))

    def process(self):
        # This private server has no social graph; report zero followers for
        # the requested avatar.
        FollowerCountMessage(self.device, 0, self.high, self.low).Send()
