from Utils.Writer import Writer
from Packets.MessageIds import message_id


class NotifyOnSaleMessage(Writer):

    def __init__(self, device):
        super().__init__(device)
        self.device = device
        self.id = message_id("NotifyOnSaleMessage")
        self.seller_high = 0
        self.seller_low = 0
        self.stand_index = 0
        self.amount = 0
        self.price = 0
        self.data_id = 0

    @classmethod
    def from_sale(cls, device, seller_high, seller_low, stand_index,
                  amount, price, data_id):
        message = cls(device)
        message.seller_high = int(seller_high or 0)
        message.seller_low = int(seller_low or 0)
        message.stand_index = int(stand_index or 0)
        message.amount = int(amount or 0)
        message.price = int(price or 0)
        message.data_id = int(data_id or 0)
        return message

    def encode(self):
        # NotifyOnSaleMessage::encode order: seller id, stand, data id,
        # amount, total price.
        self.writeLong(self.seller_high, self.seller_low)
        self.writeInt(self.stand_index)
        self.writeInt(self.data_id)
        self.writeInt(self.amount)
        self.writeInt(self.price)
