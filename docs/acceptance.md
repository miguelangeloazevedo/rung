# Rung v1 acceptance

This file is the definition of done for Rung v1. It is frozen: its checksum is held outside the repo and checked by the goal gate. If a check here looks wrong, stop and ask Miguel. Never edit it.

## How acceptance runs

- `scripts/acceptance.sh` runs one end-to-end test file per use case: `tests/e2e/test_uc01_*.py` to `tests/e2e/test_uc12_*.py`.
- A use case passes only when its file collects at least one test and every test passes. Skipped, xfail or deselected tests count as failures.
- Each test drives the real Rung pane in the Hermes Desktop dev build (Chrome DevTools Protocol on `127.0.0.1:9222`) against a real Hermes backend with the Rung plugin installed. Calling the engine or the REST API alone does not count for the UI steps below; it is allowed for setup and for asserting stored state.
- Each use case writes a screenshot of its final state to `evidence/ucNN.png` during the run.
- Isolation: tests use their own Rung data store and a synthetic fixture project copied to a temporary folder. They never read or write the Rung data of Miguel's real profiles.
- Determinism: model calls are replaced by a deterministic drafting stub and a deterministic worker stub, selected through Rung's own configuration (the same seam a user would use), never by patching Rung or Hermes at runtime. One real profile run belongs to the smoke pass, not to acceptance.
- Fixture data: project `csvtidy`, a small synthetic Python package with a pytest suite, under `tests/fixtures/csvtidy`. Seeded state where a use case needs it: N-1 "Clean a messy CSV export without opening a spreadsheet", R-1 "Detect the delimiter automatically", R-2 "Normalise every date to ISO 8601", R-3 "Never drop a row without reporting it", S-2.1 "Parse day-first and month-first dates with a --locale flag", T-2.1a (command) and T-2.1b (manual). Second project `notes-sync`.
- "Needs you count" below means the same number in all three places: the status bar chip, the Needs you tile and the number of items in the Needs you list.

## UC1 Create a project
1. With no projects, opening Rung shows the new project form.
2. Enter name `csvtidy`, the fixture folder, test command `pytest`, tick at least one profile, press `Create project`.
3. The empty project view shows with `Write the first need` as its action.
4. Stored state: one project with exactly those values.

## UC2 Pick an ongoing project
1. With `csvtidy` and `notes-sync` seeded, the header project name opens the picker.
2. Each picker row shows needs you, running, stale, covered x of y and last activity, and the numbers equal the stored state.
3. Clicking `notes-sync` opens its home with its own needs and tiles; nothing from `csvtidy` is shown.
4. Reopening Rung after switching opens `notes-sync` (last project).

## UC3 Add a need and iterate requirements
1. `New need` opens the build flow on step Need. The strip reads `Need · Requirements · Specifications · Tests · Develop` and the later steps are locked.
2. Write "Merge two CSV exports by a shared key". The drafting stub suggests R-4 "Match rows by a chosen key column", R-5 "Report keys found in only one file", R-6 "Keep the first file's column order". Accept two, dismiss one, add the dismissed one back with `New requirement`.
3. Edit R-5's text in the requirement editor; Approve returns to the Requirements step with the new text.
4. The Specifications step stays locked until `Approve all`; after it, the step opens.
5. Stored state: need N-2 with three approved requirements, each linked to N-2, with the edited text kept.
6. Modify the need: change N-2's text to "Merge two or more CSV exports by a shared key". R-4 to R-6 become Stale and enter Needs you; the need's change view shows before and after; re-approving each requirement clears it. Stored state: both need versions in history.

## UC4 Specifications: AI derives or I write
1. On the Specifications step choose `AI derives` for two requirements and `I write, AI supports` for one.
2. The two AI drafts show Drafting, then Drafted, without a page reload.
3. `Approve drafted` is locked while any draft is drafting or the human-written one is missing.
4. Write the third specification in the editor; the supporting suggestion can be accepted. Approve returns to the step.
5. `Approve drafted` unlocks; pressing it opens the Tests step. Stored state: three approved specifications, each linked to its requirement, with the author recorded as human or agent.

## UC5 Tests
1. The Tests step lists the proposed tests per specification with type and pass rule.
2. `Approve tests` is locked until every test is accepted.
3. `Edit` on a proposed test opens the test editor; change its command and save; the step shows the new command and keeps earlier acceptances.
4. `Add test` creates a Manual test with steps; switching the type to Manual hides the command fields.
5. An AI-judged test can be added but is marked as unable to release a gate.
6. After all are accepted, `Approve tests` opens the Develop step.

## UC6 Pick an agent from the suggestions
1. The Develop step shows, per specification, the ranked suggested profiles with a whole-number score and its parts (tags, load, reliability, cost).
2. Disabled profiles and profiles missing a required tag are not suggested.
3. Pick a profile that is not the top suggestion. The row shows it as picked by you.
4. After the run (UC8) the execution's "carried by" is the picked profile, and the pick is stored with who made it.

## UC7 Configure agents
1. Settings lists profiles with label chips, cost, max runs and an enabled toggle.
2. Add a label to one profile, remove one from another, change a cost, disable a profile, `Save`.
3. Reload: the values persist.
4. The Develop step ranking changes accordingly: the disabled profile disappears and the score parts reflect the new labels and cost.
5. `Cancel` discards unsaved edits.

## UC8 Develop until green
1. `Send` starts a supervised run for one specification; the row and home show it under Running.
2. The worker stub fails attempt 1 and passes attempt 2. Both attempts and their test executions are recorded and shown live.
3. The run ends on its own on the first pass; it never exceeds the profile's max attempts.
4. The result view shows the attempts; `Details` on attempt 1 shows files changed, commands, test output and what was fed to attempt 2.
5. Coverage for the requirement becomes Covered and the tiles update without a reload.

## UC9 A run fails
1. On a test with failed executions, opening a failed run shows its log with exit code and the failing lines.
2. `Run again` starts a new execution shown live, ending in a new history entry; earlier entries are unchanged.
3. `Raise defect` opens the defect form with the failing runs pre-linked; `Raise` stores a defect linked to the test, the specification and those runs.
4. No defect is ever created without that press.

## UC10 Manual test
1. Opening T-2.1b shows its steps, `Pass` and `Fail`, and an evidence note.
2. Record `Fail` with a note: the test shows Fail and the specification is not released.
3. Record `Pass` with a note: the result is pending until a human approves it; only after approval does it count.
4. Stored state: both recordings in history with their note, time and recorder.

## UC11 Change upstream, staleness, Needs you
1. Edit R-2's text. S-2.1 and T-2.1a become Stale; T-2.1a's last pass stays in history but no longer counts; coverage for R-2 drops.
2. The Needs you count rises by one and is identical in all three places.
3. `View change` shows before and after and the list of what went stale.
4. Approve S-2.1 as still valid: it leaves Needs you, the count drops by one everywhere, and T-2.1a needs a fresh run before R-2 counts as covered again.
5. An agent in an ordinary Hermes chat calls a Rung tool to propose a requirement. It appears under Needs you as Proposed, naming the proposer and the source chat; the count rises by one everywhere. `Accept` adds it to the ladder; a second proposal is `Dismiss`ed and leaves no rung. An agent cannot approve its own proposal.

## UC12 Rung as a goal gate
1. `hermes rung check S-2.1` exits non-zero while S-2.1 is stale or its tests have not passed since the last upstream change, and prints which rung blocks it.
2. After the tests pass, it exits 0.
3. `hermes rung check --all` exits 0 only when every approved specification in the project passes this check.
4. The check is computed by the engine alone: no model call happens during it.
5. The test also adds it as a gate with `/goal gate add` in a Hermes session and shows the gate fail, then pass.

## Global, checked in every use case
- Status colours: pass green, fail red, stale violet, draft or not run neutral, needs you the accent or amber. Never swapped.
- No em dashes in any UI text.
- No step above can be passed by skipping a locked step through the strip, the URL or the API.
