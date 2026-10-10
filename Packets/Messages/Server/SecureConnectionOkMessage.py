import json
from Utils.Writer import Writer


class SecureConnectionOkMessage(Writer):

    def __init__(self, device, nonce):
        super().__init__(device)
        self.device = device
        self.nonce = nonce
        self.id = 20122

    def encode(self):
        self.writeString(self.nonce)
        self.writeString(json.load(open("config.json"))["ServerVersion"])
