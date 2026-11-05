# Rung use-case catalog

Every use case Rung supports, by area. Each ID appears in the name of at least one passing test (lowercase, no hyphen: `PRJ-01` is `prj01`). The UC column names the acceptance use case that walks it end to end in the pane, where one exists; the other rows are covered by unit, API or smoke tests.

Actors: **you** (the human in the pane), **agent** (a Hermes profile in a chat or a develop run), **engine** (Rung's deterministic core), **tester** (a person or bot preparing or running tests).

## ONB Onboarding and first run

| ID | Use case | UC |
| --- | --- | --- |
| ONB-01 | With no projects, you see the start screen: `Try the sample project`, `New project`, dismiss. | UC1, UC13 |
| ONB-02 | You create the sample project on request; it is copied into Rung's data folder and opens on its home. | UC13 |
| ONB-03 | You dismiss the start screen; no sample data is created and the start screen does not return. | UC13 |
| ONB-04 | The `First green` checklist ticks from stored state, can be dismissed, and can be shown again from Settings. | UC13 |
| ONB-05 | From the start screen you reach a green test in the sample within 10 pane actions. | UC13 |
| ONB-06 | Every list that can be empty shows a label and at most one primary action. | UC13 |

## PRJ Projects

| ID | Use case | UC |
| --- | --- | --- |
| PRJ-01 | You create a project by choosing a folder; name, test command and profiles fill in and stay editable. | UC1 |
| PRJ-02 | A missing or unreadable folder, or a duplicate name, shows an error on that field and stores nothing. | |
| PRJ-03 | You pick a project from the picker; its rows show needs you, running, stale, coverage and last activity. | UC2 |
| PRJ-04 | Rung reopens the last opened project. | UC2 |
| PRJ-05 | You change a project's name, folder or test command; the change is recorded. | |
| PRJ-06 | You archive a project and restore it; an archived project is read only. | UC18 |
| PRJ-07 | You delete a project after typing its name; only Rung data goes, never the folder. | UC18 |

## NED Needs

| ID | Use case | UC |
| --- | --- | --- |
| NED-01 | You write a need; the build flow opens with later steps locked. | UC3 |
| NED-02 | You change a need's text; its requirements go stale and both versions stay in history. | UC3 |
| NED-03 | You retire a need with a reason; it and its rungs leave every active view and count. | UC19 |
| NED-04 | You restore a retired need with the statuses its rungs had. | UC19 |
| NED-05 | You open a need's read-out: intent, plan, delivered. | UC17 |
| NED-06 | You export the read-out as markdown. | UC17 |

## REQ Requirements

| ID | Use case | UC |
| --- | --- | --- |
| REQ-01 | The drafting agent suggests requirements; you accept or dismiss each. | UC3 |
| REQ-02 | You add a requirement yourself. | UC3 |
| REQ-03 | You edit a requirement's text in the editor. | UC3 |
| REQ-04 | `Approve all` stays locked until every requirement is decided, then opens Specifications. | UC3 |
| REQ-05 | You re-approve a stale requirement and it leaves Needs you. | UC3 |
| REQ-06 | You revert a recorded change; what it made stale is recomputed. | |

## SPC Specifications

| ID | Use case | UC |
| --- | --- | --- |
| SPC-01 | You choose `AI derives`; the draft shows Drafting then Drafted live. | UC4 |
| SPC-02 | You choose `I write, AI supports` and accept a supporting suggestion. | UC4 |
| SPC-03 | `Approve drafted` stays locked while a draft runs or a written one is missing. | UC4 |
| SPC-04 | You open `Edit specification` from an approved specification; saving records a new version. | UC4 |
| SPC-05 | You ask for a fresh draft of an AI-derived specification. | |
| SPC-06 | A failed draft shows its reason with `Retry` and `I write`. | UC14 |

## TST Tests

| ID | Use case | UC |
| --- | --- | --- |
| TST-01 | Proposed tests list type and pass rule; you accept each. | UC5 |
| TST-02 | You edit a proposed test; earlier acceptances stay. | UC5 |
| TST-03 | You add a Manual test with steps; command fields hide. | UC5 |
| TST-04 | An AI-judged test is marked as unable to release a gate. | UC5 |
| TST-05 | `Approve tests` stays locked until every test is accepted, then opens Develop. | UC5 |
| TST-06 | A command test shows `Seen failing` or `Not seen failing`. | UC16 |
| TST-07 | You run a command test once from its view and return to where you were. | |

## AGT Agents and allocation

| ID | Use case | UC |
| --- | --- | --- |
| AGT-01 | Develop shows ranked profiles with a whole-number score and its parts. | UC6 |
| AGT-02 | Disabled profiles and profiles missing a required tag are not suggested. | UC6 |
| AGT-03 | You pick a profile that is not the top one; the pick is stored with who made it. | UC6 |
| AGT-04 | You change labels, cost, max runs and enabled in Settings; values persist. | UC7 |
| AGT-05 | `Cancel` in Settings discards unsaved edits. | UC7 |
| AGT-06 | The ranking follows the saved settings. | UC7 |

## RUN Develop runs

| ID | Use case | UC |
| --- | --- | --- |
| RUN-01 | You press `Send`; the run shows under Running, live. | UC8 |
| RUN-02 | The run stops at the first pass and never exceeds max attempts. | UC8 |
| RUN-03 | Attempt `Details` shows files changed, commands, output and what fed the next attempt. | UC8 |
| RUN-04 | You cancel a running run; it stops and is recorded as cancelled. | |
| RUN-05 | An attempt ends Needs input with a reason; the run enters Needs you. | UC15 |
| RUN-06 | An attempt that changes nothing shows No change. | UC15 |
| RUN-07 | A worker that ends without a result shows Unknown, never pass or fail. | UC15 |
| RUN-08 | An attempt reports a missing capability; it shows Partial and files a proposed rung. | UC15 |
| RUN-09 | Coverage and tiles update live when a run ends. | UC8 |
| RUN-10 | One develop run with a real Hermes profile reaches a recorded outcome. | |

## EXE Executions and defects

| ID | Use case | UC |
| --- | --- | --- |
| EXE-01 | A failed execution shows its log, exit code and failing lines. | UC9 |
| EXE-02 | `Run again` records a new execution; history is unchanged. | UC9 |
| EXE-03 | `Raise defect` pre-links the failing runs; nothing is raised without that press. | UC9 |
| EXE-04 | A command that cannot start records Error with the reason; Error is neither pass nor fail. | UC14 |
| EXE-05 | A pass that no longer counts is struck through in the list and in its own view. | UC11 |
| EXE-06 | You cancel a running execution. | |

## MAN Manual tests

| ID | Use case | UC |
| --- | --- | --- |
| MAN-01 | You record Fail with a note; the specification stays unreleased. | UC10 |
| MAN-02 | You record Pass with a note; it counts only after human approval. | UC10 |
| MAN-03 | Every recording keeps its note, time and recorder. | UC10 |

## CHG Change, staleness, Needs you and proposals

| ID | Use case | UC |
| --- | --- | --- |
| CHG-01 | An upstream edit makes everything below it stale; old passes stop counting. | UC11 |
| CHG-02 | The Needs you count is identical in the status bar, the tile and the list. | UC11 |
| CHG-03 | `View change` shows before, after and what went stale. | UC11 |
| CHG-04 | You approve a stale rung as still valid. | UC11 |
| CHG-05 | An agent in a chat proposes a rung through a Rung tool; it shows as Proposed with proposer and source. | UC11 |
| CHG-06 | You accept or dismiss a proposal. | UC11 |
| CHG-07 | An agent cannot approve anything, including its own proposal. | UC11 |

## GTE Goal gate, CLI and agent tools

| ID | Use case | UC |
| --- | --- | --- |
| GTE-01 | `hermes rung check <spec>` exits non-zero while stale or unproven, naming the blocking rung; 0 once proven. | UC12 |
| GTE-02 | `hermes rung check --all` exits 0 only when every approved specification passes. | UC12 |
| GTE-03 | The check makes no model call. | UC12 |
| GTE-04 | `/goal gate add hermes rung check ...` fails, then passes, in a Hermes session. | UC12 |
| GTE-05 | `hermes rung status`, `tree`, `projects`, `where`, `run` and `send` work and match the pane. | |
| GTE-06 | An agent reads status, runs tests and checks a specification through the Rung tools. | |
| GTE-07 | `hermes rung demo reset` recreates the sample project only. | UC22 |
| GTE-08 | `hermes rung doctor` lists each check and exits 0 when all hold; a failing check is named with its fix. | UC22 |

## ACC Accessibility

| ID | Use case | UC |
| --- | --- | --- |
| ACC-01 | A full build-flow journey works with the keyboard only, with visible focus. | UC20 |
| ACC-02 | Every interactive element has an accessible name. | UC20 |
| ACC-03 | Dialogs take focus, keep it, close on Escape and return it. | UC20 |
| ACC-04 | No status relies on colour alone. | UC20 |
| ACC-05 | Text and controls meet 4.5:1 and 3:1 contrast in at least three themes. | UC20 |
| ACC-06 | Reduced motion stops pane animation. | UC20 |

## RES Resilience and performance

| ID | Use case | UC |
| --- | --- | --- |
| RES-01 | Data survives a full Desktop and backend restart. | UC21 |
| RES-02 | A backend restart mid run never leaves a run Running forever. | UC21 |
| RES-03 | A stale edit from a second window is refused with a way to reload. | UC21 |
| RES-04 | A store from the previous release opens intact. | UC21 |
| RES-05 | 500 rungs and 2,000 executions render home and ladder in under 1 second. | UC21 |
| RES-06 | Switching Hermes themes keeps the status colours distinct. | |
| RES-07 | Worst-case data (long text, unicode, empty, one, 1,000 rows) breaks no view. | |

## SEC Safety

| ID | Use case | UC |
| --- | --- | --- |
| SEC-01 | Only human-approved test commands run; an agent edit to a command needs re-approval before it runs. | |
| SEC-02 | Commands run in the project folder; API paths cannot reach outside Rung's store or the project folder. | |
| SEC-03 | Text from agents and drafts is shown as text, never executed or rendered as markup. | |
| SEC-04 | Tests and the demo reset never touch another store or project. | |

## RDY Readiness for testers

| ID | Use case | UC |
| --- | --- | --- |
| RDY-01 | `INSTALL.md` installs Rung on a clean Hermes home; validate passes; the pane opens. | UC22 |
| RDY-03 | Uninstalling Rung leaves Hermes working and keeps Rung's data unless removal is asked for. | |
