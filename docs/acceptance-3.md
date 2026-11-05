# Rung acceptance, stage 3

This file is the definition of done for Rung's stage 3 (Round 7 of `decisions.md`). It is frozen once Miguel approves it: its checksum is held outside the repo with `docs/use-cases-3.md` and `scripts/acceptance-3.sh`. If a check here looks wrong, stop and ask Miguel. Never edit it.

Done means, on one commit and in this order:

1. `scripts/acceptance.sh` prints `ACCEPTANCE: 22/22`.
2. `scripts/acceptance-3.sh` prints `ACCEPTANCE-3: 7/7` and `COVERAGE-3: PASS`.

## How acceptance runs

Everything in "How acceptance runs" of `docs/acceptance.md` applies here unchanged: one end-to-end file per use case (`tests/e2e/test_uc23_*.py` to `tests/e2e/test_uc29_*.py`), real pane in the Hermes Desktop dev build over CDP on `127.0.0.1:9222`, skips and xfails count as failures, a fresh `evidence/ucNN.png` per use case, an isolated Rung store and Hermes home, the `csvtidy` and `notes-sync` fixtures, deterministic drafting and worker stubs selected through Rung's configuration, and the deterministic chat model of `tests/e2e/stub_model.py` for Hermes sessions. Agent steps go through a real Hermes chat session in the isolated home calling Rung's tools through Hermes's own tool bridge; calling a tool handler or the hook function directly counts only for setup and assertions. "Needs you count" means the same number in the status bar chip, the Needs you tile and the dock.

Fixture profiles as in stage 2 (`coder`, `reviewer`, `writer`, `researcher`). The isolated Hermes home has a `coder` profile whose sessions have the `todo` and `kanban` toolsets enabled. Setup named in a step (an extra need, a test command, who drafted a specification) is made through the engine or the drafting stub, never by writing rows directly.

## UC23 Claim and report
1. A Hermes session as `coder` calls `rung_claim` for S-2.1, which is approved with a failing command test. The pane shows the claim on S-2.1 and under Running on home, with profile `coder` and the session's title.
2. `rung_claim` from a second session for S-2.1 is refused, naming the holding session. `rung_claim` for a draft specification and for a human-only specification are refused, each naming its reason. Nothing is stored for the refusals.
3. The first session calls `rung_report` for S-2.1. It is refused, naming the blocking rung; the claim stays open in the pane.
4. The command test passes (run from the pane). `rung_report` now succeeds; the pane shows the claim closed as reported with the passing execution's number; S-2.1's approval record is unchanged.
5. A new claim on S-2.1 from the second session, then `Release` in the pane: it closes as released.
6. The screenshot shows S-2.1 with its claim history.

## UC24 The done hook
1. A `coder` session claims S-2.1 while its command test fails. In that session the stub model calls, in turn: `todo_list` creating item `t1` "Finish S-2.1 date parsing" as pending; `todo_list` marking `t1` completed by id only; `todo_list` creating and completing an item whose content names S-2.1; `kanban_complete`; `rung_report`. Each of the last four is blocked: the tool result names S-2.1 and the blocking rung, and the session's todo list still shows `t1` pending.
2. In the same session, `todo_list` completing an item that names no claimed specification, and `rung_status`, go through.
3. A session without a claim completes a todo naming S-2.1 and is not blocked.
4. The command test passes. The same four calls from step 1 go through.
5. No model call is made by the hook: the stub model's request log grows only by the session's own turns.
6. The screenshot shows the session's transcript with a blocked call next to the pane.

## UC25 The docked pane
1. With the full page closed, open the Rung dock beside a chat. It shows project `csvtidy`, the Needs you count equal to the chip, the Needs you items, Running, and the ladder of N-1.
2. Click a Needs you item: the full page opens on that item. Setup: a second need N-2. Open N-2 in the full page: the dock's ladder follows to N-2. The dock's need picker switches back to N-1.
3. Start a develop run and a claim: both appear under Running in the dock without a reload, the run with its attempt and elapsed time; the run ends and leaves Running.
4. Collapse the dock, switch session, reopen: it is still on `csvtidy`. `Open Rung` opens the full page on the project home.
5. On the `notes-sync` project with nothing that needs you and nothing running, each section shows a label and at most one action. With no project at all, the dock shows a label and `Open Rung`.
7. Status colours and labels of every rung in the dock equal those of the same rung on home.
8. The screenshot shows the dock beside a chat with the full page closed.

## UC26 Allocation filters
1. Settings lists each profile with tool chips and an `At once` field. `coder`'s tools are pre-filled from its Hermes toolsets. Remove `browser` from `reviewer`, set `writer`'s `At once` to 1, `Save`, reload: the values persist.
2. Setup: S-2.1's current text comes from a fresh draft by the drafting stub running as profile `coder`, approved by you. On S-2.1 declare required tool `terminal` and `Independent carrier`.
3. Develop for S-2.1 ranks the eligible profiles and lists, under the ranking, every excluded profile with its reason: `coder` `author of S-2.1`, any profile without `terminal` `missing tool terminal`, a disabled profile `disabled`.
4. Give `writer` a running develop run elsewhere: it is listed `at capacity 1 of 1` and leaves the ranking; when the run ends it returns.
5. Mark S-1.1 human only: no profile is offered, each is listed `human only`, `Send` is not offered.
6. Settings shows, per profile, the specifications it is excluded from in `csvtidy`, each with its reason.
7. Through the REST API, pick, start run and a `rung_claim` from a `coder` session each refuse an excluded profile with the same reason the pane shows.
8. The screenshot shows Develop with the ranking and the excluded profiles.

## UC27 Revert and fresh draft in the pane
1. Edit R-2's text and approve. From R-2's `View change`, `Revert`: R-2's earlier text returns as a new version, the change list records the revert, and what went stale is shown as for any change.
2. Setup: R-1 in `AI derives` mode with its AI-derived S-1.1 approved. On S-1.1, `Fresh draft`: the specification shows drafting, then the stub's new draft as a new version waiting for approval; the previous version stays in its history.
3. The screenshot shows S-1.1 with its new draft.

## UC28 Cancel from the pane
1. Setup: an approved command test on S-1.1 whose command is `sleep 30`. Run it from the pane. `Cancel` on the execution: it stops within 5 seconds and is recorded as cancelled, never as pass or fail, and it does not count.
2. Start a develop run with the slow worker stub. `Cancel` on the run: it stops within 5 seconds and is recorded as cancelled; it leaves Running in the pane and the dock.
3. The screenshot shows the cancelled execution.

## UC29 Project form and Project settings
1. In `New project`, a folder that does not exist shows an error on the folder field; an unreadable folder shows one on the folder field; the name of an existing project shows one on the name field. After each, no project was stored.
2. In `csvtidy`'s Project settings, change the name, the folder (to a copy of the fixture) and the test command, `Save`. Reload: the values persist, the picker shows the new name, and the project's history records each change.
3. The screenshot shows Project settings after the reload.

## Global, checked in every use case
As in `docs/acceptance.md`: status colours never swapped and never the only signal; no em dashes in any UI text, tool result or export; no locked step reachable through the strip, the URL, the API or a tool; labels and data only in the pane and the dock.

## Coverage (`scripts/acceptance-3.sh`)
Every ID in `docs/use-cases-3.md` appears in the name of at least one test that passed in this run: the UC23 to UC29 JUnit files and a unit run of `tests` without `tests/e2e`. Name form: the lowercase ID without the hyphen, for example `test_clm03_report_refused_while_failing`.
