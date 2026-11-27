"""OOP representation of the player's inventory (Inventory CSV id -> count).

The on-wire/on-disk shape is a flat {item_id: count} mapping. This class is a
thin OOP wrapper providing give/take/amount/has and serialization.
"""
from typing import Dict


class Inventory:
    """Counts of resources owned by the player."""

    def __init__(self, data=None):
        if isinstance(data, Inventory):
            data = data.data
        data = data if data is not None else {}
        # Normalize legacy mixed-type keys in place (the dict is shared with
        # Home.data).  When both representations existed, keep the larger
        # count rather than inventing extra items.
        normalized = {}
        for key, value in data.items():
            item = self._key(key)
            try:
                count = int(value)
            except (TypeError, ValueError):
                count = 0
            normalized[item] = max(normalized.get(item, 0), count)
        data.clear()
        data.update(normalized)
        # Shared backing dict so mutations via the manager are seen in Home.
        self.data: Dict[str, int] = data

    @staticmethod
    def _key(item_id):
        """Always use string keys.

        Mixing int and str keys (e.g. int 4294967295 from ``give()`` and the
        string "4294967295" loaded from JSON) makes ``json.dumps`` emit the
        same key twice, and the client's LogicJSONObject::put throws on the
        duplicate.  String keys serialize unambiguously.
        """
        try:
            return str(int(item_id))
        except (TypeError, ValueError):
            return str(item_id)

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #
    def amount(self, item_id) -> int:
        """How many of ``item_id`` are owned (0 when absent)."""
        return self.data.get(self._key(item_id), 0)

    def has(self, item_id, count=1) -> bool:
        return self.amount(item_id) >= count

    def __contains__(self, item_id):
        return self.amount(item_id) > 0

    def __len__(self):
        return len(self.data)

    def items(self):
        return self.data.items()

    # ------------------------------------------------------------------ #
    # Mutations
    # ------------------------------------------------------------------ #
    def give(self, item_id, count=1) -> bool:
        key = self._key(item_id)
        self.data[key] = self.data.get(key, 0) + int(count)
        if self.data[key] <= 0:
            del self.data[key]
        return True

    def take(self, item_id, count=1) -> bool:
        """Remove up to ``count``; returns False when there isn't enough."""
        key = self._key(item_id)
        have = self.data.get(key, 0)
        if have < count:
            return False
        self.data[key] = have - int(count)
        if self.data[key] <= 0:
            del self.data[key]
        return True

    def sync_from(self, data):
        """Replace contents from another mapping (or Inventory)."""
        self.data = {self._key(k): int(v) for k, v in dict(data or {}).items()}

    def prune_unknown(self, game_data):
        """Drop keys the client cannot resolve as resource data ids."""
        for key in list(self.data):
            try:
                item_id = int(key)
            except (TypeError, ValueError):
                del self.data[key]
                continue
            if game_data.row_for(item_id) is None:
                del self.data[key]
        return self

    # ------------------------------------------------------------------ #
    # Serialization
    # ------------------------------------------------------------------ #
    def to_json(self):
        return dict(self.data)

    def __repr__(self):
        return "Inventory(%r)" % self.data
