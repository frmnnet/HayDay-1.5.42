from Utils.Reader import Reader


class TargetHomeListMessage(Reader):

    ID = 24105
    def __init__(self, data, device):
        super().__init__(data)
        self.device = device

    def decode(self):
        pass

    def process(self):
        pass
