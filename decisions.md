# Rung: decision log

Hermes plugin. Entry for the Hermes Agent Plugin Hackathon (due 11 Nov 2026, 17:00 EST / 23:00 Brussels).
Owner: Miguel Azevedo. Repo (to create): github.com/miguelangeloazevedo/rung. The ladder structure is Miguel's own and will be reused beyond this plugin.

Rule: nothing employer- or customer-related in this repo. Generic examples and synthetic demo data only.

## Round 1 (4 Nov 2026)

| Topic | Decision |
|---|---|
| Name | Rung. No reference to any external project anywhere. |
| Origin | Miguel's own design. Any outside project mentioned in chat was shorthand only. |
| Third-party plugins | None bundled or required. Builds on Miguel's own ideas only. |
| Location | ~/dev/rung, then Miguel's GitHub. |
| Shape | Engine + agent tools + hooks + bundled skills + Desktop surface. Not a skills-only plugin. |
| Relation to Kanban | Replaces it as the work surface. |
| Concept | Interactive design-control surface for Hermes with human and AI portions; the system suggests the best carrier per rung. |
| Ladder | Design-control style. No System vs Detailed Requirement split. Includes Test Executions: repeated runs of one test in different contexts, kept in sequence. |
| Engine vs inference | Structure, links, gates, status, coverage, staleness, allocation scoring and execution history are deterministic engine code. Inference only drafts text and does the work. |
| Definition of done | A rung's tests are the done condition both humans and agents read; it feeds loops/goals so they stop on evidence, not on a judge's opinion. |
| Allocation in v1 | Yes, at least a generic portion. |
| First-5-minutes flow | Write a need, iterate requirements, choose per requirement whether AI derives specifications or helps write them, send to develop. |

## Round 2 (4 Nov 2026)

| Topic | Decision |
|---|---|
| Claim | Hermes cannot falsely declare work done: a test owns "done", and every piece of work traces to the need it serves. |
| Form | Full Desktop page (sidebar entry) as the main surface, a docked pane for the active ladder, a status-bar chip for "needs you". Python backend: SQLite (WAL) engine, plugin_api.py REST, broadcast_plugin_event for live updates with polling fallback. |
| Agent surface | Rung tools (claim, report, record execution, propose rung) plus a pre_tool_call hook; the close tool itself refuses without a current passing execution. /rung slash command, `hermes rung` CLI, bundled skills. |
| Workers | Rung's own supervised runner: `hermes -p <profile> chat -Q -q ... --max-turns N`, env scrubbed, pid/log/timeout tracked, works with the app closed. No dependency on the Kanban dispatcher or private Hermes imports. |
| Loop | Rung owns the loop: dispatch, run the spec's command tests, record the execution, re-dispatch with the failure evidence, stop on pass or budget. Bonus: `/goal gate add "hermes rung check <SPEC>"` for chat goals. |
| Unit of development | The Specification. |
| Q1 Test types | Data model holds command, manual and AI-judged. v1 builds command (engine runs it, only type that gates automatically, explicit success contract, timeout, output cap) and manual (human records result). AI-judged is provisional: may block, never releases a gate; built only if time allows. |
| Q2 Failures | Every execution is immutable and kept in sequence. A failure blocks and offers retry. No automatic defects; a human click raises a Defect linked to one or more executions (not nested under one test). |
| Q3 Allocation | Deterministic. Hard filters (profile enabled, required tools declared, concurrency, not the author when independence is required, human-only rungs excluded), then integer score: capability-tag match, current load, infrastructure reliability from past executions, cost band; stable tie-break; breakdown shown in the pane. Profile tags declared in Rung config. |
| Q4 Code origin | Written fresh, clean room. No employer or client repository opened, copied or ported during the build. |
| Q5 Approval | Human approves needs, requirements, specifications and tests. Agents may review; "reviewed by agent" is stored separately and never labelled approval. Command executions are authoritative from the engine. |
| Platforms | macOS and Linux. |
| Demo arc | Populated ladder with one failing test; launch worker with allocation reason; failed then passing executions stay in history; coverage goes green; edit the requirement, downstream turns stale, old pass stops counting, gate closes with no model call; human approves the revised test. |
| Cut from v1 | Auto defects, agent approval, portfolio dashboards, templates, exports, version diff UI, workflow builder, semantic dedupe, flakiness analytics, external integrations, graph visualisation beyond the ladder, generating a whole ladder from a vague need. |

## Round 3 (4 Nov 2026)

| Topic | Decision |
|---|---|
| Surface direction | "Attention" (mock 3): needs-you queue first, then running, done, draft; header coverage tiles; right rail with mini ladder and allocation. |
| Status colours | Fixed semantic hues in OKLCH: pass 150, fail 27, stale 305, draft neutral. Lightness and chroma fitted per theme background to at least 4.5:1. "Needs you" uses the theme accent when it is chromatic and at least 60 degrees from every status hue, otherwise amber (75). Verified on 15 preset theme modes x 9 accents: 135 combinations, all at 4.5:1 or better, minimum hue gap 48 degrees. Built with the SDK's own OKLCH and contrast helpers. |

## Round 4: projects and the build-from-need workflow (5 Nov 2026)

| Topic | Decision |
| --- | --- |
| Entry | Rung opens the last project's home; the project title opens the picker; `New project` sets name, folder, test command and profiles, then lands on an empty project with `Write the first need`. |
| Build flow | Five-step strip `Need · Requirements · Specifications · Tests · Develop`. Later steps are locked; each step's approve button is the only way forward and stays locked until its gate holds (drafts finished, every test accepted). |
| Spec authoring | Per requirement: `AI derives` or `I write, AI supports`. AI drafts arrive live; the human-written one blocks the gate until written. |
| Tests | Test editor with type Command, Manual or AI judged; Manual swaps command fields for steps. `Run once` returns to the step that opened it. |
| Develop | `Send` starts the loop; it ends on a result view with attempts, each opening what the agent did (files, commands, output, what fed the next attempt). |
| Change and staleness | `View change` shows before and after plus what went stale; stale passes stay visible but struck through. Approve or edit-and-approve clears the item. |
| Failures | Failed runs open their own detail; `Run again` runs live to a new execution; `Raise defect` pre-links the failing runs. |
| Agent proposals | Agent-proposed rungs appear under Needs you as Proposed with `Accept` and `Dismiss`. |
| Needs you | One global count, identical on every view (status bar and tile). |
| Out of v1 | Project archive and delete, need delete, AI-generation and test-launch error states. |
