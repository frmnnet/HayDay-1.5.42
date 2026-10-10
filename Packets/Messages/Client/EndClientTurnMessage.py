from Utils.Reader import Reader
from Packets.Messages.Server.EndClientTurnOkMessage import EndClientTurnOkMessage


class EndClientTurnMessage(Reader):

    def __init__(self, data, device):
        super().__init__(data)
        self.device = device

    def decode(self):
        pass

    def process(self):
        EndClientTurnOkMessage(self.device).Send()
