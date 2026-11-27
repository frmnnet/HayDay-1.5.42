"""Single synchronization pass for every persisted home timer."""
from Logic.GameTime import now_seconds


def sync(state, now=None, spawn_mystery=False):
    """Advance and mirror all timer-bearing subsystems to client objects.

    Callers should run this while holding ``state.lock``.  The function is
    idempotent and uses one clock value for every subsystem, so crop,
    production, animal, pet, building, tree, obstacle, shop, and achievement
    timers cannot drift against one another.
    """
    now = now_seconds() if now is None else int(now)
    data = state.home.data
    level = int(getattr(state.account, "exp_level", 1) or 1)

    from Logic import (
        Achievements, Forests, FruitTrees, HomeAnimals, HomeBuildings,
        HomeFields, MysteryBoxes, Pets, RoadsideStand, Storage, TruckOrders,
    )

    grown = HomeFields.advance(data, state.home.fields, now=now)

    state.home.productions.sync_from_objects(now)
    productions_ready = sum(
        1 for _key, _production
        in state.home.productions.ready_productions(now))

    HomeAnimals.sync_from_metadata(data, now)
    HomeBuildings.sync_timers(data, now)
    TruckOrders.normalize(data)
    Pets.sync(data, now)
    FruitTrees.sync(data, now)
    Forests.sync(data, now)
    RoadsideStand.ensure(data, level, now)
    Achievements.sync_time_lists(data, now)
    Storage.sync_rank_resources(data)
    if spawn_mystery:
        MysteryBoxes.sync(state, level, now)

    return {
        "now": now,
        "fields_ready": grown,
        "productions_ready": productions_ready,
    }
