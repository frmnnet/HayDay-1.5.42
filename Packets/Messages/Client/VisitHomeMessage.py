from Logic.GameState import GameState
from Logic import Newspaper
from Packets.Messages.Server.OtherHomeDataMessage import (
    OtherHomeDataMessage,
)
from Utils.Logging import logger
from Utils.Reader import Reader


class VisitHomeMessage(Reader):

    ID = 14108
    def __init__(self, data, device):
        super().__init__(data)
        self.device = device

    def decode(self):
        target_id = self.readLong()
        self.target_high = target_id >> 32
        self.target_low = target_id & 0xFFFFFFFF
        logger.info(
            "[NEWSPAPER] visit seller {}:{}".format(
                self.target_high, self.target_low))

    def process(self):
        state = GameState.for_device(self.device)
        seller = Newspaper.visit_home(
            state, self.target_high, self.target_low)
        if seller is None:
            logger.info(
                "[NEWSPAPER] seller {}:{} has no visitable home".format(
                    self.target_high, self.target_low))
            self.device.visiting_seller = None
            return
        self.device.visiting_seller = (
            self.target_high, self.target_low)
        OtherHomeDataMessage(self.device, seller).Send()
