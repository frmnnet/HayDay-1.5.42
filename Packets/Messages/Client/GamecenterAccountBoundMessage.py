from Utils.Reader import Reader


class GamecenterAccountBoundMessage(Reader):

    ID = 24211
    def __init__(self, data, device):
        super().__init__(data)
        self.device = device

    def decode(self):
        pass

    def process(self):
        pass
