# Roadmap

What Rung does not do yet, from the outside assessment of the hackathon build. Each open item names what it
depends on and what must be true before it counts as done. Built items move to `docs/verification.md` (their
contract) and `docs/features/README.md` (their tests); this file only holds what is still open. Updated after
every fully green verification run.

Rung's claim today: it verifies a declared integrated user journey against the code as it is now, and refuses
system completion when the required integration evidence is missing or failing. It does not claim dependency
planning, isolated workspaces, multi-repository systems, authenticated approval or deployment readiness until the
items below that cover them are built.

## Usability

| ID | Open item | Depends on | Done when |
| --- | --- | --- | --- |
| B18, U10 | Dock for decisions and chat binding | enforcement health (built), next actions (built) | the dock says what the focused chat works on; binding is a reviewable action; a blocked completion opens its evidence |
| U02 | A first page that shows why to care | sample project (built) | the start screen previews the three states; the sample can be broken and repaired with no bot |
| U04 | Needs you as a decision surface | Needs you across projects (built) | each item names why it needs you and one recommended action; a retrying run is not in the inbox |
| U12 | Results you can try | read-out (built) | the read-out leads with the outcome, what changed and how to try it; nothing runs by itself |
| U13 | Hierarchy, not decoration | navigation contract (built) | one primary action per view, visible at 1280 by 800, in the dock and at 200 percent zoom |
| R11 | Allocation labels claim no more than their inputs | allocation (built) | no score part reads as money or a probability; exclusions are explained |
| B16, U08 | Clearer labels (attempts, concurrency, assigned profile, results and evidence, verified, cost preference) | an approved amendment to the frozen acceptance labels | the visible label, accessible name, docs and tests use the approved vocabulary |
| B19 | Reusable task patterns and content search | B11 | a bug fix, feature and refactor template; search by id, phrase, failing check or profile |
| B20 | Team identity, isolated verification and sharing | a threat model; SYS-15 | approvals have a real authority and the verifier a real boundary |

## Correctness limits stated, not fixed

| ID | Open item | Depends on | Done when |
| --- | --- | --- | --- |
| R06 | Human approval is a workflow boundary, not an authenticated person | SYS-15 | approvals are bound to an authenticated role a worker cannot assume |
| R07, B12 | Per-profile capacity is not workspace isolation | SYS-05 | concurrent runs work in their own workspaces and integrate under control |
| R09 | Structural coverage can be mistaken for meaningful coverage | B14, SYS-07 | coverage names the obligations it counts and what lies outside them |
| R10 | Cancellation is not rollback; execution is not sandboxed | SYS-05, SYS-15 | a stopped run leaves the project folder as it was, and checks run in a declared sandbox |

## System capabilities (SYS-01 is built: integration milestones)

| ID | Open item | Depends on | Done when |
| --- | --- | --- | --- |
| SYS-02 | Versioned architecture baseline and shared contracts | SYS-01 | a changed shared contract names the affected specifications and milestones and requires them to be checked or approved again |
| SYS-03 | Dependency graph and readiness | SYS-01 | cycles are refused; dependent work cannot start before its prerequisites are verified; unrelated work still runs |
| SYS-04 | Dependency-aware execution plan | SYS-03, B12 | ready work proceeds, blocked work cannot, a failed prerequisite stops only its dependents |
| SYS-05 | Isolated development and controlled integration | B04, B05, B12 | two incompatible changes that each pass alone cannot become a verified integrated system |
| SYS-06 | Contract checks at interfaces | SYS-02, SYS-01 | a producer and consumer mismatch is caught against the real interface artifacts |
| SYS-07 | Whole-journey acceptance coverage | SYS-01, B14 | an in-scope journey with missing or failing evidence blocks its milestone; excluded journeys stay visibly out of scope |
| SYS-08 | Regression policy | current evidence, SYS-01 | a locally passing feature that breaks an earlier required journey is blocked at integration |
| SYS-09 | Quality obligations | SYS-01, SYS-02 | a functionally passing system with an unmet measured threshold stays incomplete |
| SYS-10 | Reproducible integration environment and migrations | current evidence, SYS-01 | an environment mismatch or failed migration gives an actionable unknown or blocked result |
| SYS-11 | Change impact and selective revalidation | SYS-02, SYS-03, SYS-06 | relevant proof goes out of date, unaffected evidence stays, full revalidation is one action |
| SYS-12 | System acceptance report | SYS-02 to SYS-11 | a reviewer can see why a candidate is accepted; no aggregate hides an unknown |
| SYS-13 | Budgets and recovery across a plan | SYS-04, B17 | exhausted work stops honestly, independent work continues, a restart never reclassifies unknown work as passed |
| SYS-14 | Larger systems and several repositories | SYS-02 to SYS-12 | a multi-service example with recorded artifact versions and failure recovery (design: `docs/design/sys-14-multi-repository.md`) |
| SYS-15 | Team authority and stronger verifier isolation | B20, a threat model | workers cannot change the authority or the verification assets through their own access (design: `docs/design/sys-15-team-authority.md`) |
| SYS-16 | Operational readiness and deployment boundary | declared operational requirements | a tested candidate can still be marked not operationally ready (design: `docs/design/sys-16-operational-readiness.md`) |
