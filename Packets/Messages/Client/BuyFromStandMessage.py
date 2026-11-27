from Utils.Reader import Reader
from Utils.Logging import logger
from Logic.GameState import GameState
from Logic import Newspaper
from Packets.Messages.Server.BuyFromStandResponseMessage import (
    BuyFromStandResponseMessage,
)


class BuyFromStandMessage(Reader):

    ID = 14110
    def __init__(self, data, device):
        super().__init__(data)
        self.device = device

    def decode(self):
        self.stand_index = self.readInt()
        self.verify_data = self.readInt()
        self.verify_amount = self.readInt()
        self.verify_price = self.readInt()
        self.coins_and_diamonds = self.readBool()
        logger.info(
            "[NEWSPAPER] buy request index={} data={} amount={} price={}"
            .format(
                self.stand_index, self.verify_data,
                self.verify_amount, self.verify_price))

    def process(self):
        state = GameState.for_device(self.device)
        seller = self.device.visiting_seller
        if seller is None:
            logger.info("[NEWSPAPER] buy rejected outside a visited home")
            response = {
                "Response": 1,
                "Data": self.verify_data,
                "Price": self.verify_price,
                "Amount": self.verify_amount,
                "Stand": self.stand_index,
                "DiamondPrice": 0,
            }
            BuyFromStandResponseMessage(self.device, response).Send()
            return
        success, response = Newspaper.buy(
            state, seller[0], seller[1], self.stand_index,
            self.verify_data, self.verify_amount, self.verify_price,
            self.coins_and_diamonds)
        if not success:
            logger.info(
                "[NEWSPAPER] buy rejected code={}".format(
                    response.get("Response")))
        BuyFromStandResponseMessage(self.device, response).Send()
