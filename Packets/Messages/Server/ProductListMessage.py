from Utils.Writer import Writer
from Packets.MessageIds import message_id


class ProductListMessage(Writer):

    def __init__(self, device):
        super().__init__(device)
        self.device = device
        self.id = message_id("ProductListMessage")

    def encode(self):
        pass
