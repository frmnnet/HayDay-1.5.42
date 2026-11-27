from Utils.Writer import Writer
from Utils.Storage import load_config
from Logic.ClientAvatar import LogicClientAvatar
from Logic.GameData import GameData
from Logic.GameTime import now_seconds
from Logic.GameState import GameState
from Logic import (
    Achievements, HomeObjects, HomeTimers, MysteryBoxes, RoadsideStand,
    Storage, TruckOrders, Wheel)
from Utils.Logging import logger

data = GameData()


class OwnHomeDataMessage(Writer):

    def __init__(self, device):
        super().__init__(device)
        self.device = device
        self.id = 24101

    def encode(self):
        state = GameState.for_device(self.device)
        # Snapshot the farm, avatar and account under the same per-player lock
        # used by command turns.  A reconnect can overlap a still-running turn
        # on another thread; serializing them concurrently produced a home JSON
        # from one revision and an avatar from another.
        with state.lock:
            conf = load_config(state.account)  # config + this player's values
            home = state.home  # mutable farm state (DB blob + JSON export)

            # The client regenerates object ids while this exact JSON is
            # loaded, so refresh the server's command aliases from the same
            # order immediately before serializing it.
            TruckOrders.ensure_client_objects(home.data)
            Wheel.ensure(home.data, state.account.exp_level)
            MysteryBoxes.sync(state, state.account.exp_level)
            RoadsideStand.ensure(home.data, state.account.exp_level)
            Storage.sync_rank_resources(home.data)
            HomeObjects.reset_runtime_ids(home.data)
            HomeTimers.sync(state)
            Achievements.normalize(state)
            storage = Storage.snapshot(home.data)
            logger.info(
                "[STORAGE] warehouse {}/{}, silo {}/{}"
                .format(
                    storage["warehouse"]["used"],
                    storage["warehouse"]["capacity"],
                    storage["silo"]["used"],
                    storage["silo"]["capacity"]))
            # These are durable repairs (special objects and their current
            # load-scoped ids), so let Main's packet flush persist them.
            state.save()
            self.writeInt(now_seconds())  # game-mode start time, in seconds
            self.writeString(home.to_json())  # farm
            LogicClientAvatar(conf, data, state).encode(self)
            self.writeInt(0)
