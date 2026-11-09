# Roadmap

What Rung does not do yet, from the outside assessment of the hackathon build. Each open item names what it
depends on and what must be true before it counts as done. Built items move to `docs/verification.md` (their
contract) and `docs/features/README.md` (their tests); this file only holds what is still open. Updated after
every fully green verification run.

Rung's claim today: it verifies a declared integrated user journey against the code as it is now, and refuses
system completion when the required integration evidence is missing or failing. It does not claim multi-repository systems, authenticated approval or deployment readiness until the
items below that cover them are built.

## Usability

| ID | Open item | Depends on | Done when |
| --- | --- | --- | --- |
| B19 | Reusable task patterns and content search | B11 | a bug fix, feature and refactor template; search by id, phrase, failing check or profile |
| B20 | Team identity, isolated verification and sharing | a threat model; SYS-15 | approvals have a real authority and the verifier a real boundary |

## Correctness limits stated, not fixed

| ID | Open item | Depends on | Done when |
| --- | --- | --- | --- |
| R06 | Human approval is a workflow boundary, not an authenticated person | SYS-15 | approvals are bound to an authenticated role a worker cannot assume |
| R09 | Structural coverage can be mistaken for meaningful coverage | B14, SYS-07 | coverage names the obligations it counts and what lies outside them |
| R10 | Cancellation is not rollback; execution is not sandboxed | SYS-05, SYS-15 | a stopped run leaves the project folder as it was, and checks run in a declared sandbox |

## System capabilities (built: SYS-01 integration milestones, SYS-02 architecture, SYS-03 dependencies, SYS-04 plan, SYS-05 isolated runs, SYS-06 contract checks, SYS-07 journeys, SYS-08 regression, SYS-09 quality obligations, SYS-10 environment, SYS-11 change impact, SYS-12 system report, SYS-13 budgets and recovery)

| ID | Open item | Depends on | Done when |
| --- | --- | --- | --- |
| SYS-14 | Larger systems and several repositories | SYS-02 to SYS-12 | a multi-service example with recorded artifact versions and failure recovery (design: `docs/design/sys-14-multi-repository.md`) |
| SYS-15 | Team authority and stronger verifier isolation | B20, a threat model | workers cannot change the authority or the verification assets through their own access (design: `docs/design/sys-15-team-authority.md`) |
| SYS-16 | Operational readiness and deployment boundary | declared operational requirements | a tested candidate can still be marked not operationally ready (design: `docs/design/sys-16-operational-readiness.md`) |
