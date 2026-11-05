---
name: rung-ladder
description: "Use when work in a project is tracked by Rung: read the ladder, propose rungs, let tests decide done."
---

# Working with a Rung ladder

Rung keeps a design-control ladder per project: Need, Requirement, Specification, Test, Test execution.
A specification is done only when Rung says it is released: approved, nothing upstream stale, and every
gating test (command or manual) has a counting pass since the last upstream change.

- Read first: `rung_status` shows the ladder, coverage and what needs a human.
- Never claim a specification is done. Call `rung_run_tests` (the engine runs the commands) and then
  `rung_check`. Its answer is the done condition.
- When you see a missing requirement, specification or test, call `rung_propose` with the parent id.
  A human accepts or dismisses it; you cannot approve anything.
- In a goal loop, add the gate: `/goal gate add hermes rung check S-2.1` (or `--all`).
