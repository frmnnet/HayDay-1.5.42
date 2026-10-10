from Logic.GameData import BITLIST_TABLES


class LogicClientAvatar:
    def __init__(self, config, data):
        self.c = config
        self.data = data

    def encode(self, w):
        c, d = self.c, self.data
        w.writeInt(c['AccountHighID']); w.writeInt(c['AccountLowID'])

        money = [('Diamonds', c['Diamonds']), ('Cash', c['Cash']),
                 ('ExpLevel', c['ExpLevel']), ('ExpPoints', c['ExpPoints'])]
        res = [(d.gid(19, n), v) for n, v in money if v]
        res = [(g, v) for g, v in res if g is not None]
        w.writeInt(len(res), 2)
        for g, v in res:
            w.writeInt(g); w.writeInt(v)

        for tid in BITLIST_TABLES:
            n = d.count(tid)
            words = [0] * ((n + 31) // 32)
            if c.get('SkipTutorial') and tid == c.get('TutorialTable', 36):
                for i in range(n):
                    words[i >> 5] |= 1 << (i & 31)
            for x in words:
                w.writeInt(x)

        w.writeInt(0, 2)  # roadside shop
        w.writeString(c['Name'])  # name
        w.writeInt(0)  # mail
        w.writeInt(0)  # new shop items
        w.writeInt(0)  # shared boat crates

