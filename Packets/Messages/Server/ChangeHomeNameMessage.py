from Utils.Writer import Writer
from Packets.MessageIds import message_id


class ChangeHomeNameMessage(Writer):

    def __init__(self, device):
        super().__init__(device)
        self.device = device
        self.id = message_id("ChangeHomeNameMessage")

    def encode(self):
        pass
