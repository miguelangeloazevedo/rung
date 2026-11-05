# Rung use-case catalog, stage 3

The use cases added by Round 7 of `decisions.md`. This file is frozen with `docs/acceptance-3.md` and `scripts/acceptance-3.sh`. `scripts/acceptance-3.sh` requires each ID below to appear in the name of at least one passing test (lowercase, no hyphen: `CLM-01` is `clm01`). The UC column names the acceptance use case that walks it end to end, where one exists; the other rows are covered by unit, API or smoke tests.

Actors as in `docs/use-cases.md`: **you**, **agent**, **engine**, **tester**.

## CLM Claims and the done gate

| ID | Use case | UC |
| --- | --- | --- |
| CLM-01 | An agent claims an approved specification with `rung_claim`; the claim shows with its profile and chat on the specification, under Running and in the dock. | UC23 |
| CLM-02 | `rung_claim` refuses a specification that is not approved, is human only, is held by another session, or whose profile a hard filter excludes; each refusal names its reason. | UC23 |
| CLM-03 | `rung_report` refuses while `rung check` fails, naming the blocking rung; the claim stays open. | UC23 |
| CLM-04 | `rung_report` succeeds once the specification is released; the claim closes as reported with the execution that proves it; the specification's approval is unchanged. | UC23 |
| CLM-05 | While a claimed specification's check fails, the hook blocks `rung_report`, `kanban_complete` from the claiming session, and a `todo_list` item set to completed that names the specification, with a message naming the specification and the blocking rung; the tool does not run. | UC24 |
| CLM-06 | A `todo_list` update that completes an item by id only is blocked when that id named a claimed specification earlier in the session. | UC24 |
| CLM-07 | Once the check passes, the same calls go through. | UC24 |
| CLM-08 | Tools that declare nothing done, and every call from a session without a claim, are never blocked. | UC24 |
| CLM-09 | The hook makes no model call and answers from the store, read only; an unreadable store lets the call through. | |
| CLM-10 | You release a claim from the pane; it closes as released and the hook stops applying to it. | UC23 |
| CLM-11 | `hermes rung claims` lists open claims; `hermes rung claims release <spec>` releases one; `--json` gives one document. | |
| CLM-12 | Claims and their outcomes are kept in the specification's history and survive a restart. | |

## ALC Allocation filters

| ID | Use case | UC |
| --- | --- | --- |
| ALC-01 | Settings lists each profile's tools as chips, pre-filled from its Hermes toolsets when Rung first lists it; you edit them and they persist. | UC26 |
| ALC-02 | A specification declares required tools on its view; a profile missing one is excluded: `missing tool <name>`. | UC26 |
| ALC-03 | Each profile has an `At once` limit; at its limit (develop runs plus open claims) it is excluded: `at capacity <n> of <m>`. | UC26 |
| ALC-04 | A specification can require an independent carrier; profiles that authored it or its tests are excluded: `author of <id>`. | UC26 |
| ALC-05 | A specification is human only when you mark it or when all its tests are manual; no profile is offered and each is listed as excluded: `human only`. | UC26 |
| ALC-06 | Develop lists every excluded profile with its reason under the ranking. | UC26 |
| ALC-07 | Settings shows, per profile, the specifications of the open project it is excluded from, each with its reason. | UC26 |
| ALC-08 | `Send`, pick, the API, the CLI and `rung_claim` refuse an excluded profile with the same reason. | UC26 |
| ALC-09 | Filters and ranking make no model call; the same store always gives the same order and the same reasons. | |
| ALC-10 | A stage 2 store migrates: profiles get no tools and `At once` 2, specifications require no tools, no independence and are not marked human only. | |

## DCK Docked pane

| ID | Use case | UC |
| --- | --- | --- |
| DCK-01 | The Rung dock opens beside the chat, collapses and reopens; it stays open across sessions and navigation. | UC25 |
| DCK-02 | The dock shows the open project and the Needs you count, equal to the status bar chip. | UC25 |
| DCK-03 | The dock lists the Needs you items; clicking one opens it in the full page. | UC25 |
| DCK-04 | The dock lists Running: develop runs with attempt and elapsed time, and open claims, live without a reload. | UC25 |
| DCK-05 | The dock shows the current need's ladder with each rung's status; a need picker switches it; it follows the last need opened in the full page. | UC25 |
| DCK-06 | `Open Rung` opens the full page on the project home. | UC25 |
| DCK-07 | With no project, nothing that needs you or nothing running, each section shows a label and at most one action. | UC25 |
| DCK-08 | The dock is reachable by keyboard, its sections are named regions, focus is visible, and every text meets WCAG 2.2 AA contrast on every theme. | UC25 |
| DCK-09 | From 237 to 360 px wide nothing overflows; long text is truncated with its full value on hover; a 500-rung project renders in the dock within 1 second. | |
| DCK-10 | Status colours and labels in the dock are the full page's. | UC25 |

## PNE Pane walk-throughs of stage 2 use cases

| ID | Use case | UC |
| --- | --- | --- |
| PNE-01 | REQ-06 in the pane: from `View change` you revert a change; the earlier text returns as a new version and the revert is recorded. | UC27 |
| PNE-02 | SPC-05 in the pane: you ask for a fresh draft of a specification; it shows drafting, then the new draft as a new version. | UC27 |
| PNE-03 | EXE-06 in the pane: you cancel a running test execution; it stops and is recorded as cancelled. | UC28 |
| PNE-04 | RUN-04 in the pane: you cancel a develop run; it stops and is recorded as cancelled. | UC28 |
| PNE-05 | PRJ-02 in the pane: a missing folder, an unreadable folder and a duplicate name each show an error on that field and store nothing. | UC29 |
| PNE-06 | PRJ-05 in the pane: you change a project's name, folder and test command in Project settings; the change persists and is recorded. | UC29 |
