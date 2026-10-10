from Utils.Writer import Writer


class EndClientTurnOkMessage(Writer):

    def __init__(self, device):
        super().__init__(device)
        self.device = device
        self.id = 24112

    def encode(self):
        pass
