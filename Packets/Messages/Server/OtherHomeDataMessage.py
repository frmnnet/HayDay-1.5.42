from contextlib import ExitStack

from Logic.AIAvatar import encode as encode_ai_avatar
from Logic.ClientAvatar import LogicClientAvatar
from Logic.GameData import GameData
from Logic.GameTime import now_seconds
from Logic.GameState import GameState
from Logic import Newspaper, RoadsideStand
from Packets.MessageIds import message_id
from Utils.Storage import load_config
from Utils.Writer import Writer


class OtherHomeDataMessage(Writer):

    def __init__(self, device, seller=None):
        super().__init__(device)
        self.device = device
        self.id = message_id("OtherHomeDataMessage")
        self.seller = dict(seller or {})

    def encode(self):
        seller = self.seller
        seller_high = int(seller.get("High") or 0)
        seller_low = int(seller.get("Low") or 0)
        seller_state = seller.get("State")
        own_state = GameState.for_device(self.device)

        states = {own_state.key: own_state}
        if seller_state is not None:
            states[seller_state.key] = seller_state
        with ExitStack() as stack:
            for key in sorted(states):
                stack.enter_context(states[key].lock)

            if seller_state is None:
                home_json = Newspaper.synthetic_home(
                    seller.get("Ads") or [])
            else:
                RoadsideStand.ensure(
                    seller_state.home.data,
                    seller_state.account.exp_level)
                seller_state.save()
                home_json = seller_state.home.to_json()

            if len(home_json.encode("utf-8")) > 900000:
                raise ValueError(
                    "seller {}:{} home exceeds 900000 bytes".format(
                        seller_high, seller_low))

            self.writeString(home_json)
            LogicClientAvatar(
                load_config(own_state.account),
                GameData.instance(),
                own_state,
            ).encode(self)

            if seller_state is None:
                encode_ai_avatar(
                    self,
                    GameData.instance(),
                    Newspaper.synthetic_avatar(),
                    seller_high,
                    seller_low,
                    str(seller.get("Name") or "Greg"),
                )
            else:
                LogicClientAvatar(
                    load_config(seller_state.account),
                    GameData.instance(),
                    seller_state,
                ).encode(self)
            self.writeInt(now_seconds())

            if seller_state is not None:
                seller_state.flush()
