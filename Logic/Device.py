from Utils.Logging import logger
from CryptoRC4.Crypto import CryptoRc4
from threading import RLock


class Device:

    _online = set()
    _online_lock = RLock()

    def __init__(self, socket=None):
        self.socket = socket
        self.crypto = None
        self._send_lock = RLock()
        # Account identity, filled in by LoginMessage: the state of whichever
        # player this connection belongs to is looked up through these.
        self.account = None
        self.high_id = None
        self.low_id = None
        # Set after VisitHomeMessage succeeds and cleared when returning home.
        # BuyFromStandMessage carries only a slot in this visited farm.
        self.visiting_seller = None

    def register_online(self):
        if self.high_id is None or self.low_id is None:
            return
        with self._online_lock:
            self._online.add(self)

    def unregister_online(self):
        with self._online_lock:
            self._online.discard(self)

    @classmethod
    def online_for_account(cls, high_id, low_id):
        key = (int(high_id), int(low_id))
        with cls._online_lock:
            return [
                device for device in cls._online
                if (device.high_id, device.low_id) == key
            ]

    @property
    def account_id(self):
        if self.high_id is None or self.low_id is None:
            return None
        return (self.high_id << 32) | (self.low_id & 0xFFFFFFFF)

    def EnableCrypto(self, nonce: bytes):
        self.crypto = CryptoRc4(nonce)

    def SendData(self, ID, data, version=None):
        from Utils.PacketCapture import record as capture_packet
        with self._send_lock:
            capture_packet("S2C", ID, data, version or 0)
            payload = self.crypto.encrypt(data) if self.crypto else data
            packet = ID.to_bytes(2, 'big') + len(payload).to_bytes(3, 'big') + (version or 0).to_bytes(2, 'big') + payload
            self.socket.send(packet)
        logger.info('[*] {} sent ({} bytes)'.format(ID, len(payload)))

    def decrypt(self, data):
        return self.crypto.decrypt(data) if self.crypto else data
