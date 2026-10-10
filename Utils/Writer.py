class Writer:

    def __init__(self, device, endian: str = 'big'):
        self.buffer = b''
        self.endian = endian

    def writeByte(self, data):
        self.writeInt(data, 1)

    def writeInt(self, data, length=4):
        self.buffer += data.to_bytes(length, 'big')

    def writeUInteger(self, integer: int, length: int = 1):
        self.buffer += integer.to_bytes(length, self.endian, signed=False)
        
    def writeUInt8(self, integer: int):
        self.writeUInteger(integer)
        
    def writeVint(self, data):

        rotate = True
        final = b''
        if data == 0:
            self.writeByte(0)

        else:
            data = (data << 1) ^ (data >> 31)
            while data:
                b = data & 0x7f

                if data >= 0x80:
                    b |= 0x80

                if rotate:

                    rotate = False
                    lsb = b & 0x1
                    msb = (b & 0x80) >> 7
                    b >>= 1
                    b = b & ~(0xC0)
                    b = b | (msb << 7) | (lsb << 6)

                final += b.to_bytes(1, 'big')
                data >>= 7

        self.buffer += final

    def writeString(self, data=None):
        if data is not None:
            self.writeInt(len(data))
            self.buffer += data.encode('utf-8')
        else:
            self.writeInt(2**32 - 1)

    def writeHexa(self, data):
        if data:
            if data.startswith('0x'):
                data = data[2:]

            self.buffer += bytes.fromhex(''.join(data.split()).replace('-', ''))

    def Send(self):

        self.encode()
        if hasattr(self, 'version'):
            self.device.SendData(self.id, self.buffer, self.version)

        else:
            self.device.SendData(self.id, self.buffer)
            
    def writeDataReference(self, x, y):
        self.writeVint(x)
        self.writeVint(y)
        
    def writeBoolean(self, boolean: bool):
        if boolean:
            self.writeUInt8(1)
        else:
            self.writeUInt8(0)

    def writeLong(self, high, low):
        self.buffer += high.to_bytes(4, 'big') + low.to_bytes(4, 'big')  
