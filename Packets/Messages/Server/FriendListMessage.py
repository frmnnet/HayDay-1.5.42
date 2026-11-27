from Utils.Writer import Writer
from Packets.MessageIds import message_id


class FriendListMessage(Writer):

    def __init__(self, device):
        super().__init__(device)
        self.device = device
        self.id = message_id("FriendListMessage")

    def encode(self):
        pass
