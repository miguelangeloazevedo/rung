# Rung acceptance, stage 4

This file is the definition of done for Rung's stage 4 (Rounds 10 to 13 of `decisions.md`). It is frozen once Miguel approves it: its checksum is held outside the repo with `docs/use-cases-4.md` and `scripts/acceptance-4.sh`. If a check here looks wrong, stop and ask Miguel. Never edit it.

Done means, on one commit and in this order:

1. `scripts/acceptance.sh` prints `ACCEPTANCE: 22/22`.
2. `scripts/acceptance-3.sh` prints `ACCEPTANCE-3: 7/7` and `COVERAGE-3: PASS`.
3. `scripts/acceptance-4.sh` prints `ACCEPTANCE-4: 7/7` and `COVERAGE-4: PASS`.
5. A clean Hermes 0.23 home installs Rung from the public repository and opens the pane.

## Superseded criteria

`docs/acceptance.md` UC13 step 5 and `docs/use-cases.md` ONB-03 are superseded by FST-02 (Round 12): with no projects, the start screen's cross leaves Rung for the view the person came from and creates nothing; the start screen shows again on the next open until a project exists. `tests/e2e/test_uc13_*.py` asserts the FST-02 behaviour for that step; every other step of UC13 is unchanged. Nothing else in the earlier acceptance files changes.

## How acceptance runs

Everything in "How acceptance runs" of `docs/acceptance.md` and `docs/acceptance-3.md` applies here unchanged: one end-to-end file per use case (`tests/e2e/test_uc30_*.py` to `tests/e2e/test_uc36_*.py`), the real pane in the Hermes Desktop dev build over CDP on `127.0.0.1:9222`, skips and xfails count as failures, a fresh `evidence/ucNN.png` per use case, an isolated Rung store and Hermes home, synthetic fixtures, deterministic drafting and worker stubs selected through Rung's configuration. Bot actions in these tests run through the drafting stub as a named profile; a Suggest that runs through a real Hermes profile is covered by a smoke test against the stub model.

Pane steps use visible controls (click, keyboard) unless a step says it opens a view directly. `window.__rungNavigate` is allowed only to set up the starting view.

## UC30 Route walk
1. A test walks every view and state the gallery captures (start screen, Needs you, project home, every build step, every rung kind, every editor, runs, attempts, executions, read-out, change, retired needs, project settings, settings, archive, a missing rung, run, attempt, execution and change, an unknown view). For each it records the h1, where focus is, and every visible exit.
2. From each, it takes every visible exit (Back, Cancel, `Back to X`, the project name, Home) and Escape. Each lands on the view the person came from or the parent named by Round 11, never on a form already left, never in another project, never on Loading for more than 2 seconds, and focus is on the new view's h1.
3. Missing destinations and the unknown view show the missing page with Back, Home and Projects.
4. Breadcrumbs, the step strip and the rail mark the current item on every view that has them.
5. The screenshot shows the missing page for a missing execution.

## UC31 Typed text, dialogs and results
1. On each New form and editor, type text and leave by the rail, the header, the dock and the status bar chip: each asks Discard or Keep editing; Keep editing keeps the text; Discard leaves. Cancel leaves without asking. Save moves on without asking and shows the result line.
2. Open Raise defect and Retire, type a title or reason, press Escape, the cross and click outside: each asks; Cancel does not. While a dialog is open, Tab stays inside it.
3. New project with an existing name and a missing folder: each field shows its error, is marked invalid with the error tied to it, and focus is on the first invalid field.
4. The screenshot shows the Discard or Keep editing question over a typed requirement.

## UC32 Needs you front page
1. Setup: three projects through the engine: one with two items that need you and a running develop run, one with one item, one with nothing waiting and one stale rung; one archived project.
2. Open Rung: it shows `Needs you` with the total 3, the two projects with items grouped and counted, the running marker, the third under `Nothing waiting` with its counts, and `Projects` with each covered count and `Archived 1`. The total equals the status bar chip and the dock.
3. `Open` on an item opens it in its project; Back returns to `Needs you`. `Open project` opens its home; Back returns to `Needs you`. From any project view, one action reaches `Needs you`.
4. Approve the item in the second project from its page: on return, `Needs you` shows total 2 and the second project under `Nothing waiting`, without a reload.
5. The screenshot shows `Needs you` with the three projects.

## UC33 First install
1. A fresh store: Rung opens on the start screen with `Try the sample project`, `New project` and the cross. The cross returns to the chat the test came from; stored state has zero projects; opening Rung again shows the start screen.
2. With visible controls only: `New project` with a copy of the `csvtidy` fixture, then a need, one requirement, its specification, a command test, approve each, run: the test passes and `First green test` ticks. The test records each control's label and checks it matches the same control's label elsewhere in the pane.
3. Every empty list and section met on the way shows a label naming what is missing and one action; the walk records each.
4. The screenshot shows the first green test.

## UC34 Paste text
1. On `csvtidy`'s home, `Paste text`, paste a requirement-shaped sentence, `Place`: the dialog shows `Requirement` under N-1 with one line why. `Open as new requirement` opens New requirement under N-1 with the text filled in; nothing is stored until Save.
2. The stub places a second text under a retired need: that place is not offered; you choose N-1 and the kind `Specification` under R-1 instead, and the form follows.
3. Cancel in the dialog and in the form stores nothing; leaving the form with its text asks first.
4. The screenshot shows the placed text with its kind and parent.

## UC35 Draft on New forms
1. On New need, New requirement, New specification and New test, `Draft` fills each empty field from the parent chain and shows the drafting profile.
2. With typed text in one field, `Draft` asks Replace or Keep; Keep leaves the typed text and fills only the empty fields.
3. A slow stub draft: Cancel stops it; the form keeps what was typed and stores nothing. A failing stub draft shows its reason and Retry.
4. The screenshot shows a drafted New specification with its profile.

## UC36 Suggest
1. Setup: N-1's requirements were drafted by the stub as `writer` and approved. `Suggest` on N-1: `writer` is listed excluded as `author of R-1`, a disabled profile `disabled`; the best ranked eligible profile runs; the result shows exactly three requirements, the profile and why.
2. Accept one: a draft requirement appears under N-1 waiting for approval. Dismiss one. The third stays proposed. Nothing else changed in the ladder.
3. Add a requirement while a slow Suggest runs: the result is marked `Changed since`; an item can still be accepted.
4. A slow Suggest: Cancel stops it within 5 seconds; it is recorded as cancelled and proposes nothing. While it runs it counts toward the profile's `At once`.
5. Disable every eligible profile: `Suggest` says no profile can suggest, lists each profile with its reason, and runs nothing.
6. `rung check` and the done hook give the same answer before and after every step above.
7. The screenshot shows the three suggestions with the profile and why.

## Global, checked in every use case
As in `docs/acceptance.md`: status colours never swapped and never the only signal; no em dashes in any UI text, tool result or export; no locked step reachable through the strip, the URL, the API or a tool; labels and data only in the pane and the dock; one name per thing.

## Coverage (`scripts/acceptance-4.sh`)
Every ID in `docs/use-cases-4.md` appears in the name of at least one test that passed in this run: the UC30 to UC36 JUnit files and a unit run of `tests` without `tests/e2e`. Name form: the lowercase ID without the hyphen, for example `test_bot08_suggest_with_no_eligible_profile`.
