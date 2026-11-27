"""Animal state stored on placed home objects.

``LogicAnimal::save`` writes the normal object position/data id plus ``HID``
(the parent habitat type index), ``Timer`` and ``Fed``.  The old server kept
animals in an unrelated dictionary, so reconnect lost their positions and
feed state.
"""
from Logic import HomeObjects
from Logic.GameData import GameData, TABLE_IDS
from Logic.GameTime import now_seconds, sync_timer

ANIMAL_TYPE = TABLE_IDS["animals"]
HABITAT_TYPE = TABLE_IDS["animal_habitats"]

def _animals(data):
    bucket = data.setdefault("Animals", {})
    if not isinstance(bucket, dict):
        bucket = {}
        data["Animals"] = bucket
    return bucket


def habitat_data_for(animal_data_id):
    """Map an ``animals.csv`` row to its ``animal_habitats.csv`` row."""
    game_data = GameData.instance()
    animal = game_data.row_for(animal_data_id)
    if animal is None or animal.tid != ANIMAL_TYPE:
        return None
    animal_name = animal.s("Name")
    for habitat in game_data.rows(HABITAT_TYPE):
        if habitat.s("Animal").strip().lower() == animal_name.strip().lower():
            return habitat.global_id
    return None


def entry_for(data, animal_id):
    _, entry = HomeObjects.find_by_runtime_id(data, animal_id)
    if entry is None or HomeObjects.object_type(entry) != ANIMAL_TYPE:
        return None
    return entry


def add(data, data_id, accurate_x, accurate_y, habitat_id=None,
        mirrored=False):
    parent_x = 0
    parent_y = 0
    if habitat_id is not None:
        _index, habitat = HomeObjects.find_by_runtime_id(data, habitat_id)
        if habitat is not None and HomeObjects.object_type(habitat) in (
                HABITAT_TYPE, 79):
            parent_x = int(habitat.get(
                "_AccurateX", int(habitat.get("X") or 0) * 512))
            parent_y = int(habitat.get(
                "_AccurateY", int(habitat.get("Y") or 0) * 512))
    relative_x = int(accurate_x) - parent_x
    relative_y = int(accurate_y) - parent_y
    entry = {
        "ID": int(data_id),
        "X": relative_x >> 9,
        "Y": relative_y >> 9,
        "_AccurateX": relative_x,
        "_AccurateY": relative_y,
        "Fed": False,
        "_PendingRuntime": True,
    }
    if mirrored:
        entry["Mirrored"] = True
    if habitat_id is not None:
        try:
            entry["HID"] = int(habitat_id) % 100000
        except (TypeError, ValueError):
            pass
    data.setdefault("Objects", []).append(entry)
    return entry


def feed(data, animal_id, total_seconds, ready_at, now=None):
    entry = entry_for(data, animal_id)
    if entry is None:
        return None
    now = now_seconds() if now is None else int(now)
    total_seconds = max(0, int(total_seconds or 0))
    ready_at = int(ready_at)
    sync_timer(entry, "Timer", total_seconds, ready_at, now)
    entry["Fed"] = True
    _animals(data)[str(animal_id)] = {
        "DataId": int(entry.get("ID") or 0),
        "FedAt": now,
        "Ready": ready_at,
        "TotalSeconds": total_seconds,
    }
    return entry


def instant(data, animal_id):
    entry = entry_for(data, animal_id)
    if entry is None:
        return None
    now = now_seconds()
    entry.pop("Timer", None)
    entry["Fed"] = True
    metadata = _animals(data).get(str(animal_id))
    if isinstance(metadata, dict):
        metadata["Ready"] = now
    return entry


def collect(data, animal_id, now=None):
    """Return the animal entry when its product is ready."""
    entry = entry_for(data, animal_id)
    if entry is None:
        return None
    now = now_seconds() if now is None else int(now)
    metadata = _animals(data).get(str(animal_id))
    if isinstance(metadata, dict):
        if int(metadata.get("Ready") or 0) > now:
            return None
    else:
        timer = entry.get("Timer")
        if isinstance(timer, dict):
            if int(timer.get("TicksLeft") or 0) > 0:
                return None
    entry.pop("Timer", None)
    entry["Fed"] = False
    _animals(data).pop(str(animal_id), None)
    return entry


def sync_from_metadata(data, now=None):
    """Keep client Timer ticks in sync with the database-ready timestamp."""
    now = now_seconds() if now is None else int(now)
    fed_legacy = data.get("FedAnimals", {})
    if not isinstance(fed_legacy, dict):
        fed_legacy = {}

    # Older builds stored feed-ready timestamps in ``FedAnimals``.  Convert
    # those records before pruning unrelated bare values from ``Animals``.
    for key, value in list(fed_legacy.items()):
        entry = entry_for(data, key)
        if entry is None:
            fed_legacy.pop(key, None)
            continue
        try:
            ready_at = int(value)
        except (TypeError, ValueError):
            continue
        instant_ready = _animals(data).get(key)
        if not isinstance(instant_ready, dict):
            try:
                # Older instant-complete handlers wrote the new ready time to
                # ``Animals`` while feed time stayed in ``FedAnimals``.
                ready_at = min(ready_at, int(instant_ready))
            except (TypeError, ValueError):
                pass
        _animals(data)[key] = {
            "DataId": int(entry.get("ID") or 0),
            "Ready": ready_at,
            "TotalSeconds": 0,
        }
        fed_legacy.pop(key, None)

    for key, metadata in list(_animals(data).items()):
        if not isinstance(metadata, dict):
            _animals(data).pop(key, None)
            continue
        entry = entry_for(data, key)
        if entry is None:
            _animals(data).pop(key, None)
            continue
        if metadata.get("Ready") is None:
            # Pre-normalization records used lowercase ``ready`` for unrelated
            # action bookkeeping.  They do not describe a current feed state.
            _animals(data).pop(key, None)
            continue
        ready_at = int(metadata.get("Ready") or 0)
        sync_timer(
            entry, "Timer",
            int(metadata.get("TotalSeconds") or 0),
            ready_at, now)
        entry["Fed"] = True


def sync_habitats(data):
    """Ensure animals point at the habitat matching their species."""
    objects = data.setdefault("Objects", [])
    animals = [
        entry for entry in list(objects)
        if HomeObjects.object_type(entry) == ANIMAL_TYPE
    ]
    habitat_by_data = {}
    for entry in objects:
        if HomeObjects.object_type(entry) != HABITAT_TYPE:
            continue
        habitat_by_data.setdefault(int(entry.get("ID") or 0), []).append(entry)

    # Add one matching habitat for every species that has animals.
    for animal in animals:
        animal_data = int(animal.get("ID") or 0)
        habitat_data = habitat_data_for(animal_data)
        if habitat_data is None or habitat_by_data.get(habitat_data):
            continue
        same_species = [
            other for other in animals
            if int(other.get("ID") or 0) == animal_data
        ]
        min_x = min(int(other.get("X") or 0) for other in same_species)
        min_y = min(int(other.get("Y") or 0) for other in same_species)
        habitat = {
            "ID": habitat_data,
            "X": max(0, min_x - 1),
            "Y": max(0, min_y - 1),
            "_AccurateX": max(0, (min_x - 1) * 512),
            "_AccurateY": max(0, (min_y - 1) * 512),
        }
        objects.append(habitat)
        habitat_by_data[habitat_data] = [habitat]

    # HID is the type-local habitat index.  A wrong species parent causes the
    # client to restore the animal to an old/default place.
    species_ordinal = {}
    for animal in animals:
        animal_data = int(animal.get("ID") or 0)
        habitat_data = habitat_data_for(animal_data)
        habitat = (habitat_by_data.get(habitat_data) or [None])[0]
        if habitat is None:
            continue
        new_hid = HomeObjects.runtime_id_for(habitat, objects) % 100000
        try:
            old_hid = int(animal.get("HID", -1))
        except (TypeError, ValueError):
            old_hid = -1
        if old_hid != new_hid:
            ordinal = species_ordinal.get(animal_data, 0)
            species_ordinal[animal_data] = ordinal + 1
            animal["X"] = 1 + ordinal % 3
            animal["Y"] = 1 + ordinal // 3
            animal["_AccurateX"] = animal["X"] * 512
            animal["_AccurateY"] = animal["Y"] * 512
        animal["HID"] = new_hid

    # The tutorial chicken tent is replaced by the claimed chicken habitat.
    habitat_data = {
        int(entry.get("ID") or 0) for entry in objects
        if HomeObjects.object_type(entry) == HABITAT_TYPE
    }
    game_data = GameData.instance()
    chicken_tent = game_data.find(21, "ChickenTent")
    chicken_habitat = game_data.find(11, "ChickenHabitat")
    replacement_tents = {}
    if chicken_tent is not None and chicken_habitat is not None:
        replacement_tents[chicken_tent.global_id] = chicken_habitat.global_id
    data["Objects"] = [
        entry for entry in objects
        if not (
            HomeObjects.object_type(entry) == 21
            and replacement_tents.get(int(entry.get("ID") or 0)) in habitat_data
        )
    ]
