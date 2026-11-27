from Utils.Reader import Reader


class NotifyOnBoatHelpRequestedMessage(Reader):

    ID = 20111
    def __init__(self, data, device):
        super().__init__(data)
        self.device = device

    def decode(self):
        pass

    def process(self):
        pass
