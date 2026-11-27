from Utils.Logging import logger
from Utils.Reader import Reader
from Packets.Messages.Server.AIHomeDataMessage import AIHomeDataMessage


class VisitAIMessage(Reader):
    ID = 14112

    def __init__(self, data, device):
        super().__init__(data)
        self.device = device

    def decode(self):
        self.id = self.readLong()  # AI avatar id
        logger.info('[*] visit AI id={}'.format(self.id))

    def process(self):
        AIHomeDataMessage(self.device, self.id >> 32, self.id & 0xFFFFFFFF).Send()
