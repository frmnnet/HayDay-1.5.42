"""Tutorial progress helpers shared by state persistence and packets.

The client stores tutorial progress as one bit per ``tutorials.csv`` row.
``LogicInventory::tutorialCompleted`` sets that bit, recursively completes
rows named by ``AutoCompleteOtherTutorial``, and awards ``GoodReward`` only
when the bit was not already set.  The server mirrors those rules so a
duplicate/replayed command cannot grant a reward twice.
"""
from Logic.GameData import TUTORIAL_TABLE, tutorial_instance


def _table(data):
    return data.table(TUTORIAL_TABLE)


def progress_order(data):
    """CSV instance ids in the order in which the tutorial advances."""
    table = _table(data)
    if table is None:
        return []
    return sorted(
        range(len(table.rows)),
        key=lambda index: (table.rows[index].i("Priority", index), index),
    )


def normalize_completed(home, data):
    """Return valid, unique, priority-ordered completed instance ids."""
    table = _table(data)
    if table is None:
        return []
    count = len(table.rows)
    completed = set()
    for raw in home.data.get("TutorialsCompleted", []) or []:
        instance = tutorial_instance(raw)
        if instance is not None and 0 <= instance < count:
            completed.add(instance)
    return [instance for instance in progress_order(data)
            if instance in completed]


def store_completed(home, instances, data):
    """Persist a normalized tutorial bit set and refresh derived fields."""
    completed = set(instances or ())
    ordered = [instance for instance in progress_order(data)
               if instance in completed]
    home.data["TutorialsCompleted"] = ordered
    return ordered


def row_for(data, instance):
    table = _table(data)
    if table is None or instance is None:
        return None
    if not 0 <= int(instance) < len(table.rows):
        return None
    return table.rows[int(instance)]


def requirement_met(home, data, row):
    """Whether the named ``RequiredTutorial`` row is already complete."""
    if row is None:
        return False
    required = row.s("RequiredTutorial").strip()
    if not required:
        return True
    completed = set(normalize_completed(home, data))
    for index, candidate in enumerate(data.rows(TUTORIAL_TABLE)):
        if candidate.s("Name").strip() == required:
            return index in completed
    return False


def auto_complete_ids(data, instance):
    """Rows recursively auto-completed by ``instance``."""
    table = _table(data)
    row = row_for(data, instance)
    if table is None or row is None:
        return []
    name = row.s("AutoCompleteOtherTutorial").strip()
    if not name:
        return []
    for index, other in enumerate(table.rows):
        if other.s("Name").strip() == name:
            return [index] + auto_complete_ids(data, index)
    return []


def complete(home, data, instance):
    """Apply the client's recursive completion rule.

    Returns ``(newly_completed_ids, all_completed_ids)``.  ``newly_completed``
    is used by the command handler to award good rewards exactly once.
    """
    current = set(normalize_completed(home, data))
    newly = []

    def apply(value):
        value = tutorial_instance(value)
        if row_for(data, value) is None or value in current:
            return
        current.add(value)
        newly.append(value)
        for other in auto_complete_ids(data, value):
            apply(other)

    apply(instance)
    ordered = store_completed(home, current, data)
    return newly, ordered


def next_instance(completed, data, account_level=1):
    """First level-eligible tutorial row not completed yet."""
    table = _table(data)
    if table is None:
        return None
    completed = set(completed or ())
    account_level = max(1, int(account_level or 1))
    for instance in progress_order(data):
        if instance in completed:
            continue
        row = table.rows[instance]
        min_level = max(1, row.i("MinExpLevel10", 0) // 10)
        max_level = row.i("MaxExpLevel10", 0) // 10
        if account_level < min_level:
            continue
        if max_level and account_level > max_level:
            continue
        return instance
    return None
