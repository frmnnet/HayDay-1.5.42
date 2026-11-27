from Utils.Writer import Writer


class FollowerCountMessage(Writer):
    """Server reply to ``GetFollowerCountMessage`` (id 24116).

    Wire layout (from ``FollowerCountMessage::encode``)::

        int32   follower count
        int32   avatar high id
        int32   avatar low id
    """

    ID = 24116

    def __init__(self, device, count=0, high=0, low=0):
        super().__init__(device)
        self.device = device
        self.id = self.ID
        self.count = int(count)
        self.high = int(high)
        self.low = int(low)

    def encode(self):
        self.writeInt(self.count)
        self.writeInt(self.high)
        self.writeInt(self.low)
