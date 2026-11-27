"""Home object identity and mutations.

The client's ``LogicGameObjectManager::generateGameObjectGlobalID`` assigns
``GlobalID.createGlobalID(data_type, ordinal)`` while the home JSON is loaded.
The command field is that runtime id, not the object's data id.  For example
the third field (data class 4) has runtime id ``400002`` regardless of which
crop happens to be growing on it.
"""


def object_type(entry):
    try:
        return int(entry.get("ID")) // 100000
    except (AttributeError, TypeError, ValueError):
        return None


def runtime_id_for(entry, objects):
    """Current runtime global id for ``entry``.

    IDs are valid for one client home load.  ``reset_runtime_ids`` refreshes
    all aliases whenever a home snapshot is sent; commands in one turn then
    address the same entries until the next snapshot.
    """
    explicit = entry.get("_ClientRuntimeID")
    if explicit is not None:
        try:
            return int(explicit)
        except (TypeError, ValueError):
            pass
    return _load_runtime_id_for(entry, objects)


def _load_runtime_id_for(entry, objects):
    """Runtime id assigned while ``LogicGameObjectManager`` loads the JSON."""
    data_type = object_type(entry)
    if data_type is None:
        return None
    ordinal = 0
    for candidate in objects:
        if candidate is entry:
            return data_type * 100000 + ordinal
        if object_type(candidate) == data_type and not candidate.get("Stored"):
            ordinal += 1
    return None


def resolve_runtime_id(data, game_object_id):
    """Resolve a live client object id, including recreated field cycles.

    ``LogicField`` replaces an empty field's display object after harvest.
    The client therefore starts issuing the next global-id cycle for the same
    field tiles (for example ``400012..400023`` after the original
    ``400000..400011``).  The persisted object order is stable, so map the
    cycle ordinal back to the matching field entry and bind the new alias.
    """
    index, entry = find_by_runtime_id(data, game_object_id)
    if entry is not None:
        return index, entry
    try:
        wanted = int(game_object_id)
    except (TypeError, ValueError):
        return None, None
    if wanted // 100000 != 4:
        return None, None
    objects = data.setdefault("Objects", [])
    fields = [
        (candidate_index, candidate)
        for candidate_index, candidate in enumerate(objects)
        if object_type(candidate) == 4
    ]
    if not fields:
        return None, None
    ordinal = wanted % 100000
    index, entry = fields[ordinal % len(fields)]
    entry["_ClientRuntimeID"] = wanted
    return index, entry


def reset_runtime_ids(data):
    """Rebuild the client's load-scoped runtime ids from object order.

    ``LogicGameObjectManager::generateGameObjectGlobalID`` increments one
    counter per data type for every non-stored object accepted by
    ``loadObjectsFromJSON``.  The counter is not serialized in the home JSON,
    so aliases from a previous load cannot be reused after OwnHomeData.
    """
    objects = data.setdefault("Objects", [])
    aliases = {}
    for entry in objects:
        if not isinstance(entry, dict) or entry.get("Stored"):
            continue
        runtime_id = _load_runtime_id_for(entry, objects)
        if runtime_id is None:
            continue
        entry["_ClientRuntimeID"] = runtime_id
        entry.pop("_PendingRuntime", None)
        aliases[runtime_id] = entry
    return aliases


def find_by_runtime_id(data, game_object_id):
    """Return ``(index, entry)`` for the object the client referenced."""
    try:
        wanted = int(game_object_id)
    except (TypeError, ValueError):
        return None, None
    objects = data.setdefault("Objects", [])
    for index, entry in enumerate(objects):
        try:
            if int(entry.get("_ClientRuntimeID")) == wanted:
                return index, entry
        except (TypeError, ValueError):
            continue
    return None, None


def reconcile_runtime_ids(data, observed_ids):
    """Bind ids generated during this home-load to newly created objects.

    The buy commands carry ``-1`` in their object-id argument in this client
    build.  New object ids are therefore learned from the first command that
    references one.  The client allocates consecutive ids in append order, so
    an observed high-water mark identifies the whole fresh pending batch even
    when only some of those objects have been touched in this turn.
    """
    objects = data.setdefault("Objects", [])
    observed_by_type = {}
    for observed in observed_ids:
        try:
            observed = int(observed)
        except (TypeError, ValueError):
            continue
        object_data_type = observed // 100000
        pending = [
            entry for entry in objects
            if _PendingRuntime(entry) and object_type(entry) == object_data_type
        ]
        if not pending:
            continue
        known = {
            int(entry["_ClientRuntimeID"])
            for entry in objects
            if not _PendingRuntime(entry) and entry.get("_ClientRuntimeID") is not None
        }
        if observed in known:
            continue
        observed_by_type.setdefault(object_data_type, set()).add(observed)

    for object_data_type, ids in observed_by_type.items():
        pending = [
            entry for entry in objects
            if _PendingRuntime(entry) and object_type(entry) == object_data_type
        ]
        highest_id = max(ids)
        first_id = highest_id - len(pending) + 1
        for offset, entry in enumerate(pending):
            runtime_id = first_id + offset
            entry["_ClientRuntimeID"] = runtime_id
            entry["_PendingRuntime"] = False


def _PendingRuntime(entry):
    return bool(entry.get("_PendingRuntime"))


def _translate(entry, dx, dy):
    tile_x = int(entry.get("X") or 0)
    tile_y = int(entry.get("Y") or 0)
    accurate_x = int(entry.get("_AccurateX", tile_x * 512)) + int(dx)
    accurate_y = int(entry.get("_AccurateY", tile_y * 512)) + int(dy)
    entry["_AccurateX"] = accurate_x
    entry["_AccurateY"] = accurate_y
    # LogicGameObject::getTileXForSaving/getTileYForSaving use ASRS #9.
    # Arithmetic right shift floors negative sub-tile coordinates.
    entry["X"] = accurate_x >> 9
    entry["Y"] = accurate_y >> 9
    return entry


def move(data, game_object_id, dx, dy):
    """Apply the client's accurate-coordinate delta to one object."""
    _, entry = find_by_runtime_id(data, game_object_id)
    if entry is None:
        return None
    # The Mach-O saves getTileXForSaving/getTileYForSaving, which divide by
    # 512 with signed truncation toward zero.
    _translate(entry, dx, dy)

    return entry


def mirror(data, game_object_id):
    """Toggle the client-visible mirror flag for one object."""
    _, entry = find_by_runtime_id(data, game_object_id)
    if entry is None:
        return None
    entry["Mirrored"] = not bool(entry.get("Mirrored"))
    return entry


def remove(data, game_object_id):
    """Remove and return one placed object referenced by runtime id."""
    index, entry = find_by_runtime_id(data, game_object_id)
    if entry is None:
        return None
    return data["Objects"].pop(index)
