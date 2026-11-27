from Utils.Writer import Writer
from Logic.Account import read_config


class LoginOkMessage(Writer):

    def __init__(self, device):
        super().__init__(device)
        self.device = device
        self.id = 20104

    def encode(self):
        # Echo the account the login actually resolved to, so the client
        # stores it and the next login lands on the same farm.
        account = getattr(self.device, "account", None)
        if account is not None:
            high_id, low_id = account.high_id, account.low_id
            token = account.pass_token
        else:
            conf = read_config()
            high_id = conf.get("AccountHighID", 0)
            low_id = conf.get("AccountLowID", 1)
            token = conf.get("PassToken", "hayday")

        for _ in range(3):
            self.writeInt(high_id)
            self.writeInt(low_id)
        self.writeString(token)
        self.writeString()  # facebookId
        self.writeString()  # gameCenterId
        self.writeInt(1)    # sessionCount
        self.writeInt(0)    # playTimeSeconds
        self.writeInt(0)    # unknown
