from Utils.Reader import Reader
from Logic.Commands.LogicCommand import LogicCommand
from Logic import Storage
import math


class LogicBuyGoodsWithDiamondsCommand(LogicCommand):
    """Buy resources with diamonds.

    IDA's ``createAndDecode`` shows a variable-length payload:

        byte count
        count * (int data id, int amount)
        byte category/flags
        int tick

    Treating this as two bytes followed by the tick made the command stream
    desynchronize, so every command after a seed purchase was discarded.
    """

    NAME = "LogicBuyGoodsWithDiamondsCommand"
    TYPE = 39
    FIELDS = ['counted_int_pairs', 'byte', 'tick']

    def execute(self, state):
        purchases = self.f0 if isinstance(self.f0, list) else []
        total = 0
        rows = []
        level = int(getattr(state.account, "exp_level", 1) or 1)
        level_row = self.data.level_row(level)
        coins_per_diamond = max(
            1, level_row.i("DiamondsToCoinsRate", 1)
            if level_row is not None else 1)
        for data_id, amount in purchases:
            amount = int(amount or 0)
            row = self.data_row(data_id)
            if row is None or amount <= 0:
                return False
            currency, unit_price = self.data.shop_price(row, count=0)
            if currency == "diamond" and unit_price > 0:
                price = int(unit_price) * amount
            else:
                value = max(
                    row.i("OrderValue", 0),
                    row.i("DumbValue", 0),
                    row.i("OrderPrice", 0),
                )
                price = max(
                    1, int(math.ceil(float(max(1, value)) /
                                     coins_per_diamond))) * amount
            total += price
            rows.append((data_id, amount))

        # A purchase is atomic: never grant half of a multi-resource order.
        if not Storage.can_store_many(state.home.data, rows):
            return False
        if not self.spend_diamonds(state, total):
            return False
        for data_id, amount in rows:
            self.give(state, data_id, amount)
        return bool(rows)

    def decode(self):
        """Parse the real binary payload layout (see command_formats.json)."""
        if self.payload:
            self.decode_fields(Reader(self.payload), self.FIELDS)
