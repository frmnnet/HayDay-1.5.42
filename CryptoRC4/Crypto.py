from Crypto.Cipher import ARC4 as RC4

KEY = b'gWZW0tm9Elv78dX6kX1ew3FB837yc2CSaVLlTjei4hW0'


class CryptoRc4:
    def __init__(self, nonce: bytes):
        k = KEY + nonce
        self.rx = RC4.new(k)
        self.rx.encrypt(b'\0' * len(k))
        self.tx = RC4.new(k)
        self.tx.encrypt(b'\0' * len(k))

    def decrypt(self, data):
        return self.rx.encrypt(data)

    def encrypt(self, data):
        return self.tx.encrypt(data)
