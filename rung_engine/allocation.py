"""Deterministic allocation: which profile should carry a specification.

Hard filters first, then an integer score made of four visible parts. No model call.

Hard filters, each with the reason shown wherever the profile is left out:

    disabled                the profile is switched off in Settings
    human only              the specification is marked human only, or every test under it is manual
    missing tag <t>         the specification requires a capability tag the profile does not carry
    missing tool <t>        the specification requires a Hermes toolset the profile does not declare
    author of <id>          the specification requires an independent carrier and the profile wrote it
                            or one of its tests
    at capacity <n> of <m>  the profile already carries <n> develop runs and open claims; <m> is its
                            At once limit

    tags        0..40  share of the specification's capability tags the profile carries
    load        0..20  20 when idle, minus 10 per develop run or open claim the profile carries now
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
    tools: tuple[str, ...] = ()
    at_once: int = 2
    claims: int = 0

    @property
    def load(self) -> int:
        return max(0, self.running) + max(0, self.claims)


@dataclass(frozen=True)
class Needs:
    """What a specification asks of its carrier."""
    spec: str = ""
    required_tags: tuple[str, ...] = ()
    required_tools: tuple[str, ...] = ()
    independent: bool = False
    authors: frozenset = frozenset()
    human_only: bool = False
    # (profile, rung id) for each author: the rung a reason names, the specification or one of its tests.
    authored: tuple[tuple[str, str], ...] = ()


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


def reasons(p: ProfileFacts, needs: Needs) -> list[str]:
    """Every hard filter the profile fails for these needs, in a fixed order. Empty means eligible."""
    out = []
    if not p.enabled:
        out.append("disabled")
    if needs.human_only:
        out.append("human only")
    missing = [t for t in dict.fromkeys(needs.required_tags or ()) if t and t not in set(p.labels)]
    if missing:
        out.append("missing tag " + ", ".join(missing))
    have = {t.lower() for t in p.tools}  # toolset names compare without case: Terminal is terminal
    missing = [t for t in dict.fromkeys(needs.required_tools or ()) if t and t.lower() not in have]
    if missing:
        out.append("missing tool " + ", ".join(missing))
    if needs.independent and p.name in needs.authors:
        # One id (`author of <id>`): the specification when the profile wrote it, else the first test it wrote.
        wrote = [rid for name, rid in needs.authored if name == p.name]
        out.append("author of " + (needs.spec if needs.spec in wrote or not wrote else wrote[0]))
    if p.load >= max(1, int(p.at_once)):
        out.append(f"at capacity {p.load} of {int(p.at_once)}")
    return out


def eligible(p: ProfileFacts, required=None, needs: Needs | None = None) -> tuple[bool, str]:
    needs = needs if needs is not None else Needs(required_tags=tuple(required or ()))
    why = reasons(p, needs)
    return (not why), "; ".join(why)


def rank(profiles, wanted_tags=(), required_tags=(), needs: Needs | None = None) -> list[Suggestion]:
    needs = needs if needs is not None else Needs(required_tags=tuple(required_tags or ()))
    out: list[Suggestion] = []
    for p in profiles:
        if reasons(p, needs):
            continue
        parts = {
            "tags": tags_part(p.labels, wanted_tags),
            "load": load_part(p.load),
            "reliability": reliability_part(p.completed, p.total),
            "cost": cost_part(p.cost),
        }
        out.append(Suggestion(p.name, sum(parts.values()), parts))
    out.sort(key=lambda s: (-s.score, s.profile))
    return out
