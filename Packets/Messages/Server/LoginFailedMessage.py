from Utils.Writer import Writer


class LoginFailedMessage(Writer):

    def __init__(self, device, code=10, reason=""):
        super().__init__(device)
        self.device = device
        self.id = 20103
        self.code = code
        self.reason = reason

    def encode(self):
        self.writeInt(self.code)
        self.writeString(self.reason)
        self.writeString()  # resourceFingerprintData
