# Rung use-case catalog, stage 5

The use cases added by the response to the outside assessment (`decisions.md` Rounds 22 to 24): usability that
lets a small task stay small, and the system-level capabilities SYS-02 to SYS-13 built on integration milestones.
This file is frozen with `docs/acceptance-5.md` and `scripts/acceptance-5.sh`. `scripts/acceptance-5.sh` requires
each ID below to appear in the name of at least one passing test (lowercase, no hyphen: `TSK-01` is `tsk01`). The
UC column names the acceptance use case that walks it end to end; `unit` rows are covered by unit tests only and
are required in every run.

Actors as in `docs/use-cases.md`: **you**, **agent**, **engine**, **tester**.

## TSK A small task stays small (B11, U01)

| ID | Use case | UC |
| --- | --- | --- |
| TSK-01 | From a project home, `Quick task` opens one card: `What should work?` (the outcome), `How will we check it?` (one to five checks, each a command or manual steps, editable in place) and the profile. Nothing is stored until Save. | UC37 |
| TSK-02 | Save creates one need, one requirement, one specification and its tests through the ordinary engine calls, as drafts; the card shows every text it created. | UC37 |
| TSK-03 | `Approve` on the card approves exactly the versions shown (each id and version is named); a text changed by anyone after the card loaded refuses the approval and reloads. | UC37 |
| TSK-04 | `Build and verify` is a separate action after approval; it starts the ordinary develop run, and the card shows the verification state of the task. | UC37 |
| TSK-05 | `Show full ladder` opens the same need; the ladder holds exactly the rungs the card created, no copies; the card never uses the word specification. | UC37 |
| TSK-06 | An edit to an approved check from the card resets its approval and makes earlier evidence count for nothing, under the same engine rules as the ladder. | UC37 |

## CMP Need-level completeness (B14)

| ID | Use case | UC |
| --- | --- | --- |
| CMP-01 | The engine reports a need as complete only when every approved requirement under it has at least one specification and every specification under it is verified now. | UC38 |
| CMP-02 | An approved requirement with no specification, or with a specification that is not verified, is listed by id with its reason; a retired requirement is listed as out of scope, never silently dropped. | UC38 |
| CMP-03 | The need view, Home and `hermes rung verify N-1` show the same verdict and the same open list. | UC38 |

## DOK Dock for decisions (B18, U10)

| ID | Use case | UC |
| --- | --- | --- |
| DOK-01 | The dock leads with the focused chat's task: its outcome, its verification state, one blocker and the next action; Needs you, Running and the ladder follow and the ladder starts collapsed. | UC39 |
| DOK-02 | The dock shows whether the focused chat holds a claim, naming the specification, or says it is not bound. | UC39 |
| DOK-03 | An unbound chat offers `Bind to task`: you pick a specification, see what binding means for this chat, and confirm; only then a claim opens for that chat and its profile. Nothing binds silently. | UC39 |
| DOK-04 | A blocked completion in the dock opens that specification's verification section. | UC39 |

## STR First page (U02)

| ID | Use case | UC |
| --- | --- | --- |
| STR-01 | The start screen shows one sentence on what Rung does and a three-state preview: a requested behaviour, a blocked check and verified evidence. | UC40 |
| STR-02 | The sample project home is labelled Sample and offers `Break the sample` and, once broken, `Repair the sample`; both change only the sample folder, never another project, and say no bot ran. | UC40 |
| STR-03 | After a pass, breaking the sample makes its test Out of date; checking again fails it; repairing and checking again verifies it, each state shown in the same verification section as any project. | UC40 |

## NYD Needs you as a decision surface (U04)

| ID | Use case | UC |
| --- | --- | --- |
| NYD-01 | Every Needs you item names the affected outcome, why it needs you, what changed or failed, and one recommended action with its own verb (`Review change`, `Review proposal`, `Approve result`, `Repair test setup`, `Answer the worker`); `Open` stays as a secondary route. | UC41 |
| NYD-02 | A develop run still retrying within its budget does not appear in Needs you; Home shows it as `Agent still working`. | UC41 |
| NYD-03 | An empty Needs you names how much unfinished work remains and where; it never reads as all done. | UC41 |
| NYD-04 | Resolving one item through its recommended action removes it and the counts converge. | UC41 |

## OUT Results and evidence (U12)

| ID | Use case | UC |
| --- | --- | --- |
| OUT-01 | The need read-out leads with the requested outcome and the verified behaviours, then `What changed` (files changed by the newest run), `Checks run`, `Remaining manual review`, and the code basis the evidence applies to. | UC42 |
| OUT-02 | A project may declare how to try the result (an instruction, optionally a command a person starts); the read-out shows it as declared and never runs anything by itself. | UC42 |
| OUT-03 | Commands, profiles and times sit in an expandable evidence section; automated results, manual observations and model commentary are labelled as such. | UC42 |
| OUT-04 | The exported read-out states open obligations, optional checks and evidence that no longer applies, and is readable without the pane. | UC42 |

## ALO Allocation that claims no more than its inputs (R11)

| ID | Use case | UC |
| --- | --- | --- |
| ALO-01 | Each score part has a plain description on focus and hover: tags matched, current load, share of past executions that completed (not a chance of success), configured cost preference (not money spent). | UC43 |
| ALO-02 | A suggestion explains why the top profile fits and why every excluded profile is excluded; no part is shown as money or a probability. | UC43 |
| ALO-03 | `Independent` is described as a different profile from the author, not an independent model or reviewer; the chosen profile stays overridable among eligible ones. | UC43 |

## HIE Hierarchy (U13)

| ID | Use case | UC |
| --- | --- | --- |
| HIE-01 | Every view in the gallery marks one primary action (or none on a read-only view) and its h1 names the page's question or object. | UC44 |
| HIE-02 | At 1280 by 800 and at the dock's width, each view's primary action is visible without horizontal scrolling; wide tables scroll inside their own region. | UC44 |
| HIE-03 | At 200 percent zoom each view keeps its h1 and primary action reachable without horizontal page scrolling. | UC44 |
| HIE-04 | Truncated text shows in full on keyboard focus as well as on hover. | UC44 |

## ARC Architecture baseline and shared contracts (SYS-02)

| ID | Use case | UC |
| --- | --- | --- |
| ARC-01 | A project holds components (name, responsibility, paths) and contracts (kind, producer, consumers, artifact paths, text), each versioned; approving a new version keeps the old ones in history. | UC45 |
| ARC-02 | Specifications and milestones name the components they touch. | UC45 |
| ARC-03 | Approving a changed contract lists every affected specification and milestone; each is Out of date (`contract_changed`) until checked again or, for a milestone, approved again. | UC45 |

## DEP Dependencies (SYS-03)

| ID | Use case | UC |
| --- | --- | --- |
| DEP-01 | A specification may require other specifications to be verified first; the edge is separate from the ladder. | UC46 |
| DEP-02 | A cycle, a self edge, an unknown id or an edge into another project is refused with the path named. | UC46 |
| DEP-03 | A develop run of a specification whose prerequisite is not verified is refused with the blocked path explained (`S-3.1 waits for S-2.1: Failed`); unrelated work still starts. | UC46 |

## ISO Isolated runs and controlled integration (SYS-05, B12)

| ID | Use case | UC |
| --- | --- | --- |
| ISO-01 | A project may set runs to `Isolated`: each develop run works in its own workspace copied from the project folder; the project folder is untouched while it runs. | UC47 |
| ISO-02 | Passes inside a workspace are local results; they never verify a specification. | UC47 |
| ISO-03 | `Integrate` applies a finished run's changes to the project folder only when the files it changed are unchanged there since it started; otherwise it is refused as a conflict, naming the files, and nothing is applied. | UC47 |
| ISO-04 | After an integration the affected specifications are checked on the project folder; two changes that each passed alone but break together end not verified. | UC47 |

## PLN Execution plan (SYS-04)

| ID | Use case | UC |
| --- | --- | --- |
| PLN-01 | The plan lists approved, unverified specifications in dependency order, each Ready, Blocked (by what), Running, Waiting for capacity or Verified. | UC48 |
| PLN-02 | `Start ready work` starts every Ready specification within each profile's limits and nothing else. | UC48 |
| PLN-03 | A failed prerequisite blocks only its dependents; independent specifications stay Ready. | UC48 |

## CON Interface contract checks (SYS-06)

| ID | Use case | UC |
| --- | --- | --- |
| CON-01 | A contract carries approved checks run against its actual artifacts (the producer's real output), recorded with the code basis and the contract version. | UC49 |
| CON-02 | A producer and consumer mismatch fails the contract check although each side's own tests pass; a milestone touching both components is blocked by it. | UC49 |
| CON-03 | A contract check from an older contract version or code basis is Out of date, never current. | UC49 |

## JRN Whole journeys (SYS-07)

| ID | Use case | UC |
| --- | --- | --- |
| JRN-01 | A milestone lists its user journeys, each In scope or Out of scope with a reason. | UC50 |
| JRN-02 | An in-scope journey with no check, a failing check or a missing required review blocks the milestone, named. | UC50 |
| JRN-03 | Out-of-scope journeys are shown and exported as out of scope, never counted as passed. | UC50 |

## RGR Regression policy (SYS-08)

| ID | Use case | UC |
| --- | --- | --- |
| RGR-01 | A milestone may name earlier milestones as its regression baseline, and optionally a full baseline command. | UC51 |
| RGR-02 | Verifying the milestone runs the baseline checks on the same code; a locally passing feature that breaks an earlier journey blocks it (`regression_failed`). | UC51 |

## QLT Quality obligations (SYS-09)

| ID | Use case | UC |
| --- | --- | --- |
| QLT-01 | A milestone check may be a quality obligation (security, performance, resilience, accessibility, other) with a measured value read from its output, a threshold, the workload and the environment, or a required human review. | UC52 |
| QLT-02 | A functionally passing milestone with an unmet threshold is not verified; the result states the measured value, threshold and workload, never `secure` or `fast`. | UC52 |

## ENV Integration environment (SYS-10)

| ID | Use case | UC |
| --- | --- | --- |
| ENV-01 | A milestone may declare its environment: probes (a command and the output it must contain) and a migration command. | UC53 |
| ENV-02 | Before checks run, the probes and migration run and their actual output is recorded with the run; a mismatch makes the run Could not verify (`environment_mismatch`) and a failed migration blocks (`migration_failed`), naming the probe. | UC53 |
| ENV-03 | A rerun uses the same declared setup; nothing is recorded as environment fact that a probe did not print. | UC53 |

## IMP Change impact (SYS-11)

| ID | Use case | UC |
| --- | --- | --- |
| IMP-01 | A milestone whose components declare paths judges its evidence on those paths (plus files outside every component); a change elsewhere leaves its evidence current. | UC54 |
| IMP-02 | A change inside its paths, or to a contract or dependency it uses, makes it Out of date with the reason. | UC54 |
| IMP-03 | `Check everything` reruns every milestone check regardless of impact; the limits of selection are stated in the milestone view. | UC54 |

## REP System acceptance report (SYS-12)

| ID | Use case | UC |
| --- | --- | --- |
| REP-01 | A project system report lists every milestone with its journeys, quality obligations, dependencies, environment, exclusions and manual decisions. | UC55 |
| REP-02 | The report says Accepted only when every required obligation is verified now; any unknown or out-of-date obligation is named and keeps it not accepted. | UC55 |

## BUD Budgets and recovery across the plan (SYS-13)

| ID | Use case | UC |
| --- | --- | --- |
| BUD-01 | A plan may set a budget of attempts and elapsed minutes; usage counts actual attempts and time, and actual model usage only when the host reports it (otherwise `unavailable`). | UC56 |
| BUD-02 | An exhausted budget stops starting work and says so; work already verified stays verified. | UC56 |
| BUD-03 | After a restart, a run that was in progress is `Interrupted` (unknown, never passed) and resuming the plan skips verified work without repeating it. | UC56 |

## DSN Design notes (SYS-14 to SYS-16)

| ID | Use case | UC |
| --- | --- | --- |
| DSN-01 | `docs/design/sys-14-multi-repository.md`, `sys-15-team-authority.md` and `sys-16-operational-readiness.md` each state the problem, the boundary, a proposed model, dependencies, acceptance criteria and what Rung must not claim until built. | unit |

## RDM Roadmap

| ID | Use case | UC |
| --- | --- | --- |
| RDM-01 | `docs/roadmap.md` lists every brief item not done (B, SYS, R and U ids), each with its dependency and acceptance criterion; every SYS id appears in it or in `docs/verification.md` as built. | unit |
