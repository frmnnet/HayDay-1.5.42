from Utils.Writer import Writer


class ChangeHomeNameResponseMessage(Writer):
    """Reply to ``ChangeHomeNameMessage`` (id 24104).

    Payload: int32 status code (0 = success).
    """

    ID = 24104

    def __init__(self, device, status=0):
        super().__init__(device)
        self.device = device
        self.id = self.ID
        self.status = int(status)

    def encode(self):
        self.writeInt(self.status)
