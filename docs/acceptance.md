# Rung acceptance (v2)


Done means both commands exit 0, in this order, on one commit:

1. `scripts/acceptance.sh` prints `ACCEPTANCE: 22/22`.

## How acceptance runs

- `scripts/acceptance.sh` runs one end-to-end test file per use case: `tests/e2e/test_uc01_*.py` to `tests/e2e/test_uc22_*.py`.
- A use case passes only when its file collects at least one test and every test passes. Skipped, xfail or deselected tests count as failures.
- Each test drives the real Rung pane in the Hermes Desktop dev build (Chrome DevTools Protocol on `127.0.0.1:9222`) against a real Hermes backend with the Rung plugin installed. Calling the engine or the REST API alone does not count for the UI steps below; it is allowed for setup and for asserting stored state.
- Each use case writes a screenshot of its final state to `evidence/ucNN.png` during the run.
- Isolation: tests use their own Rung data store and a synthetic fixture project copied to a temporary folder. They never read or write the Rung data of Miguel's real profiles.
- Determinism: model calls are replaced by a deterministic drafting stub and a deterministic worker stub, selected through Rung's own configuration (the same seam a user would use), never by patching Rung or Hermes at runtime. Stub modes needed below (drafting failure, worker outcomes) are selected the same way. One real profile run belongs to the smoke pass, not to acceptance.
- Fixture data: project `csvtidy`, a small synthetic Python package with a pytest suite, under `tests/fixtures/csvtidy`. Seeded state where a use case needs it: N-1 "Clean a messy CSV export without opening a spreadsheet", R-1 "Detect the delimiter automatically", R-2 "Normalise every date to ISO 8601", R-3 "Never drop a row without reporting it", S-2.1 "Parse day-first and month-first dates with a --locale flag", T-2.1a (command) and T-2.1b (manual). Second project `notes-sync`.
- "Needs you count" below means the same number in all three places: the status bar chip, the Needs you tile and the number of items in the Needs you list.

## UC1 Create a project
1. With no projects, opening Rung shows the start screen with `Try the sample project`, `New project` and a dismiss control. `New project` opens the new project form.
2. Choose the fixture folder. Name, test command and profiles fill in from it (name from the folder, `pytest` detected, enabled profiles ticked); each stays visible and editable. Press `Create project`.
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
6. An approved specification's own view shows `Edit specification`; it opens the editor with the current text, and saving a change records a new version.

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
4. Opening T-2.1a's earlier pass shows its result struck through as no longer counting, in the execution list and in the execution's own view.
5. Approve S-2.1 as still valid: it leaves Needs you, the count drops by one everywhere, and T-2.1a needs a fresh run before R-2 counts as covered again.
6. An agent in an ordinary Hermes chat calls a Rung tool to propose a requirement. It appears under Needs you as Proposed, naming the proposer and the source chat; the count rises by one everywhere. `Accept` adds it to the ladder; a second proposal is `Dismiss`ed and leaves no rung. An agent cannot approve its own proposal.

## UC12 Rung as a goal gate
1. `hermes rung check S-2.1` exits non-zero while S-2.1 is stale or its tests have not passed since the last upstream change, and prints which rung blocks it.
2. After the tests pass, it exits 0.
3. `hermes rung check --all` exits 0 only when every approved specification in the project passes this check.
4. The check is computed by the engine alone: no model call happens during it.
5. The test also adds it as a gate with `/goal gate add` in a Hermes session and shows the gate fail, then pass.

## UC13 First run and the sample project
1. With no projects, `Try the sample project` creates one project from Rung's bundled synthetic sample, copied into Rung's own data folder, and opens its home. The sample holds one need whose requirements, specifications and tests are approved and whose command test has never run.
2. The home shows the `First green` checklist: `Write a need`, `Approve requirements`, `Approve specifications`, `Approve tests`, `First green test`. Each item's tick is computed from stored state, so the sample opens with four ticked.
3. From the sample home, running the test turns it green, ticks `First green test`, and the test counts the pane actions it took: 10 or fewer from the start screen.
4. Dismissing the checklist hides it; it stays hidden after a reload and can be shown again from Settings.
5. With no projects, the start screen's dismiss control opens the new project form and creates nothing. Stored state: zero projects and no sample data. The start screen does not come back while that store has a project or the dismissal is recorded.
6. Every list that can be empty (projects, needs, Needs you, running, executions, defects, archived, retired) shows a label and at most one primary action when empty, never a blank area.

## UC14 Error states: drafting and test launch
1. With the drafting stub set to fail, `AI derives` ends in Draft failed with the reason. `Retry` drafts again; `I write` switches that requirement to human authoring. The step's gate counts a failed draft as missing, and nothing else on the step is blocked.
2. Running a command test whose command cannot start (not found, or the project folder is missing) records an execution with status Error and the reason. Error is neither pass nor fail: it does not release the specification, does not count as a failed run toward defects, and enters Needs you.
3. Fixing the cause and pressing `Run again` records a new execution; the Error entry stays in history.
4. No error leaves a view without a way back or forward.

## UC15 Honest attempt outcomes
Each outcome below is produced by a worker stub mode and shown live in the run and in the attempt's `Details`.
1. Needs input: the attempt ends with a reason given by the worker. The run stops, shows Needs input with that reason, and enters Needs you. `Run again` starts a new run.
2. No change: the attempt finishes without changing any file. It shows No change, distinct from a test failure, and its tests are not re-run as if work had happened.
3. Unknown: the worker process ends without reporting a result. The attempt shows Unknown, never Pass or Fail, and the run never stays Running.
4. Partial: the worker reports a missing capability. The attempt shows Partial and files the named capability as a Proposed rung under Needs you, naming the run as its source; the attempt does not claim the specification.
5. Stored state: every outcome, its reason and the attempt it belongs to.

## UC16 Seen failing first
1. A command test whose first ever execution passes shows `Not seen failing`.
2. A command test that failed at least once before its first pass shows `Seen failing`.
3. The marker appears on the test, in its execution list and in the need read-out. It does not change whether the specification is released.

## UC17 Need read-out and export
1. Each need has a read-out view in three sections: Intent (the need text as written and its version), Plan (its requirements, specifications and tests), Delivered (per requirement: the execution that currently proves it, with status, time, carried by and the seen failing marker, or the reason it is not proven: stale, not run, failing, error, manual pending).
2. Every number and status in the read-out equals the stored state.
3. `Export` writes a markdown file whose content matches the view, and shows its path. The file contains no em dashes.

## UC18 Project archive, restore and delete
1. Archiving `notes-sync` removes it from the picker's default list and shows it under Archived. An archived project opens read only.
2. `Restore` brings it back with all its data.
3. `Delete` asks for the project name to be typed; until it matches, the delete button stays disabled. Deleting removes the project's Rung data only. The project folder and its files are untouched (checked byte for byte).
4. If the deleted project was the last opened one, Rung opens the start screen or the picker, never an error.

## UC19 Retire and restore a need
1. `Retire` on N-2 asks for a reason. After it, N-2 and every rung under it leave the home, the tiles, Needs you, coverage and `hermes rung check --all`; the Needs you count updates identically everywhere.
2. A Retired filter shows N-2 with its reason, read only, history intact.
3. `Restore` returns N-2 and its rungs with the statuses they had.

## UC20 Keyboard and screen reader
1. The UC3 journey up to `Approve all` completes with the keyboard only (key events through CDP, no clicks), with visible focus on every focused element.
2. On every view the end-to-end tests visit, the accessibility tree has no interactive element without an accessible name, and no status that is shown by colour alone.
3. Dialogs (defect form, delete confirmation, retire) take focus when opened, keep it inside, close on Escape and return focus to the control that opened them.
4. Status text and controls in the pane meet 4.5:1 (text) and 3:1 (controls) contrast in at least three Hermes themes, measured from rendered colours.
5. With reduced motion requested, no pane animation runs.

## UC21 Resilience
1. Data entered in the pane survives a full Desktop and backend restart.
2. Restarting the backend in the middle of a running develop run leaves that run Unknown or resumed after the restart, never Running forever.
3. An edit sent from a second window after the rung changed is refused with a message and a way to reload; nothing is silently overwritten.
4. A store written by the previous release (fixture `tests/fixtures/store-v1`) opens with every project, rung, execution and pick intact.
5. A seeded project with 500 rungs and 2,000 executions renders its home and its ladder in under 1 second each, measured in the pane.

## UC22 Ready for testers
1. `hermes rung demo reset` recreates the sample project to its initial state, touching no other project.
2. Following `INSTALL.md` on a clean Hermes home installs Rung from the repository, `hermes plugins validate` passes, and the pane opens on the start screen.
4. `hermes rung doctor` exits 0 on that install and lists each check it ran. With a project's folder removed it exits non-zero, naming that check and its fix.
5. The screenshot shows the sample home after the reset.

## Global, checked in every use case
- Status colours: pass green, fail red, stale violet, draft or not run neutral, needs you the accent or amber. Error, Unknown, Needs input, No change and Partial each carry a text label, so none relies on colour. Never swapped.
- No em dashes in any UI text or export.
- No step above can be passed by skipping a locked step through the strip, the URL or the API.
- Labels and data only: no explanatory, hint or how-it-works sentences in the pane.

1. Use-case coverage: every ID in `docs/use-cases.md` appears in the name of at least one test that passed in this commit's runs (the acceptance JUnit files, `tests` unit run and `tests/e2e/smoke` run). Name form: the lowercase ID without the hyphen, for example `test_prj01_prj02_create_with_defaults`.
2. Reviews closed: `docs/reviews/ux.md`, `docs/reviews/accessibility.md`, `docs/reviews/architecture.md` and `docs/reviews/worst-case.md` exist, each a findings table with a Status column; no row is `open`, and every `declined` row has a reason.
3. Tester material exists: `INSTALL.md` (ending with `hermes rung doctor`), `TESTING.md` (how to run each suite, how to reset, where evidence lands), `docs/features/README.md` (feature map: feature, view, test file, status) and `docs/charters.md` (at least one exploratory charter per feature map row).
4. `hermes plugins validate` passes.
