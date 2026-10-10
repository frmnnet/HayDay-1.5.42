from Logic.GameData import BITLIST_TABLES


def encode(w, data, ai, high, low, name):
    inv = ai['inventory']
    res = [(t['Table'] * 100000 + i, v) for t in inv['ResourceList']
           for i, v in enumerate(t['Values']) if v]
    w.writeInt(high); w.writeInt(low)
    w.writeInt(len(res), 2)
    for g, v in res:
        w.writeInt(g); w.writeInt(v & 0xFFFFFFFF)
    bits = {b['Table']: b['Values'] for b in inv['BitLists']}
    for tid in BITLIST_TABLES:
        n = (data.count(tid) + 31) // 32
        vals = (bits.get(tid, []) + [0] * n)[:n]
        for x in vals:
            w.writeInt(x & 0xFFFFFFFF)

    w.writeInt(0, 2)  # roadside shop
    w.writeString(name)  # AI's name
    w.writeInt(0)
    w.writeInt(0)
    w.writeInt(0)
