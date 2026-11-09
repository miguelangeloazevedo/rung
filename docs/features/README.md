# Feature map

One row per user-facing feature: where it lives, the test that pins it, and whether that test exists.
Charters for exploratory testing are in `docs/charters.md`, one or more per row, named by the feature.

| Feature | View | Test file | Status |
| --- | --- | --- | --- |
| Start screen | start | tests/e2e/test_uc13_first_run.py | tested |
| Sample project | start, home | tests/e2e/test_uc13_first_run.py | tested |
| First green checklist | home, settings | tests/e2e/test_uc13_first_run.py | tested |
| Create project | project-new | tests/e2e/test_uc01_create_project.py | tested |
| Project picker | projects | tests/e2e/test_uc02_pick_project.py | tested |
| Project settings | project-settings | tests/test_lifecycle.py | tested |
| Archive and restore a project | project-settings, projects | tests/e2e/test_uc18_archive_delete.py | tested |
| Delete a project | project-settings | tests/e2e/test_uc18_archive_delete.py | tested |
| Need and requirements | need-new, build, rung | tests/e2e/test_uc03_need_requirements.py | tested |
| Specifications | build, spec-edit | tests/e2e/test_uc04_specifications.py | tested |
| Draft errors | build | tests/e2e/test_uc14_error_states.py | tested |
| Tests step | build, test-edit | tests/e2e/test_uc05_tests.py | tested |
| Agent allocation | build, rail | tests/e2e/test_uc06_pick_agent.py | tested |
| Agent settings | settings | tests/e2e/test_uc07_configure_agents.py | tested |
| Develop runs | build, run, attempt | tests/e2e/test_uc08_develop.py | tested |
| Attempt outcomes | run, attempt, home | tests/e2e/test_uc15_attempt_outcomes.py | tested |
| Test executions | exec | tests/e2e/test_uc09_failed_run.py | tested |
| Execution errors | exec | tests/e2e/test_uc14_error_states.py | tested |
| Defects | defect dialog | tests/e2e/test_uc09_failed_run.py | tested |
| Manual tests | rung | tests/e2e/test_uc10_manual_test.py | tested |
| Seen failing | rung, readout | tests/e2e/test_uc16_seen_failing.py | tested |
| Staleness and Needs you | home, change, rung | tests/e2e/test_uc11_staleness_needs_you.py | tested |
| Revert a change | change | tests/test_use_case_ids.py | tested |
| Read-out and export | readout | tests/e2e/test_uc17_readout.py | tested |
| Retire and restore a need | rung, retired | tests/e2e/test_uc19_retire_restore.py | tested |
| Goal gate | hermes rung check | tests/e2e/test_uc12_goal_gate.py | tested |
| Current evidence (code basis, protected test files, required manual checks) | rung, home, exec | tests/test_evidence.py | tested |
| Verification section, next action, Next on Home | rung, home | tests/e2e/smoke/test_verification_pane.py | tested |
| Verify and recheck | hermes rung verify, recheck | tests/test_evidence.py | tested |
| Integration milestones (engine, REST, CLI, export) | hermes rung milestone | tests/test_milestones.py | tested |
| Milestones in the pane (Home, list, form, milestone view) | home, milestones, milestone, milestone-new | tests/e2e/smoke/test_milestone_pane.py | tested |
| Enforcement health per chat | hermes rung enforcement | tests/test_evidence.py | tested |
| Command line | hermes rung | tests/test_use_case_ids.py | tested |
| Agent tools | rung_status, rung_check, rung_run_tests, rung_propose | tests/test_use_case_ids.py | tested |
| Keyboard and screen reader | every view | tests/e2e/test_uc20_accessibility.py | tested |
| Status colours | every view | tests/e2e/smoke/test_smoke_pane.py | tested |
| Resilience | every view | tests/e2e/test_uc21_resilience.py | tested |
| Worst-case data | every view | tests/e2e/smoke/test_readiness_smoke.py | tested |
| Doctor and demo reset | hermes rung doctor, hermes rung demo reset | tests/test_lifecycle_api_cli.py | tested |
| Install | INSTALL.md | tests/e2e/test_uc22_ready_for_testers.py | tested |
| Quick task | Quick task on a project home, the task card | tests/test_quick.py, tests/e2e/test_uc37_quick_task.py, tests/e2e/smoke/test_quick_pane.py | tested |
| Need completeness | A need's Completeness section, Home's Needs list, `rung verify N-1` | tests/test_completeness.py, tests/e2e/test_uc38_need_completeness.py | tested |
| This chat | The dock's first section: the focused chat's task, Bind to task | tests/test_binding.py, tests/e2e/test_uc39_dock_task.py | tested |

## How to reach each view

`window.__rungNavigate(view, params)` in the pane opens any view directly (the e2e tests use it). A person reaches them by the sidebar entry **Rung**, then:

- **home**: the project name's view; the status chip in the window's status bar returns here.
- **projects**: the project name in the header.
- **project-settings**: `Project settings` in Rung settings.
- **build**: `New need`, or a need's build step from the rail.
- **rung**: any id in the right-hand rail.
- **exec**, **run**, **attempt**: from a test's execution list, a running row, an attempt's `Details`.
- **readout**: `Read-out` on a need.
- **retired**: the `Retired` link under the rail.
- **settings**: `Allocation:` in the rail.
- **quick-new**, **quick**: `Quick task` in a project home's header.
