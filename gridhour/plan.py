"""Scoring half-hour slots and finding the best window to run a job.

A job is a name and a duration. Each slot gets a score from 0 (best in the window) to 1 (worst),
from carbon, price or both, and the best window is the run of slots with the lowest mean score
that starts no earlier than the current half hour.
"""
import re
from dataclasses import dataclass

from .grid import SLOT, floor_slot
from .safe import label

MODES = ("green", "cheap", "both")
MODE_LABEL = {"green": "greenest", "cheap": "cheapest", "both": "green + cheap"}


@dataclass
class Job:
    name: str
    minutes: int

    @property
    def slots(self):
        return max(1, -(-self.minutes // 30))

    def to_json(self):
        return {"name": self.name, "minutes": self.minutes}


DEFAULT_JOBS = [Job("Washing", 120), Job("Dishwasher", 180), Job("EV charge", 240), Job("Batch job", 60)]


@dataclass
class Window:
    job: Job
    first: int          # index of the first slot
    last: int           # index of the last slot (inclusive)
    score: float
    carbon: float       # mean gCO2/kWh, None if unknown
    price: float        # mean p/kWh, None if unknown
    start: object
    end: object


def parse_duration(text):
    """'2h', '1h30', '90m', '1.5h', '45' (minutes) -> minutes, rounded up to the half hour."""
    s = text.strip().lower().replace(" ", "")
    m = re.fullmatch(r"(?:(\d+(?:\.\d+)?)h)?(?:(\d+)(?:m|min)?)?", s)
    if not s or not m or not (m.group(1) or m.group(2)):
        raise ValueError("durations look like 2h, 1h30, 90m or 1.5h")
    mins = float(m.group(1) or 0) * 60 + int(m.group(2) or 0)
    if m.group(1) is None and m.group(2) and not s.endswith(("m", "min")) and int(m.group(2)) <= 12:
        mins = int(m.group(2)) * 60            # a bare small number means hours
    mins = int(-(-mins // 30) * 30)
    if not 30 <= mins <= 24 * 60:
        raise ValueError("a job runs between 30 minutes and 24 hours")
    return mins


def parse_job(text):
    """'Dryer 1h30' -> Job. The duration is the last word."""
    parts = text.strip().rsplit(None, 1)
    if len(parts) != 2:
        raise ValueError("type a name and a duration, e.g. 'Dryer 1h30'")
    name = (label(parts[0], 18) or "").strip()
    if not name:
        raise ValueError("give the job a name")
    return Job(name, parse_duration(parts[1]))


def fmt_duration(mins):
    h, m = divmod(int(mins), 60)
    if not h:
        return "%dm" % m
    return "%dh%02d" % (h, m) if m else "%dh" % h


def _norm(values):
    known = [v for v in values if v is not None]
    if not known:
        return [None] * len(values)
    lo, hi = min(known), max(known)
    span = (hi - lo) or 1.0
    return [None if v is None else (v - lo) / span for v in values]


def effective_mode(slots, mode):
    """Price modes fall back to green when there are no prices at all."""
    if mode != "green" and not any(s.price is not None for s in slots):
        return "green"
    return mode


def scores(slots, mode):
    mode = effective_mode(slots, mode)
    c = _norm([s.carbon for s in slots])
    if mode == "green":
        return c
    p = _norm([s.price for s in slots])
    if mode == "cheap":
        return p
    return [None if a is None or b is None else (a + b) / 2 for a, b in zip(c, p, strict=True)]


def _mean(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def now_index(slots, now):
    t = floor_slot(now)
    for i, s in enumerate(slots):
        if s.start == t:
            return i
    return 0 if slots and now < slots[0].start else len(slots)


def best_window(slots, sc, job, now):
    """The cheapest-scoring run of ``job.slots`` slots starting at or after the current half hour."""
    n = job.slots
    best = None
    for i in range(now_index(slots, now), len(slots) - n + 1):
        run = sc[i:i + n]
        if any(v is None for v in run):
            continue
        m = sum(run) / n
        if best is None or m < best[1] - 1e-9:
            best = (i, m)
    if best is None:
        return None
    i, m = best
    run = slots[i:i + n]
    return Window(job, i, i + n - 1, m, _mean([s.carbon for s in run]), _mean([s.price for s in run]),
                  run[0].start, run[-1].start + SLOT)


def window_now(slots, job, now):
    """Mean carbon and price if the job started right now (for 'saves 40%')."""
    i = now_index(slots, now)
    run = slots[i:i + job.slots]
    return _mean([s.carbon for s in run]), _mean([s.price for s in run])


def next_green(slots, now):
    """(slot, is_now) for the first green slot from the current half hour on, or None."""
    i = now_index(slots, now)
    for j in range(i, len(slots)):
        if slots[j].green:
            return slots[j], j == i
    return None


def green_until(slots, now):
    """End of the green run that contains now, or None if now is not green."""
    i = now_index(slots, now)
    if i >= len(slots) or not slots[i].green:
        return None
    j = i
    while j + 1 < len(slots) and slots[j + 1].green:
        j += 1
    return slots[j].end


def extremes(slots, now, attr):
    """(lowest slot, highest slot) by ``attr`` from now on."""
    fut = [s for s in slots[now_index(slots, now):] if getattr(s, attr) is not None]
    if not fut:
        return None, None
    return min(fut, key=lambda s: getattr(s, attr)), max(fut, key=lambda s: getattr(s, attr))


def fmt_in(delta):
    """timedelta -> 'now', '25m', '2h', '3h30', '1d4h'."""
    mins = int(round(delta.total_seconds() / 60))
    if mins <= 0:
        return "now"
    if mins < 60:
        return "%dm" % mins
    h, m = divmod(mins, 60)
    if h >= 24:
        d, h = divmod(h, 24)
        return "%dd%dh" % (d, h)
    m = m // 30 * 30 if m else 0
    return "%dh%02d" % (h, m) if m else "%dh" % h
