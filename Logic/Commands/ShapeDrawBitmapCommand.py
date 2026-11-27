from Logic.Commands.LogicCommand import LogicCommand


class ShapeDrawBitmapCommand(LogicCommand):
    """Handler for ShapeDrawBitmapCommand."""

    NAME = "ShapeDrawBitmapCommand"

    def execute(self, state):
        return super().execute(state)
