from Utils.Logging import logger
from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import Achievements


class LogicCompletePeopleOrderCommand(LogicCommand):
    """Complete a visitor order (f0 = ``tutorial_people_orders.csv`` row).

    ``LogicPeopleOrder`` rewards are derived from the requested good's
    ``OrderPrice`` / ``OrderExp`` columns, multiplied by ``GoodAmount``.
    """

    NAME = "LogicCompletePeopleOrderCommand"
    TYPE = 40
    FIELDS = ['int', 'tick']

    def execute(self, state):
        order = self.f0
        row = self.data.row(51, order)  # tutorial_people_orders
        good_name = row.s("Good") if row is not None else ""
        amount = row.i("GoodAmount", 0) if row is not None else 0
        amount = max(1, amount)

        good = self.item(good_name)
        cash = good.i("OrderPrice", 0) * amount if good is not None else 0
        exp = good.i("OrderExp", 0) * amount if good is not None else 0
        if cash <= 0:
            level = int(getattr(state.account, "exp_level", 1) or 1)
            level_row = self.data.level_row(level)
            guest = level_row.i("GuestOrderValue", 10) if level_row else 10
            cash, exp = max(1, guest * 2), max(1, guest)

        record = state.home.data.setdefault("PeopleOrders", {}).setdefault(str(order), {})
        record.update({"Completed": True, "Cash": cash, "Exp": exp,
                       "Good": good_name, "Amount": amount})
        self.earn_cash(state, cash)
        self.earn_exp(state, exp)
        Achievements.record(state, "PeopleOrders")
        logger.info("[CMD] people order {} ({}) -> cash {}, exp {}".format(
            order, good_name, cash, exp))
        state.save()
        return True

    def decode(self):
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
