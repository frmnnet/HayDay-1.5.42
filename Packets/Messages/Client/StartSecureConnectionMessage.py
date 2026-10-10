import os
from Utils.Reader import Reader
from Packets.Messages.Server.SecureConnectionOkMessage import SecureConnectionOkMessage


class StartSecureConnectionMessage(Reader):

    def __init__(self, data, device):
        super().__init__(data)
        self.device = device

    def decode(self):
        pass

    def process(self):
        nonce = os.urandom(12).hex()
        SecureConnectionOkMessage(self.device, nonce).Send()
        self.device.EnableCrypto(nonce.encode())
