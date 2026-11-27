from Utils.Writer import Writer
from Packets.MessageIds import message_id


class BuyFromStandResponseMessage(Writer):

    def __init__(self, device, response=None):
        super().__init__(device)
        self.device = device
        self.id = message_id("BuyFromStandResponseMessage")
        self.response = dict(response or {})

    def encode(self):
        response = self.response
        self.writeInt(int(response.get("Response", 1)))

        buyer_high = int(response.get("BuyerHigh") or 0)
        buyer_low = int(response.get("BuyerLow") or 0)
        has_buyer = bool(buyer_high or buyer_low)
        self.writeBoolean(has_buyer)
        if has_buyer:
            self.writeLong(buyer_high, buyer_low)

        seller_high = int(response.get("SellerHigh") or 0)
        seller_low = int(response.get("SellerLow") or 0)
        has_seller = bool(seller_high or seller_low)
        self.writeBoolean(has_seller)
        if has_seller:
            self.writeLong(seller_high, seller_low)

        self.writeInt(int(response.get("Data") or 0))
        self.writeInt(int(response.get("Price") or 0))
        self.writeInt(int(response.get("Amount") or 0))
        self.writeInt(int(response.get("Stand") or 0))
        self.writeInt(int(response.get("DiamondPrice") or 0))
