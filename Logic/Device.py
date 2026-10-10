from CryptoRC4.Crypto import CryptoRc4


class Device:

    def __init__(self, socket=None):
        self.socket = socket
        self.crypto = None

    def EnableCrypto(self, nonce: bytes):
        self.crypto = CryptoRc4(nonce)

    def SendData(self, ID, data, version=None):
        payload = self.crypto.encrypt(data) if self.crypto else data
        packet = ID.to_bytes(2, 'big') + len(payload).to_bytes(3, 'big') + (version or 0).to_bytes(2, 'big') + payload
        self.socket.send(packet)
        print('[*] {} sent ({} bytes)'.format(ID, len(payload)))

    def decrypt(self, data):
        return self.crypto.decrypt(data) if self.crypto else data
