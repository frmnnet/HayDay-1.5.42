from Utils.Reader import Reader


class GamecenterAccountAlreadyBoundMessage(Reader):

    ID = 24212
    def __init__(self, data, device):
        super().__init__(data)
        self.device = device

    def decode(self):
        pass

    def process(self):
        pass
