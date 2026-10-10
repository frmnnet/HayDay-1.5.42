BIT_LIST_ROWS = {
    3: 53, 4: 11, 6: 17, 13: 5, 15: 5, 16: 5, 17: 0, 22: 5, 23: 4, 24: 7, 25: 6, 26: 5, 27: 3, 28: 3,
    29: 3, 30: 5, 33: 7, 36: 60, 38: 9, 48: 8, 51: 3, 60: 5, 61: 6, 64: 3, 65: 3, 66: 4, 68: 10,
    69: 4, 75: 3, 77: 4, 78: 9, 80: 17, 82: 5, 84: 5,
}
BITLIST_TABLES = sorted(BIT_LIST_ROWS)

MONEY_ROWS = {'Cash': 0, 'Diamonds': 1, 'ExpLevel': 2, 'ExpPoints': 3}

class GameData:
    def count(self, tid):
        return BIT_LIST_ROWS.get(tid, 0)

    def gid(self, tid, name):
        if tid == 19 and name in MONEY_ROWS:
            return tid * 100000 + MONEY_ROWS[name]
        return None
