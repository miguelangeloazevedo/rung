# UX review

Procedure: a screen review (task, hierarchy, effort, copy, states, consistency,
accessibility, psychology, metric) for every new view, from 1440x900 captures of the real pane
(made through the same engine seams as the demo).
Guardrails: no urgency, loss framing, anchoring or fake progress; every number
true; a default is an editable pre-fill, never a pre-selected commit. Standing rule: labels and data only.

Views that already existed are held to the approved prototype and are not re-reviewed here.

## Per view

- **start**. Task: Get to a first project. Read first: `Rung` card. Primary action: `Try the sample project`. Copy: 3 labels, no prose. States: dismiss and Escape create nothing.
- **home with First green**. Task: See what is left to a first green test. Read first: the tiles, then `First green 4 of 5`. Primary action: none (the checklist is a status). Copy: item labels only. States: ticks follow stored state, dismissable.
- **read-out**. Task: Show what a need delivers and with what proof. Read first: Intent. Primary action: `Export`. Copy: section labels and data. States: unproven rows name the reason.
- **test with Seen failing**. Task: Trust that a test can fail. Read first: `Seen failing` badge next to the result. Primary action: `Run tests`. Copy: labels only. States: Not seen failing on a test that only passed.
- **retire dialog**. Task: Retire a need with a reason. Read first: `Retire N-1`. Primary action: `Retire` (destructive). Copy: field label `Reason`. States: Retire waits for a reason.
- **project settings**. Task: Change a project. Read first: the project header. Primary action: `Save`. Copy: field labels. States: Archive secondary, Delete destructive.
- **delete dialog**. Task: Delete Rung's data for a project. Read first: `Delete csvtidy`. Primary action: `Delete` (destructive). Copy: field label `Project name`. States: Delete waits for the exact name.
- **retired needs**. Task: Find and restore a retired need. Read first: the list. Primary action: row opens the need. Copy: reason and date per row. States: `No retired needs` when empty.
- **projects, archived**. Task: Find an archived project. Read first: `Archived 1`. Primary action: `Restore` per row. Copy: labels only. States: Active and Archived counts.
- **home, archived**. Task: Read an archived project. Read first: `Read only` and the archived bar. Primary action: `Restore`. Copy: labels only. States: no write control is shown.
- **execution Error**. Task: Recover from a command that never started. Read first: `Error` badge. Primary action: `Run again`. Copy: output log carries the reason. States: Error is neither pass nor fail.
- **run Needs input**. Task: Answer what the worker asked. Read first: `Needs input` and the reason. Primary action: `Run again`. Copy: the worker's own question. States: the run stops, nothing claimed.
- **home, Needs input item**. Task: Act on a stopped run. Read first: the Needs you item. Primary action: `Run again`. Copy: the question. States: count equal in chip, tile and list.
- **build, Draft failed**. Task: Get a specification written. Read first: `Draft failed` and its reason. Primary action: `Retry` and `I write`. Copy: the reason only. States: the step's gate counts it missing.

## Findings

| # | View | Finding | Status | Reason |
| --- | --- | --- | --- | --- |
| U1 | read-out | `Export` sat under the last section, below the fold on a need with many requirements (rule 4) | fixed | `Export` and `Back` moved to the header row next to the status badge (`desktop/src/60-lifecycle.js`) |
| U2 | delete dialog | The confirm field gave no cue to what must be typed | fixed | The field shows the project name as its placeholder; data, not a hint sentence |
| U3 | execution Error | `Exit code` showed `error`, repeating the badge where no exit code exists | fixed | Shows `none` in the neutral tone; the reason stays in the output log |
| U4 | retired needs | Opened with a bare heading, unlike its sibling views | fixed | The shared project header with Back, then the section label |
| U5 | project settings | Same as U4 | fixed | The shared project header |
| U6 | every truncated value | Reasons, commands, rail lines and history changes were cut with no way to read them | fixed | Each truncated value carries its full text as a tooltip |
| U7 | run Needs input | No way to answer the question in place | declined | UC15 defines `Run again` as the way forward; the answer belongs in the specification, which the person edits from the rail. Adding a reply field would add a second write path for specification text |
| U8 | start | No explanation of what a sample project is | declined | Labels and data only. The button names the outcome; the sample is removed like any project (Project settings, Delete) and `hermes rung demo reset` restores it |
| U9 | home with First green | The checklist could read as progress pressure | declined | It counts real stored steps only (no endowed or fake progress), has no urgency and is dismissable; the guardrail is met |
| U10 | build, Draft failed | `Approve drafted` is shown while a draft failed | declined | UC14 step 1: the gate counts the failed draft as missing and nothing else on the step is blocked; the button approves the drafts that exist |
| U11 | Error, Draft failed | Amber, not red | declined | Neither is a failing test; amber marks "a person acts next", red is kept for a test that ran and failed. Each has its text label |

## Metric to watch

Time from first open to the first green test on the sample (the First green checklist's last tick), and the
share of develop runs that end Needs input and are followed by `Run again` within the same session.
