# Exploratory charters

One or more charters per row of the feature map (`docs/features/README.md`), named by the feature.
Format: **Explore** a target **with** resources **to discover** information. Time box 30 to 45 minutes each.
Start from a fresh store (`scripts/e2e-up.sh`, or your own install after moving the store aside) unless the
charter says otherwise. Record findings as described in `TESTING.md`.

## Onboarding

- **Start screen**: explore the first run with an empty store, keyboard only, to discover whether every way
  out (sample, new project, dismiss, Escape, reload) lands somewhere useful and creates nothing unasked.
- **Sample project**: explore Try the sample project, then `hermes rung demo reset` after editing the
  sample, to discover whether the reset restores it exactly and leaves every other project alone.
- **First green checklist**: explore ticking each item in different orders (approve out of order, retire the
  sample need, run a failing test first) to discover any item that ticks or unticks against the stored state.

## Projects

- **Create project**: explore folders that are odd (spaces, unicode, symlinks, no tests, a file instead of a
  folder, no read access) to discover unclear field errors or wrong defaults.
- **Project picker**: explore twenty projects with mixed activity to discover numbers that disagree with
  each project's home.
- **Project settings**: explore renaming, moving the folder and changing profiles while a run is going, to
  discover lost edits or runs bound to the old values.
- **Archive and restore a project**: explore every view of an archived project, the CLI and the agent tools,
  to discover any write that gets through a read-only project.
- **Delete a project**: explore deleting the open project, the only project and a project with a running
  run, to discover dead ends and anything removed from the project folder.

## Building the ladder

- **Need and requirements**: explore editing a need while requirements are being drafted, to discover
  stale states that are missed or doubled.
- **Specifications**: explore switching between AI derives and I write repeatedly on one requirement, to
  discover lost text or orphan specifications.
- **Draft errors**: explore a drafting profile that times out, returns nothing or returns markup, to
  discover dead ends or text rendered as markup.
- **Tests step**: explore Manual, command and AI-judged tests with long commands and many steps, to
  discover a gate released by a test that should not release it.
- **Revert a change**: explore reverting the same change twice and reverting an old change after newer
  ones, to discover stale states that are wrong after the revert.

- **Quick task**: explore a task with five checks, a check edited after approval, a requirement changed in
  another window while the card is open and an archived project, to discover a card that approves text it did
  not show or that stays Verified after its check changed.

- **Need completeness**: explore a need with a draft requirement, a requirement taken out of scope and put back,
  a specification whose code drifted and a need with no requirements, to discover a need called complete while
  something it asks for is unverified, or a requirement that disappears instead of being listed.

## Running work

- **Agent allocation**: explore profiles with equal scores, all disabled and missing tags, to discover a
  suggestion that contradicts Settings.
- **Agent settings**: explore Save and Cancel with many edits across profiles, to discover partial saves.
- **Develop runs**: explore Stop at each moment of a run (queued, mid attempt, while tests run), to
  discover runs left Running or attempts with no outcome.
- **Attempt outcomes**: explore each stub outcome (needs input, no change, unknown, partial) in sequence
  on one specification, to discover outcomes shown as pass or fail.
- **Test executions**: explore very long output, output with ANSI codes and a test that never ends, to
  discover truncation without a label or a view that freezes.
- **Execution errors**: explore a missing command, a missing folder and a folder outside the project, to
  discover an Error that reads like a failed test or a view with no way back.
- **Defects**: explore raising a defect with and without linked runs and closing the dialog every way, to
  discover a defect stored without Raise.
- **Manual tests**: explore recording Pass and Fail repeatedly from two windows, to discover a pass that
  counts before a human approves it.
- **Seen failing**: explore tests that pass first time, fail then pass, and are edited after passing, to
  discover a marker that disagrees with the execution history.

## Reading the state

- **Staleness and Needs you**: explore edits high in the ladder with many rungs below, to discover a
  Needs you count that differs between the chip, the tile and the list.
- **Read-out and export**: explore a need with unproven, stale and retired requirements, to discover a
  number in the read-out or the export that differs from the ladder.
- **Retire and restore a need**: explore retiring a need with a running run and restoring it later, to
  discover rungs that stay in counts or come back with the wrong status.

- **Current evidence (code basis, protected test files, required manual checks)**: explore editing code, test
  files, `.gitignore` and runner configuration after a pass, to discover a specification that stays Verified on
  work it never checked.
- **Verification section, next action, Next on Home**: explore every blocker a specification can have, to
  discover a next action that does not resolve it or a Next list that disagrees with the specification.
- **Integration milestones (engine, REST, CLI, export)**: explore editing scope and checks of an approved
  milestone and changing code between its runs, to discover a milestone that stays Verified on another version
  or other code.
- **Milestones in the pane (Home, list, form, milestone view)**: explore creating, approving and running a
  milestone, leaving its form half typed and opening a missing id, to discover a state the pane names
  differently from the CLI or a way out that loses text.

## Outside the pane

- **Goal gate**: explore `hermes rung check` inside a `/goal` loop while the ladder changes under it, to
  discover a gate that passes on a stale or unproven specification.
- **Command line**: explore every `hermes rung` subcommand with a wrong project, wrong ids and `--json`, to
  discover output that disagrees with the pane or an unclear error.
- **Agent tools**: explore an agent session that proposes, runs tests and checks, to discover any tool that
  approves, creates or edits what only a person may.
- **Verify and recheck**: explore `hermes rung verify` and `recheck` after code changes, with a running test
  and with no project, to discover output that disagrees with the pane.
- **Enforcement health per chat**: explore `hermes rung enforcement` with no session, a session without a
  claim, a moved store and a garbage store, to discover a case reported as enforced when nothing is watched.
- **Doctor and demo reset**: explore a store with a moved project folder, a read-only store folder and a
  newer schema, to discover a check that passes when it should fail or a fix that does not work.
- **Install**: explore `INSTALL.md` on a clean Hermes home and then uninstalling, to discover missing steps
  or data removed without being asked.

## Quality across views

- **Keyboard and screen reader**: explore a whole build flow with VoiceOver and the keyboard only, to
  discover controls without names, lost focus or a trap.
- **Status colours**: explore every Hermes theme in light and dark, to discover a status that becomes hard
  to tell apart or to read.
- **Resilience**: explore quitting the Desktop and killing the backend at random moments during runs and
  edits, to discover lost data or a run that stays Running.
- **Worst-case data**: explore very long text, right-to-left text, emoji, empty projects and 1,000-row
  ladders in every view, to discover layout breaks or slow views.
