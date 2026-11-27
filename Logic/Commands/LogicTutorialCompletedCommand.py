from Utils.Logging import logger
from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic.GameData import tutorial_instance
from Logic.Tutorials import complete, next_instance, requirement_met

TUTORIAL_TABLE = 36


class LogicTutorialCompletedCommand(LogicCommand):
    """Complete one tutorial step (f0 = tutorial data global id).

    The client sets a bit in the tutorial bitlist for the tutorial's CSV
    instance id; we mirror that here and persist completed ids so progress
    survives a reconnect.
    """

    NAME = "LogicTutorialCompletedCommand"
    TYPE = 34
    FIELDS = ['int', 'tick']

    def execute(self, state):
        gid = self.f0
        instance = tutorial_instance(gid)
        if instance is None:
            state.save()
            return False
        row = self.data.row(TUTORIAL_TABLE, instance)
        if row is None or not requirement_met(state.home, self.data, row):
            logger.info("[CMD] tutorial {} rejected: prerequisite incomplete"
                        .format(instance))
            state.save()
            return False

        newly, completed = complete(state.home, self.data, instance)
        if not newly:
            # Replayed/duplicate commands are successful no-ops.  In
            # particular they must not grant the tutorial good reward twice.
            state.save()
            return True

        # Per-step progress is mirrored into the avatar bit list.  Do NOT
        # flip the global "tutorial finished" flag here: the patched client
        # crashes on the next home load when every tutorial bit is set.  The
        # last bit is deliberately left clear by LogicClientAvatar.encode.
        total = self.data.count(TUTORIAL_TABLE)
        next_id = next_instance(completed, self.data, state.account.exp_level)
        state.home.data["TutorialStarted"] = next_id
        state.home.data["TutorialNext"] = next_id
        state.save()
        for completed_id in newly:
            tutorial = self.data.row(TUTORIAL_TABLE, completed_id)
            if tutorial is None:
                continue
            reward = tutorial.get("GoodReward")
            amount = tutorial.i("GoodAmount", 0) or 1
            key = str(reward or "").strip().lower()
            if key == "cash":
                self.earn_cash(state, amount)
            elif key in ("freediamonds", "diamonds"):
                self.earn_diamonds(state, amount)
            elif reward:
                self.give_named(state, reward, amount)

        logger.info("[CMD] tutorial step {} (gid {}) completed {}: {}/{}".format(
            instance, gid, newly, len(completed), total))
        state.save()
        return True

    def decode(self):
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
