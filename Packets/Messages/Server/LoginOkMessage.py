import json
from Utils.Writer import Writer


class LoginOkMessage(Writer):

    def __init__(self, device):
        super().__init__(device)
        self.device = device
        self.id = 20104

    def encode(self):
        c = json.load(open("config.json"))
        for _ in range(3):
            self.writeInt(c['AccountHighID']); self.writeInt(c['AccountLowID'])
        self.writeString(c['PassToken'])
        self.writeString()  # facebookId
        self.writeString()  # gameCenterId
        self.writeInt(1)    # sessionCount
        self.writeInt(0)    # playTimeSeconds
        self.writeInt(0)    # unknown
