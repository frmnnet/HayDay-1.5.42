import json
from Utils.Reader import Reader
from Packets.Messages.Server.LoginOkMessage import LoginOkMessage
from Packets.Messages.Server.LoginFailedMessage import LoginFailedMessage


class LoginMessage(Reader):

    def __init__(self, data, device):
        super().__init__(data)
        self.device = device

    def decode(self):
        try:
            self.accountId = self.readInt(8)
            self.passToken = self.readString()
            self.resourceSha = self.readString()
            print('[*] login id={} sha={}'.format(self.accountId, self.resourceSha))
        except Exception:
            pass

    def process(self):
        if json.load(open("config.json")).get("Maintenance"):
            LoginFailedMessage(self.device, 10, "Maintenance").Send()
        else:
            LoginOkMessage(self.device).Send()