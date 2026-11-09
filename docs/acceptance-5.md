# Rung acceptance, stage 5

This file is the definition of done for Rung's stage 5: the rest of the outside assessment (`decisions.md` Round
committed, its checksum held outside the repo with `docs/use-cases-5.md` and `scripts/acceptance-5.sh`. If a
check here looks wrong, stop and ask Miguel. Never edit it.

Done means, on one commit and in this order:

1. `scripts/acceptance.sh` prints `ACCEPTANCE: 22/22`.
2. `scripts/acceptance-3.sh` prints `ACCEPTANCE-3: 7/7` and `COVERAGE-3: PASS`.
3. `scripts/acceptance-4.sh` prints `ACCEPTANCE-4: 7/7` and `COVERAGE-4: PASS`.
4. `scripts/acceptance-5.sh` prints `ACCEPTANCE-5: 20/20` and `COVERAGE-5: PASS`.
6. The public tree built by `.publish/scrub.py` scans `0 hits`, and a clean Hermes 0.23 home installs it from
   GitHub (install, validate, enabled, `rung doctor` PASS).

## Working through it

The use cases run in this fixed order (the goal's scope order, SYS items in dependency order). `scripts/acceptance-5.sh`
also prints `ACCEPTANCE-5 THROUGH: UCnn`, the last use case of the unbroken passing run from UC37, and
`COVERAGE-5 THROUGH UCnn` for the IDs of those use cases plus every `unit` row. A chain counts as fully green for
a private push and a public update when items 1 to 3 and 5 pass, `ACCEPTANCE-5 THROUGH` covers every use case
whose code is on the commit, its coverage passes, and `docs/roadmap.md` lists each later use case as open. Code
for a use case past the passing run never ships in a public update.

## Superseded criteria

None. Labels frozen by earlier rounds change only through the separate B16 amendment, once Miguel approves it.

## How acceptance runs

Everything in "How acceptance runs" of `docs/acceptance.md`, `docs/acceptance-3.md` and `docs/acceptance-4.md`
applies unchanged: one end-to-end file per use case (`tests/e2e/test_uc37_*.py` to `tests/e2e/test_uc56_*.py`), the
real pane over CDP on `127.0.0.1:9222`, skips and xfails count as failures, a fresh `evidence/ucNN.png` per
use case, an isolated store and Hermes home, synthetic fixtures (`csvtidy`, `linkpair`, the bundled sample) and the
deterministic drafting and worker stubs. Engine set-up through the engine is allowed; each use case's own steps
use visible controls unless a step says otherwise, and every state checked in the pane is also checked in the
store or through the engine.

## UC37 Quick task
1. On `csvtidy`'s home, `Quick task`: type an outcome and two checks (one command, one manual), choose a profile, Save. The store holds one new need, requirement, specification and two tests, all drafts; the card shows each text.
2. `Approve` names each id and version and approves them; a second test changes the requirement through the engine first and the approval is refused, the card reloads.
3. `Build and verify` starts the develop run (worker stub); the card shows the run and then Verified once both checks pass and the manual result is approved.
4. `Show full ladder` opens the need: the same five rungs, no copies. The card's text has no `specification`. Editing a check from the card resets its approval and the card no longer shows Verified.
5. The screenshot shows the card with its verification state.

## UC38 Need completeness
1. `csvtidy` N-1 has R-1 verified and R-2 approved with no specification: the need view says not complete and lists R-2 `no specification`.
2. Add and approve a specification under R-2 with no passing test: the list says R-2 `S-2.x not verified`. Retire R-2: it is listed as out of scope and the need is complete once R-1's specifications are verified.
3. Home and `hermes rung verify N-1` show the same verdict and list as the need view.
4. The screenshot shows the need with its open list.

## UC39 Dock
1. A chat with no claim: the dock leads with the project's next task, says the chat is not bound and offers `Bind to task`.
2. `Bind to task`, pick S-2.1, the confirmation names the chat and the profile; Cancel stores nothing; confirm opens one claim for that chat and profile.
3. The dock now leads with S-2.1: outcome, verification state, one blocker, the next action. The ladder is collapsed until opened.
4. With S-2.1's test failing, the blocker opens S-2.1's verification section.
5. The screenshot shows the bound dock.

## UC40 First page and sample
1. A fresh store: the start screen shows the sentence and the three-state preview.
2. `Try the sample project`, run its test: Verified. `Break the sample`: the result line says no bot ran, the test is Out of date; check again: Failed.
3. `Repair the sample`, check again: Verified. A second project's folder is byte for byte unchanged throughout.
4. The screenshot shows the sample home after the repair.

## UC41 Needs you
1. `csvtidy` holds one changed requirement, one proposal, one recorded manual result, one test that could not run and one run that needs an answer. Each item names its outcome, why it needs you, what changed or failed, and its recommended action button; `Open` is secondary.
2. A develop run retrying within its budget is not in Needs you; Home shows it under `Agent still working`.
3. Approve the recorded result through its action: the item leaves, chip, tile and list agree.
4. With every item resolved, the empty state names the unfinished work left.
5. The screenshot shows the items with their actions.

## UC42 Results and evidence
1. N-1 verified after a develop run that changed two files: the read-out leads with the outcome and verified behaviours, then `What changed` naming both files, `Checks run`, `Remaining manual review` and the code basis.
2. Declare a try instruction and command in project settings: the read-out shows them; nothing runs until a person starts the command.
3. The evidence section is collapsed and holds commands, profiles and times; each line is labelled automated, manual or model.
4. Export: the file lists open obligations, optional checks and evidence that no longer applies.
5. The screenshot shows the read-out.

## UC43 Allocation labels
1. On the Develop step, focus each score part of a suggestion: its description says what it measures in plain words; no part reads as money or a probability.
2. The suggestion explains why the top profile fits and why each excluded profile is excluded.
3. An independent specification describes independence as a different profile from the author; you override the profile with another eligible one.
4. The screenshot shows a suggestion with its explanation.

## UC44 Hierarchy
1. For every view the gallery captures, the test records the h1 and the elements marked primary: at most one, exactly one where the view has an action.
2. At 1280 by 800 and at the dock's width, the primary action is inside the viewport horizontally; no view scrolls the page horizontally; wide tables scroll inside their own region.
3. At 200 percent zoom (a 640 by 400 CSS viewport) the h1 and primary action stay reachable without horizontal page scrolling.
4. Every truncated element met on the way shows its full text when focused.
5. The screenshot shows a view at 200 percent zoom.

## UC45 Architecture baseline
1. On `linkpair`, the Architecture view adds components `api` and `page` with paths, and a contract `short link JSON` produced by `api` and consumed by `page`; approve both.
2. S-1.1 names `api`, S-2.1 names `page`; milestone M-1 names both.
3. Approve a new contract version: the result lists S-1.1, S-2.1 and M-1; each shows Out of date `contract_changed` until checked again (and M-1 approved again).
4. The screenshot shows the contract with its affected work.

## UC46 Dependencies
1. S-2.1 requires S-1.1: the edge shows on both specifications.
2. Adding S-1.1 requires S-2.1 is refused naming the cycle; a self edge and an unknown id are refused.
3. With S-1.1 failing, starting S-2.1's run is refused with the blocked path; another specification without dependencies starts.
4. The screenshot shows the refused start with its explanation.

## UC47 Isolated runs
1. Set `linkpair` runs to Isolated. A develop run of S-1.1 works in its own workspace; the project folder's files are unchanged while it runs and its passes are local.
2. A second run of S-2.1 changes the same file: integrating the first applies; integrating the second is refused as a conflict naming the file, nothing applied.
3. Two runs that change different files and each pass locally but break the journey together: both integrate, the affected specifications are checked on the project folder and the integrated result is not verified.
4. The screenshot shows the conflict.

## UC48 Plan
1. With S-2.1 requiring S-1.1 and S-3.1 independent, the plan lists S-1.1 Ready, S-2.1 Blocked by S-1.1, S-3.1 Ready.
2. `Start ready work` starts S-1.1 and S-3.1 only.
3. S-1.1 fails: S-2.1 stays Blocked, S-3.1 continues to Verified.
4. The screenshot shows the plan.

## UC49 Contract checks
1. The `short link JSON` contract gets an approved check that runs the real API handler and validates the consumer's expectation: it fails while both specifications' own tests pass; M-1 is blocked by it.
2. Repair the producer: the contract check passes and M-1 can verify.
3. A code change makes the contract check Out of date.
4. The screenshot shows the failing contract check.

## UC50 Journeys
1. M-1 lists journeys `shorten and follow` (in scope) and `bulk import` (out of scope, with a reason).
2. The in-scope journey without a check blocks M-1, named; adding its check and passing it clears that blocker.
3. The export lists `bulk import` as out of scope.
4. The screenshot shows the journeys.

## UC51 Regression baseline
1. M-2 names M-1 as its regression baseline.
2. A change that passes M-2's own checks but breaks M-1's journey: verifying M-2 runs M-1's checks too and M-2 is blocked `regression_failed`.
3. The screenshot shows the regression blocker.

## UC52 Quality obligations
1. M-1 gets a performance obligation: measure `p95_ms=(\d+)` from its output, threshold 200, workload and environment text.
2. The check prints `p95_ms=350`: M-1 is not verified and shows `350 ms against 200 under <workload>`; at `p95_ms=120` it verifies. No view says fast or secure.
3. The screenshot shows the unmet obligation.

## UC53 Environment
1. M-1 declares a probe (`python3 --version` must contain `Python 3`) and a migration command.
2. A probe expecting a version the machine does not have makes the run Could not verify `environment_mismatch` naming the probe; a failing migration blocks `migration_failed`.
3. With both satisfied, the run records each probe's actual output and verifies; a rerun uses the same setup.
4. The screenshot shows the environment mismatch.

## UC54 Change impact
1. M-1 covers `api` and `page`; a third component `docs` is outside it. Changing a file under `docs` leaves M-1 Verified.
2. Changing a file under `api` makes M-1 Out of date with the reason.
3. `Check everything` reruns every check; the milestone view states the limits of selection.
4. The screenshot shows the impact reason.

## UC55 System report
1. Export the system report for `linkpair`: every milestone with journeys, quality obligations, dependencies, environment, exclusions and manual decisions.
2. With one obligation out of date the report says not accepted and names it; with everything verified it says Accepted.
3. The screenshot shows the report view.

## UC56 Budgets and recovery
1. A plan budget of 2 attempts: the plan stops starting work when it is used and says so; verified work stays verified; model usage reads `unavailable` with the stub.
2. A run in progress when the engine restarts is Interrupted, never passed; resuming the plan skips verified specifications and starts the rest.
3. The screenshot shows the exhausted budget.
