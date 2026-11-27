from Utils.Logging import logger
from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic.Tutorials import complete, next_instance
from Logic.GameData import TUTORIAL_TABLE, tutorial_instance


class LogicStartTutorialCommand(LogicCommand):
    """Start a tutorial step (f0 = LogicTutorialData id)."""

    NAME = "LogicStartTutorialCommand"
    TYPE = 35
    FIELDS = ['int', 'tick']

    def execute(self, state):
        gid = self.f0
        instance = tutorial_instance(gid)
        row = self.data.row(TUTORIAL_TABLE, instance)
        if row is None:
            logger.info("[CMD] start tutorial {}: unknown row".format(gid))
            state.save()
            return False
        state.home.data["TutorialStarted"] = instance
        # StartTutorial completes the row named by AutoCompleteOtherTutorial,
        # but deliberately does not mark the newly started row itself.
        auto_name = row.s("AutoCompleteOtherTutorial").strip()
        auto_index = None
        if auto_name:
            for index, candidate in enumerate(self.data.rows(TUTORIAL_TABLE)):
                if candidate.s("Name").strip() == auto_name:
                    auto_index = index
                    break
        if auto_index is not None:
            complete(state.home, self.data, auto_index)
        completed = state.home.data.get("TutorialsCompleted", [])
        state.home.data["TutorialNext"] = next_instance(
            completed, self.data, state.account.exp_level)
        if not state.home.data.get("TutorialCompleted"):
            logger.info("[CMD] start tutorial step {} (gid {})".format(instance, gid))
        state.save()
        return True

    def decode(self):
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
