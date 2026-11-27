from Utils.Reader import Reader


class BuyFromStandResponseMessage(Reader):

    ID = 24103
    def __init__(self, data, device):
        super().__init__(data)
        self.device = device

    def decode(self):
        pass

    def process(self):
        pass
