from Utils.Logging import logger
from Utils.Reader import Reader
from Packets.Messages.Server.LoginOkMessage import LoginOkMessage
from Packets.Messages.Server.LoginFailedMessage import LoginFailedMessage
from Logic.Account import Account, read_config
from Utils.Database import Database


class LoginMessage(Reader):
    ID = 10101

    def __init__(self, data, device):
        super().__init__(data)
        self.device = device
        self.account_id = 0
        self.pass_token = ""
        self.resource_sha = ""

    def decode(self):
        # Each field is read on its own: a short/legacy packet must not leave
        # an attribute missing (that used to raise in process()).
        try:
            self.account_id = self.readInt(8)
        except Exception:
            self.account_id = 0
        for attr in ("pass_token", "resource_sha"):
            try:
                value = self.readString()
            except Exception:
                value = ""
            setattr(self, attr, value or "")
        logger.info("[*] login id={} token={!r} sha={}".format(
            self.account_id, self.pass_token, self.resource_sha))

    def process(self):
        conf = read_config()
        if conf.get("Maintenance"):
            LoginFailedMessage(self.device, 10, "Maintenance").Send()
            return

        account = self._resolve_account(conf)
        self.device.account = account
        self.device.high_id = account.high_id
        self.device.low_id = account.low_id
        self.device.register_online()
        logger.info("[LOGIN] {} -> account {}:{} ({!r})".format(
            self.device.socket.getpeername()[0]
            if self.device.socket else "?",
            account.high_id, account.low_id, account.name))
        LoginOkMessage(self.device).Send()

    def _resolve_account(self, conf):
        """Pick the account row this connection plays.

        ``accountId`` is the 64-bit id the server handed out earlier
        (``high_id << 32 | low_id``).  The rules are deliberately forgiving:

        * **known id** -> that row (recreated from config if the database was
          restored from an older/emptier backup, so the player still gets a
          farm instead of a login failure);
        * **no id yet** -> the configured account on a brand new server
          (first run keeps working exactly as before), otherwise a brand new
          row so a second device cannot overwrite the first player's farm.
        """
        db = Database.instance()
        token = self.pass_token or conf.get("PassToken", "hayday")
        high_id = conf.get("AccountHighID", 0)
        low_id = conf.get("AccountLowID", 1)

        if self.account_id:
            resolved_high = self.account_id >> 32
            resolved_low = self.account_id & 0xFFFFFFFF
            row = db.get_account(resolved_high, resolved_low)
            if row is None:
                logger.info("[LOGIN] unknown account {}:{} -> seeding it".format(
                    resolved_high, resolved_low))
                return Account.get_or_create(resolved_high, resolved_low,
                                             pass_token=token, db=db)
            account = Account.from_row(row, db=db)
            if self.pass_token and account.pass_token \
                    and self.pass_token != account.pass_token:
                logger.warning(
                    "[LOGIN] pass token mismatch for {}:{} (sent {!r}, stored "
                    "{!r}) - accepting anyway".format(
                        resolved_high, resolved_low,
                        self.pass_token, account.pass_token))
            return account

        if conf.get("AssignNewAccounts", True):
            if db.get_account(high_id, low_id) is None:
                # Very first run: seed the configured account like before.
                return Account.load(db=db)
            return Account.allocate(db=db, pass_token=token)
        return Account.load(db=db)
