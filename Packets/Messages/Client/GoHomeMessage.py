from Utils.Reader import Reader
from Packets.Messages.Server.OwnHomeDataMessage import OwnHomeDataMessage


class GoHomeMessage(Reader):
    ID = 14101

    def __init__(self, data, device):
        super().__init__(data)
        self.device = device

    def decode(self):
        pass

    def process(self):
        self.device.visiting_seller = None
        OwnHomeDataMessage(self.device).Send()  # send ohd
