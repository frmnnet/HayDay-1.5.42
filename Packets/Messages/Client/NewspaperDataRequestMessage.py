from Utils.Reader import Reader
from Utils.Logging import logger
from Logic.GameState import GameState
from Logic import Newspaper
from Packets.Messages.Server.AdvertisementListMessage import (
    AdvertisementListMessage,
)


class NewspaperDataRequestMessage(Reader):

    ID = 14111
    def __init__(self, data, device):
        super().__init__(data)
        self.device = device

    def decode(self):
        self.exp_level = self.readInt()
        self.required_count = self.readInt()
        logger.info(
            "[NEWSPAPER] request level={} count={}".format(
                self.exp_level, self.required_count))

    def process(self):
        state = GameState.for_device(self.device)
        with state.lock:
            entries = Newspaper.refresh(
                state, self.required_count, force=False)
        AdvertisementListMessage(self.device, entries).Send()
