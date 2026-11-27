from Utils.Writer import Writer
from Packets.MessageIds import message_id


class GetFollowingListMessage(Writer):

    def __init__(self, device):
        super().__init__(device)
        self.device = device
        self.id = message_id("GetFollowingListMessage")

    def encode(self):
        pass
