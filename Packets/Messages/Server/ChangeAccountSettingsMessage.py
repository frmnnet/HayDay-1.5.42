from Utils.Writer import Writer
from Packets.MessageIds import message_id


class ChangeAccountSettingsMessage(Writer):

    def __init__(self, device):
        super().__init__(device)
        self.device = device
        self.id = message_id("ChangeAccountSettingsMessage")

    def encode(self):
        pass
