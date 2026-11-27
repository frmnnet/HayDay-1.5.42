from Utils.Reader import Reader


class BindGamecenterAccountMessage(Reader):

    ID = 14211
    def __init__(self, data, device):
        super().__init__(data)
        self.device = device

    def decode(self):
        pass

    def process(self):
        pass
