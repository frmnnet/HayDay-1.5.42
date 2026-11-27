from Utils.Reader import Reader


class AvatarInfoRequestMessage(Reader):

    ID = 10102
    def __init__(self, data, device):
        super().__init__(data)
        self.device = device

    def decode(self):
        pass

    def process(self):
        pass
