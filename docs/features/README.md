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
| Sample break and repair | The start screen preview; the sample home's Break the sample and Repair the sample | tests/test_sample_break.py, tests/e2e/test_uc40_first_page.py | tested |
| Needs you decisions | Each Needs you card's outcome, why, what and recommended action; Answer the worker; the empty state's open work | tests/test_needs_you_decisions.py, tests/e2e/test_uc41_needs_you.py | tested |
| Result first read-out | The read-out's Result section, Try the result in project settings, labelled evidence and the export's obligations | tests/test_result_first.py, tests/e2e/test_uc42_results.py | tested |
| Allocation labels | Each score part's description on focus and hover, why the top profile fits, excluded profiles with reasons, Different profile from the author help | tests/test_allocation_labels.py, tests/e2e/test_uc43_allocation_labels.py | tested |
| View hierarchy | One h1 and at most one primary action per view at 1280 by 800, in the dock and at 200 percent zoom; truncated text in full on focus | tests/e2e/test_uc44_hierarchy.py | tested |
| Architecture | The Architecture view: components and contracts, each a draft a person approves, history kept; a contract's affected work; the components a specification or milestone touches | tests/test_system.py, tests/e2e/test_uc45_architecture.py | tested |
| Dependencies | A specification's System section: Requires, Required by, Waits for; a start refused with the blocked path | tests/test_system.py, tests/e2e/test_uc46_dependencies.py | tested |
| Isolated runs | Project settings' Runs; a run's Workspace with its changed files, conflicts and Integrate | tests/test_isolation.py, tests/e2e/test_uc47_isolated_runs.py | tested |
| Plan | The Plan view: each specification Ready, Blocked by, Running, Waiting for capacity, Needs you (only a manual test left) or Verified, in dependency order; Start ready work; the attempt budget; opened from the Develop step, Home's Milestones section or the milestones list | tests/test_system.py, tests/e2e/test_uc48_plan.py, tests/e2e/smoke/test_develop_plan_link.py | tested |
| Contract checks | A contract's checks: a proposed command a person approves, run against the real producer and consumer files; Satisfied, Failed, Out of date (older contract version or changed code), Not run | tests/test_system.py, tests/e2e/test_uc49_contract_checks.py | tested |
| Journeys | A milestone's journeys, in scope with a check or out of scope with a reason; an in-scope journey with no check blocks | tests/test_milestone_system.py, tests/e2e/test_uc50_journeys.py | tested |
| Regression baseline | Earlier milestones and a command a milestone must not break; their checks run on the same code | tests/test_milestone_system.py, tests/e2e/test_uc51_regression.py | tested |
| Quality obligations | A check with a measure, threshold, unit, workload and environment, or a required human review; the measured value against its threshold | tests/test_milestone_system.py, tests/e2e/test_uc52_quality.py | tested |
| Environment | A milestone's probes and migration, run before its checks, with what each printed | tests/test_milestone_system.py, tests/e2e/test_uc53_environment.py | tested |
| Change impact | Judged on: the components' paths a milestone or specification names; Check everything | tests/test_milestone_system.py, tests/e2e/test_uc54_change_impact.py | tested |
| System report | Every milestone with its journeys, obligations, dependencies, environment, exclusions and manual decisions; Accepted only when all are verified now | tests/test_milestone_system.py, tests/e2e/test_uc55_system_report.py | tested |
| Plan budgets and recovery | The plan's attempt and minute budget with its stop reason; an interrupted run reads Interrupted, never passed | tests/test_system.py, tests/e2e/test_uc56_budgets.py | tested |

## How to reach each view

`window.__rungNavigate(view, params)` in the pane opens any view directly (the e2e tests use it). A person reaches them by the sidebar entry **Rung**, then:

- **home**: the project name's view; the status chip in the window's status bar returns here.
- **projects**: the project name in the header.
- **project-settings**: `Project settings` in Rung settings.
- **build**: `New need`, or a need's build step from the rail.
- **rung**: any id in the right-hand rail.
- **exec**, **run**, **attempt**: from a test's execution list, a running row, an attempt's `Details`.
- **readout**: `Results and evidence` on a need.
- **retired**: the `Retired` link under the rail.
- **settings**: `Allocation:` in the rail.
- **quick-new**, **quick**: `Quick task` in a project home's header.
