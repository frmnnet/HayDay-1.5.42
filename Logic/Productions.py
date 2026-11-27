"""Production queues for buildings (StartProduction -> CollectProductions).

Each building queues productions keyed by the building object id. Every
production records ``started`` and ``ready`` times; collecting gives the
finished goods.
"""
from Logic import HomeObjects
from Logic.GameTime import now_seconds, seconds_to_ticks


class Production:
    """One production job in a building queue."""

    PRODUCE_TIME = 60  # seconds to complete (overridden by CSV)

    def __init__(self, good=0, started=None, ready=0, duration=None,
                 queued=False, finished=False):
        self.good = int(good)
        self.started = (
            now_seconds() if started is None else int(started))
        remaining = (
            int(duration)
            if duration is not None
            else max(0, int(ready or 0) - self.started)
        )
        self.duration = max(1, remaining or self.PRODUCE_TIME)
        self.ready = int(ready) if ready else self.started + self.duration
        self.queued = bool(queued)
        self.finished = bool(finished)

    def is_ready(self, now=None):
        now = now_seconds() if now is None else now
        return self.finished or (not self.queued and now >= self.ready)

    def to_dict(self):
        return {
            "good": self.good,
            "started": self.started,
            "ready": self.ready,
            "duration": self.duration,
            "queued": self.queued,
            "finished": self.finished,
        }

    @classmethod
    def from_dict(cls, d):
        if not d:
            return cls()
        return cls(
            good=d.get("good", 0),
            started=d.get("started", 0),
            ready=d.get("ready", 0),
            duration=d.get("duration"),
            queued=d.get("queued", False),
            finished=d.get("finished", False),
        )


def _seconds_remaining(production, now):
    return max(0, int(production.ready) - int(now))


def slot_count(building_row, rank):
    """Mirror ``LogicProcessingBuildingData::getSlotCount(rank)``.

    The row's ``Slots`` value is the rank-1 capacity and every valid rank adds
    one production slot.  The rank is clamped to the building's CSV
    continuation rows, as the client does through ``getMaxLevel``.
    """
    base = max(1, int(building_row.i("Slots", 1) or 1))
    max_rank = max(1, 1 + len(building_row.subs))
    rank = max(1, min(int(rank or 1), max_rank))
    return base + rank - 1


def encode_list(productions, now=None):
    """Encode a queue in ``LogicProcessingBuilding``'s JSON save format."""
    now = now_seconds() if now is None else int(now)
    active = []
    finished = []
    for production in productions:
        good = int(production.good or 0)
        if good <= 0:
            continue
        if production.finished:
            finished.append({"ID": good})
            continue
        total = max(1, int(production.duration))
        remaining = (
            total if production.queued
            else max(0, int(production.ready) - int(now))
        )
        if remaining <= 0:
            finished.append({"ID": good})
            continue
        active.append({
            "ID": good,
            "Timer": {
                "StartSeconds": total,
                "TicksLeft": seconds_to_ticks(remaining),
            },
        })
    result = {}
    if active:
        result["Productions"] = active
    if finished:
        result["FinishedProductions"] = finished
    return result


def decode_list(payload, now=None):
    """Decode one building's ``ProductionList`` into server productions."""
    now = now_seconds() if now is None else int(now)
    if not isinstance(payload, dict):
        return []
    result = []
    active = payload.get("Productions")
    if isinstance(active, list):
        for position, item in enumerate(active):
            if not isinstance(item, dict):
                continue
            try:
                good = int(item.get("ID") or 0)
            except (TypeError, ValueError):
                continue
            if good <= 0:
                continue
            timer = item.get("Timer")
            remaining = 0
            total = 0
            if isinstance(timer, dict):
                try:
                    from Logic.GameTime import ticks_to_seconds
                    remaining = ticks_to_seconds(
                        timer.get("TicksLeft") or 0)
                    total = max(0, int(timer.get("StartSeconds") or 0))
                except (TypeError, ValueError):
                    remaining = 0
                    total = 0
            total = max(1, total, remaining)
            queued = position > 0
            result.append(Production(
                good=good,
                started=now if not queued else now + total,
                ready=(
                    now + (remaining if remaining else total)
                    if not queued else now + total * 2),
                duration=total,
                queued=queued,
            ))
    finished = payload.get("FinishedProductions")
    if isinstance(finished, list):
        for item in finished:
            if not isinstance(item, dict):
                continue
            try:
                good = int(item.get("ID") or 0)
            except (TypeError, ValueError):
                continue
            if good > 0:
                result.append(Production(
                    good=good, started=now, ready=now,
                    duration=1, finished=True))
    return result


class ProductionManager:
    """Manages the {building_id: [Production, ...]} mapping."""

    def __init__(self, data=None, home_data=None):
        self.data = data if isinstance(data, dict) else {}
        self.home_data = home_data

    def _building_entry(self, building_id):
        if self.home_data is None:
            return None
        _, entry = HomeObjects.find_by_runtime_id(
            self.home_data, building_id)
        if entry is None or HomeObjects.object_type(entry) != 6:
            return None
        return entry

    def _sync_building(self, building_id, now=None):
        entry = self._building_entry(building_id)
        if entry is None:
            return
        entry["ProductionList"] = encode_list(
            self.get_queue(building_id), now=now)

    def _advance_queue(self, building_id, now=None):
        """Advance only the head job and promote queued slots sequentially."""
        now = now_seconds() if now is None else int(now)
        key = str(building_id)
        queue = self.get_queue(building_id)
        finished = [p for p in queue if p.finished]
        active = [p for p in queue if not p.finished]
        if not active:
            self.data[key] = [p.to_dict() for p in finished]
            self._sync_building(key, now)
            return finished

        if active[0].queued:
            # A queued job becomes the head only after the previous head
            # finishes.  Start it at that completion time.  An already-running
            # head must keep its original start even when an out-of-order
            # instant-complete appended a newer finished production.
            cursor = int(finished[-1].ready or 0) if finished else now
        else:
            cursor = int(active[0].started or now)
        if cursor <= 0:
            cursor = now
        pending = 0
        waiting = []
        for production in active:
            duration = max(1, int(production.duration))
            production.started = cursor
            production.ready = cursor + duration
            production.queued = pending > 0
            production.finished = False
            if production.ready <= now:
                production.finished = True
                finished.append(production)
            else:
                pending += 1
                waiting.append(production)
            cursor = production.ready
        ordered = finished + waiting
        self.data[key] = [p.to_dict() for p in ordered]
        self._sync_building(key, now)
        return ordered

    def active_count(self, building_id, now=None):
        self._advance_queue(building_id, now)
        return sum(
            1 for production in self.get_queue(building_id)
            if not production.finished)

    def advance(self, building_id, now=None):
        """Advance one building's queue to ``now`` and return its jobs."""
        return self._advance_queue(building_id, now)

    def sync_from_objects(self, now=None):
        """Load ``ProductionList`` from buildings and mirror server queues."""
        if self.home_data is None:
            return self
        now = now_seconds() if now is None else int(now)
        objects = self.home_data.setdefault("Objects", [])
        for index, entry in enumerate(objects):
            if HomeObjects.object_type(entry) != 6:
                continue
            building_id = HomeObjects.runtime_id_for(entry, objects)
            if building_id is None:
                building_id = 600000 + index
            key = str(building_id)
            raw_queue = self.data.get(key)
            if isinstance(raw_queue, list):
                queue = self._advance_queue(building_id, now)
            else:
                queue = decode_list(entry.get("ProductionList"), now)
                self.set_queue(building_id, queue)
                queue = self._advance_queue(building_id, now)
            entry["ProductionList"] = encode_list(queue, now)
        return self

    def get_queue(self, building_id):
        return [Production.from_dict(d) for d in self.data.get(str(building_id), [])]

    def set_queue(self, building_id, prods):
        self.data[str(building_id)] = [
            p.to_dict() if hasattr(p, "to_dict") else dict(p)
            for p in prods
        ]
        self._sync_building(building_id)

    def start(self, building_id, good, produce_time=60, now=None):
        now = now_seconds() if now is None else int(now)
        self._advance_queue(building_id, now)
        q = self.get_queue(building_id)
        active = [p for p in q if not p.finished]
        cursor = active[-1].ready if active else now
        p = Production(
            good=good,
            started=cursor,
            ready=cursor + int(produce_time),
            duration=int(produce_time),
            queued=bool(active),
        )
        q.append(p)
        self.set_queue(building_id, q)
        return p

    def ready_productions(self, now=None):
        """Yield (building_id, Production) for all ready jobs."""
        now = now_seconds() if now is None else now
        for key, queue in self.data.items():
            for p in self._advance_queue(key, now):
                if p.finished:
                    yield key, p

    def complete_all(self, now=None):
        """Mark ready jobs as collected: returns [(building_id, Production)]."""
        done = []
        for key in list(self.data.keys()):
            self._advance_queue(key, now)
            q = self.get_queue(key)
            remaining = []
            for p in q:
                if p.finished:
                    done.append((key, p))
                else:
                    remaining.append(p)
            self.set_queue(key, remaining)
        return done

    def complete_for(self, building_id, now=None):
        """Collect ready jobs from one building without touching others."""
        now = now_seconds() if now is None else now
        key = str(building_id)
        queue = self._advance_queue(building_id, now)
        done = []
        remaining = []
        for production in queue:
            if production.finished:
                done.append((key, production))
            else:
                remaining.append(production)
        self.set_queue(building_id, remaining)
        return done

    def ready_for(self, building_id, now=None):
        """Return ready jobs from one building without mutating the queue."""
        now = now_seconds() if now is None else now
        self._advance_queue(building_id, now)
        return [
            (str(building_id), production)
            for production in self.get_queue(building_id)
            if production.finished
        ]

    def complete_next(self, building_id, now=None):
        """Remove and return one finished job, matching the client command."""
        now = now_seconds() if now is None else now
        queue = self._advance_queue(building_id, now)
        for index, production in enumerate(queue):
            if not production.finished:
                continue
            queue.pop(index)
            self.set_queue(building_id, queue)
            return production
        self.set_queue(building_id, queue)
        return None

    def finish_active(self, building_id, index, now=None, auto_collect=False):
        """Instantly finish one active slot.

        ``auto_collect`` mirrors the client's instant-complete command: if the
        finished item fits in storage, it is removed from the building in the
        same operation so a later collect command cannot award it again.
        """
        now = now_seconds() if now is None else now
        queue = self._advance_queue(building_id, now)
        finished = [production for production in queue if production.finished]
        active = [production for production in queue if not production.finished]
        try:
            index = int(index)
        except (TypeError, ValueError):
            return None
        if index < 0 or index >= len(active):
            return None
        target = active[index]
        target.finished = True
        target.ready = now
        finished.append(target)
        active.pop(index)
        # Finishing the current head starts the next queued job now.  Other
        # slots keep their timers; instant-completing a queued slot must not
        # restart the job that is already running.
        if index == 0 and active:
            active[0].started = now
            active[0].ready = now + max(1, int(active[0].duration))
            active[0].queued = False
        ordered = finished + active
        if auto_collect and target in ordered:
            ordered.remove(target)
        self.set_queue(building_id, ordered)
        return target

    def __len__(self):
        return len(self.data)
