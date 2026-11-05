"""Deterministic allocation: which profile should carry a specification.

Hard filters first, then an integer score made of four visible parts. No model call.

    tags        0..40  share of the specification's capability tags the profile carries
    load        0..20  20 when idle, minus 10 per develop run the profile is carrying now
    reliability 0..20  share of the profile's past command executions that completed
                       (pass or fail, not an infrastructure error), smoothed toward 15
    cost        0..10  10 minus the profile's cost band (cost 0 is cheapest)

Ties break on profile name so the order never changes between calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field

TAGS_MAX = 40
LOAD_MAX = 20
RELIABILITY_MAX = 20
COST_MAX = 10


@dataclass(frozen=True)
class ProfileFacts:
    name: str
    labels: tuple[str, ...]
    cost: int
    enabled: bool
    running: int = 0
    completed: int = 0
    total: int = 0


@dataclass
class Suggestion:
    profile: str
    score: int
    parts: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"profile": self.profile, "score": self.score, "parts": dict(self.parts)}


def tags_part(labels, wanted) -> int:
    wanted = [t for t in dict.fromkeys(wanted or []) if t]
    if not wanted:
        return TAGS_MAX // 2
    have = set(labels or [])
    hit = sum(1 for t in wanted if t in have)
    return round(TAGS_MAX * hit / len(wanted))


def load_part(running: int) -> int:
    return max(0, LOAD_MAX - 10 * max(0, running))


def reliability_part(completed: int, total: int) -> int:
    return round(RELIABILITY_MAX * (completed + 3) / (total + 4))


def cost_part(cost: int) -> int:
    return max(0, min(COST_MAX, COST_MAX - int(cost)))


def eligible(p: ProfileFacts, required) -> tuple[bool, str]:
    if not p.enabled:
        return False, "disabled"
    missing = [t for t in (required or []) if t not in set(p.labels)]
    if missing:
        return False, "missing tag " + ", ".join(missing)
    return True, ""


def rank(profiles, wanted_tags=(), required_tags=()) -> list[Suggestion]:
    out: list[Suggestion] = []
    for p in profiles:
        ok, _ = eligible(p, required_tags)
        if not ok:
            continue
        parts = {
            "tags": tags_part(p.labels, wanted_tags),
            "load": load_part(p.running),
            "reliability": reliability_part(p.completed, p.total),
            "cost": cost_part(p.cost),
        }
        out.append(Suggestion(p.name, sum(parts.values()), parts))
    out.sort(key=lambda s: (-s.score, s.profile))
    return out
