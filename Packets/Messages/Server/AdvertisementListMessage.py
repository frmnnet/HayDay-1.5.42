from Utils.Writer import Writer
from Packets.MessageIds import message_id


class AdvertisementListMessage(Writer):

    def __init__(self, device, entries=None):
        super().__init__(device)
        self.device = device
        self.id = message_id("AdvertisementListMessage")
        self.entries = list(entries or [])

    def encode(self):
        self.writeInt(len(self.entries))
        for entry in self.entries:
            self.writeLong(
                int(entry.get("SellerHigh") or 0),
                int(entry.get("SellerLow") or 0))
            self.writeInt(int(entry.get("Data") or 0))
            self.writeInt(int(entry.get("Price") or 0))
            self.writeInt(int(entry.get("Count") or 0))
            # Reserved advertisement flag in AdvertisementEntry; the 1.5.42
            # newspaper UI does not interpret it as item state.
            self.writeInt(0)
