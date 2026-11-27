from Utils.Logging import logger
from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import Achievements


class LogicClaimAchievementCommand(LogicCommand):
    """Claim an achievement reward (f0 = achievements.csv global id).

    ``achievements.csv`` stores the real ``Exp`` and ``DiamondReward``.
    """

    NAME = "LogicClaimAchievementCommand"
    TYPE = 51
    FIELDS = ['int', 'tick']

    def execute(self, state):
        achievement = self.arg(0, 0)
        row = self.data_row(achievement)
        if row is None:
            logger.info("[CMD] unknown achievement {}".format(achievement))
            return False
        diamonds = row.i("DiamondReward", 0)
        exp = row.i("Exp", 0)
        points = row.i("Points", 0)

        if Achievements.is_claimed(state.home.data, achievement):
            logger.info("[CMD] achievement {} already claimed".format(achievement))
            return False
        if not Achievements.can_claim(state, achievement):
            logger.info(
                "[CMD] achievement {} rejected: progress {}/{}".format(
                    achievement,
                    Achievements.progress_for(
                        state, row.s("Action"), row.s("ActionData")),
                    max(1, row.i("ActionCount", 1))))
            return False

        Achievements.mark_claimed(state.home.data, achievement)

        if diamonds:
            self.earn_diamonds(state, diamonds)
        if exp:
            self.earn_exp(state, exp)
        if points:
            state.account_stat("achievement_points", points)
        Achievements.update_house_rank(state)
        logger.info(
            "[CMD] claim achievement {} -> {} diamonds, {} exp, {} points"
            .format(achievement, diamonds, exp, points))
        state.save()
        return True

    def decode(self):
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
