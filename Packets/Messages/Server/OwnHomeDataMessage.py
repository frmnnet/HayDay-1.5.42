import json
from Utils.Writer import Writer
from Logic.ClientAvatar import LogicClientAvatar
from Logic.GameData import GameData

conf = json.load(open("config.json"))
data = GameData()
home = open(conf["HomeFile"]).read()


class OwnHomeDataMessage(Writer):

    def __init__(self, device):
        super().__init__(device)
        self.device = device
        self.id = 24101

    def encode(self):
        self.writeInt(0)  # startTime
        self.writeString(home)  # farm
        LogicClientAvatar(conf, data).encode(self)
        self.writeInt(0)
