from Logic.GameData import BITLIST_TABLES, TUTORIAL_TABLE


class LogicClientAvatar:
    def __init__(self, config, data, state=None):
        self.c = config
        self.data = data
        self.state = state

    def tutorial_bits_enabled(self, tid):
        """Config skip flag (kept for compatibility)."""
        c = self.c
        return bool(c.get('SkipTutorial')) and tid == (c.get('TutorialTable', 36) or 36)

    def tutorial_completed_ids(self, tid):
        """CSV instance ids of completed tutorial steps, for table ``tid``."""
        if tid != (self.c.get('TutorialTable', 36) or 36):
            return set()
        home = getattr(self.state, 'home', None) if self.state else None
        if home is None:
            return set()
        from Logic.Tutorials import normalize_completed
        return set(normalize_completed(home, self.data))

    def resource_pairs(self, diamonds, cash, level, points):
        """All avatar resources in the client's actual inventory format.

        ``LogicInventory::encode`` writes
        ``short count, count * (int global id, int amount)``.  Diamonds, cash
        and exp are resources too, followed by every item owned in the farm
        inventory.  Sending only the four account values reset the client's
        goods to zero on every home load.
        """
        d = self.data
        pairs = []
        seen = set()
        for name, value in (("Diamonds", diamonds), ("Cash", cash),
                            ("ExpLevel", level), ("ExpPoints", points)):
            value = int(value or 0)
            global_id = d.gid(19, name)
            if global_id is not None and value:
                pairs.append((global_id, value))
                seen.add(global_id)

        home = getattr(self.state, "home", None) if self.state else None
        inventory = getattr(home, "inventory", None) if home is not None else None
        if inventory is not None:
            for raw_id, raw_count in inventory.items():
                try:
                    global_id = int(raw_id)
                    amount = int(raw_count)
                except (TypeError, ValueError):
                    continue
                # Table 19 is the account-resource table and is emitted above.
                # Unknown ids would make the client's data lookup fail.
                if amount <= 0 or global_id in seen:
                    continue
                if d.row_for(global_id) is None:
                    continue
                pairs.append((global_id, amount))
                seen.add(global_id)

        if self.state is not None:
            # Achievement progress is encoded as table-19 counters, while
            # claim state is encoded as table-59 resources (0/1/2).
            from Logic import Achievements
            for global_id, amount in (
                    Achievements.money_resource_pairs(self.state)
                    + Achievements.resource_pairs(self.state)):
                if amount > 0 and global_id not in seen:
                    pairs.append((global_id, amount))
                    seen.add(global_id)
        return pairs

    def encode(self, w):
        c, d = self.c, self.data
        # The account object is authoritative.  Reading these values back out
        # of config.json made the client display whatever the file said (or
        # crash with KeyError when a key was missing), not what the player
        # actually owns after a command turn.
        acct = getattr(self.state, "account", None)
        if acct is not None:
            high, low = acct.high_id, acct.low_id
            diamonds, cash = acct.diamonds, acct.cash
            level, points = acct.exp_level, acct.exp_points
            name = acct.name
        else:
            high = c.get("AccountHighID", 0)
            low = c.get("AccountLowID", 1)
            diamonds = c.get("Diamonds", 0)
            cash = c.get("Cash", 0)
            level = c.get("ExpLevel", 1)
            points = c.get("ExpPoints", 0)
            name = c.get("Name", "Forman")
        w.writeInt(high); w.writeInt(low)

        res = self.resource_pairs(diamonds, cash, level, points)
        w.writeInt(len(res), 2)
        for g, v in res:
            w.writeInt(g); w.writeInt(v)

        level = int(level or 1)
        for tid in BITLIST_TABLES:
            n = d.count(tid)
            words = [0] * ((n + 31) // 32)
            if self.tutorial_bits_enabled(tid):
                # Full skip (config flag only).
                for i in range(n):
                    words[i >> 5] |= 1 << (i & 31)
            elif tid == TUTORIAL_TABLE:
                # Per-step tutorial progress (simulates the client's
                # LogicInventory::setBit(data) for each completed step).
                #
                # IMPORTANT: never send *every* bit set.  The patched 1.5.42
                # client treats that as "tutorial finished" and exits to the
                # post-tutorial game mode with a farm that was never set up
                # for it, which crashes it while loading home.  Keep the last
                # step clear; enabled tutorials still work normally.
                ids = self.tutorial_completed_ids(tid)
                if n > 0 and len(ids) >= n:
                    ids = {i for i in ids if i != n - 1}
                for instance in ids:
                    if 0 <= instance < n:
                        words[instance >> 5] |= 1 << (instance & 31)
            else:
                # LogicInventory::isUnlocked() reads these bit lists -- NOT
                # the UnlockLevel column alone.  Leaving them empty makes the
                # client think no crops/goods/tools are unlocked, which
                # crashes LogicSpinWheelCar::randomizePrizes (empty prize
                # lists) as soon as the wheel appears at level 8.
                table = d.table(tid)
                if table is not None:
                    for i, row in enumerate(table.rows):
                        if i >= n:
                            break
                        if row.i("UnlockLevel", 0) <= level:
                            words[i >> 5] |= 1 << (i & 31)
            for x in words:
                w.writeInt(x)

        w.writeInt(0, 2)  # roadside shop
        w.writeString(name)  # name
        w.writeInt(0)  # mail
        w.writeInt(0)  # new shop items
        w.writeInt(0)  # shared boat crates

