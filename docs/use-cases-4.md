# Rung use-case catalog, stage 4

The use cases added by Rounds 10 to 13 of `decisions.md`: the navigation contract, the Needs you front page, first install and bot help. This file is frozen with `docs/acceptance-4.md` and `scripts/acceptance-4.sh`. `scripts/acceptance-4.sh` requires each ID below to appear in the name of at least one passing test (lowercase, no hyphen: `NAV-01` is `nav01`). The UC column names the acceptance use case that walks it end to end, where one exists; the other rows are covered by unit, API or smoke tests.

Actors as in `docs/use-cases.md`: **you**, **agent**, **engine**, **tester**.

## NAV Navigation contract

| ID | Use case | UC |
| --- | --- | --- |
| NAV-01 | Every view and state has a visible way out (Back, Cancel or a named `Back to X`), and Escape takes the same action. | UC30 |
| NAV-02 | Back, Cancel and Escape return to the view you came from, else the view's parent; leaving adds no history entry. | UC30 |
| NAV-03 | A form or editor is never returned to by Back once left, and Back never crosses into another project. | UC30 |
| NAV-04 | `Back to X` always goes to X; the build steps name their Back after the step they return to. | UC30 |
| NAV-05 | Leaving a form or editor that holds typed text, by any route other than its Cancel, asks Discard or Keep editing; Keep editing keeps the text; Cancel and the move after a save do not ask. | UC31 |
| NAV-06 | A dialog closes with its view; its cross, Escape and a click outside ask before dropping typed text; its Cancel does not; the rest of the pane is inert while it is open. | UC31 |
| NAV-07 | A missing rung, run, attempt, execution, change or project, a failed load and an unknown view show one page naming what is missing, with Back, Home and Projects; it never stays on Loading. | UC30 |
| NAV-08 | Each view has one h1 naming the page after the project name; focus moves to it on every view change and on entering Rung. | UC30 |
| NAV-09 | Breadcrumbs, the step strip and the rail mark the current item; the project name in the header is the way to the project list. | UC30 |
| NAV-10 | A refused save marks each field it names, ties the error to the field and focuses the first one. | UC31 |
| NAV-11 | Create, save and raise actions show a result line on the view they land on, until the next view change. | UC31 |
| NAV-12 | A cross only closes: it never creates or opens a form. | UC33 |
| NAV-13 | The route walk visits every view and state of the gallery and leaves each one by every visible exit and by Escape, without Loading, a dead end or a lost focus. | UC30 |

## FRT Front page

| ID | Use case | UC |
| --- | --- | --- |
| FRT-01 | With at least one project, Rung opens on `Needs you`: every item that needs you across open projects, grouped by project, with the total. | UC32 |
| FRT-02 | Each project group shows its count, what is running and `Open project`; each item shows its id, text, what it needs from you and `Open`, which opens it in its project. | UC32 |
| FRT-03 | Projects with nothing waiting are listed under `Nothing waiting` with their stale and covered counts and `Open project`. | UC32 |
| FRT-04 | Beside the list, `Projects` lists every open project with its covered count, and `Archived` with its count; each opens its project or the archive. | UC32 |
| FRT-05 | The page has `Settings` and `New project`; the total equals the status bar chip and the dock. | UC32 |
| FRT-06 | Every project view reaches `Needs you` in one action, and Back from a project home opened there returns to it. | UC32 |
| FRT-07 | The page updates without a reload when an item stops or starts needing you, and renders 20 projects with 500 rungs each within 1 second. | |

## FST First install

| ID | Use case | UC |
| --- | --- | --- |
| FST-01 | With no projects, Rung opens on the start screen: `Try the sample project`, `New project` and the cross. | UC33 |
| FST-02 | The start screen's cross leaves Rung for the view you came from (the chat home when there is none) and creates nothing; the start screen shows again on the next open until a project exists. Supersedes UC13.5 and ONB-03. | UC33 |
| FST-03 | From a fresh store you reach a first green test on your own project using visible controls only: New project, a need, a requirement, a specification, a command test, run. | UC33 |
| FST-04 | Every view and section that can be empty names what is missing and offers the one action that fills it. | UC33 |
| FST-05 | Every control the first-install walk uses is named the same on every view that shows it. | UC33 |

## BOT Bot help

| ID | Use case | UC |
| --- | --- | --- |
| BOT-01 | `Paste text` on the project home and on `Needs you` takes pasted text; `Place` names the rung kind, the parent and one line why. | UC34 |
| BOT-02 | The engine checks the place: the parent exists, is not retired, and the kind fits under it; an invalid answer is not offered and you choose instead. | UC34 |
| BOT-03 | `Open as new <kind>` opens that kind's New form under the parent, prefilled and unsaved; you can change the kind and the parent first. | UC34 |
| BOT-04 | Every New form (need, requirement, specification, test) has `Draft`, which fills empty fields from the parent chain and names the profile that drafted. | UC35 |
| BOT-05 | `Draft` never replaces typed text without asking Replace or Keep; drafting can be cancelled; nothing is saved until you save. | UC35 |
| BOT-06 | `Suggest` on a need sends the need and its requirements to the best placed profile and returns exactly three possibly missing requirements, naming the profile and why it was chosen. | UC36 |
| BOT-07 | Suggest's profile follows the allocation rules: disabled, at capacity and author of a requirement of the need exclude a profile; the eligible rank as Develop ranks; a running Suggest counts toward `At once`. | UC36 |
| BOT-08 | With no eligible profile, Suggest says so and lists each profile with its reason; nothing runs. | UC36 |
| BOT-09 | Suggest can be cancelled while it runs; it is recorded as cancelled and proposes nothing. | UC36 |
| BOT-10 | Each suggested item has Accept, which adds a draft requirement approved as any other, and Dismiss; nothing lands without Accept. | UC36 |
| BOT-11 | A Suggest result older than the need's current requirements is marked `Changed since`; its items can still be accepted. | |
| BOT-12 | No bot action is read by `rung check`, the done hook or allocation, and none makes the done gate call a model. | |
| BOT-13 | A bot failure (the profile errors or times out) shows its reason on the form or dialog, keeps what you typed, and offers Retry. | |
