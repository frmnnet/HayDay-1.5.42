"""Field growth logic.

A field is planted (crop id), starts growing (``state == 'growing'``) and
flips to ``state == 'ready'`` once ``ready`` time passes. Harvesting takes
the crop and resets the field.
"""
from Logic.GameTime import now_seconds

# Field states (match the game's LogicFieldData::State ids)
EMPTY = 0
PLANTED = 1
GROWING = 2
READY = 3


class Field:
    """One field tile with a planted crop."""

    GROW_TIME = 120  # seconds until the crop is ready (overridden by CSV)

    STATE_NAMES = {"empty": EMPTY, "planted": PLANTED, "growing": GROWING,
                   "ready": READY}

    # Class-level aliases so handlers can use Field.READY etc.
    EMPTY = EMPTY
    PLANTED = PLANTED
    GROWING = GROWING
    READY = READY

    @staticmethod
    def _as_state(state):
        if state is None:
            return None
        if isinstance(state, str):
            return Field.STATE_NAMES.get(state.lower(), PLANTED)
        return int(state)

    def __init__(self, crop=0, state=PLANTED, planted=None, ready=0):
        self.crop = int(crop or 0)
        st = self._as_state(state)
        self.state = st if st is not None else (
            GROWING if self.crop and state is None else PLANTED)
        self.planted = int(now_seconds()) if planted is None else int(planted)
        self.ready = int(ready or 0)

    # ------------------------------------------------------------------ #
    @property
    def is_growing(self):
        return self.state == GROWING

    def grow_tick(self, now):
        """Advance growth; returns True if the field became ready."""
        if self.is_growing and now >= self.ready:
            self.state = READY
            return True
        return False

    def harvest(self, now):
        """Collect the crop. Returns the crop id if there was one."""
        crop = self.crop
        self.crop = 0
        self.state = EMPTY
        self.planted = 0
        self.ready = 0
        return crop if crop else 0

    # ------------------------------------------------------------------ #
    def to_dict(self):
        return {
            "crop": self.crop,
            "state": self.state,
            "planted": self.planted,
            "ready": self.ready,
        }

    @classmethod
    def from_dict(cls, d):
        if not d:
            return cls()
        f = cls(crop=d.get("crop", 0), state=d.get("state", 0),
                planted=d.get("planted", 0), ready=d.get("ready", 0))
        return f


class FieldManager:
    """Manages the {tile_key: Field} mapping (serialized as plain dicts)."""

    def __init__(self, data=None):
        self.data = data if isinstance(data, dict) else {}

    def get(self, key) -> Field:
        return Field.from_dict(self.data.get(str(key)))

    def set(self, key, field: Field):
        self.data[str(key)] = field.to_dict()
        return field

    def plant(self, key, crop, grow_time=120, now=None):
        now = now_seconds() if now is None else int(now)
        f = Field(crop=crop, state=GROWING, planted=now, ready=now + grow_time)
        self.set(key, f)
        return f

    def grow_all(self, now=None):
        """Advance all growing fields; returns count that became ready."""
        now = now_seconds() if now is None else now
        ready_count = 0
        for key in list(self.data.keys()):
            if self.get(key).grow_tick(now):
                ready_count += 1
                self.set(key, self.get(key))
        return ready_count

    def ready_crops(self):
        """Yield (key, crop) for fields in READY state."""
        for key in self.data:
            f = self.get(key)
            if f.state == READY and f.crop:
                yield key, f

    def __len__(self):
        return len(self.data)

    def __iter__(self):
        return iter(self.data)
