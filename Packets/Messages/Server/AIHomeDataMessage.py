import json
from Utils.Writer import Writer
from Logic.AIAvatar import encode
from Logic.GameData import GameData

conf = json.load(open("config.json"))
data = GameData()
ai = json.load(open("JSON/ai.json"))["Avatar"]  # res/data/ai.json


class AIHomeDataMessage(Writer):

    def __init__(self, device, high, low):
        super().__init__(device)
        self.device = device
        self.id = 24115
        self.high, self.low = high, low

    def encode(self):
        encode(self, data, ai, self.high, self.low, conf.get("AIName", "Greg"))
        self.writeInt(0)
