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

## Round 5: reinforcement before extensive testing (5 Nov 2026)

| Topic | Decision |
| --- | --- |
| Onboarding | Structural only, no tooltips or tour. First run shows a start screen: `Try the sample project`, `New project`, dismiss. The sample project is created only when asked; dismissing creates no sample data. A `First green` checklist in labels ticks from real state, is dismissible and can be shown again from Settings. Empty states carry one primary action. The project form only requires the folder; name, test command and profiles are pre-filled, visible and editable. |
| Back in scope | Error states for AI drafting and test launch (reason, retry, a way forward, never a dead end); project archive, restore and delete (delete removes Rung data only, never the folder); retire and restore a need (kept in history, its rungs leave every active view and count); keyboard and screen-reader support to WCAG 2.2 AA. |
| Evidence honesty | Attempt outcomes beyond pass and fail: Needs input (with a reason, enters Needs you), No change, Unknown (the worker vanished without a result, never read as pass or fail), Partial (a missing capability is filed as proposed rungs instead of being built inside the attempt). Command tests show whether they were seen failing before their first pass. Each need has a read-out: intent, plan, delivered, with every requirement paired to the execution that proves it, exportable as markdown. |
| Not adopted | Binding a pass to the commit it ran on (code drift staleness). |
| New views | Start screen, read-out, error states, archive and retire use the approved Attention design language and existing pane components; no separate mock round. Miguel reviews them during extensive testing. |

## Round 6: what well-loved Hermes plugins do (5 Nov 2026)

Reviewed: the most-starred Hermes-native catalog plugins, the official and labs plugins, and Desktop-pane and workflow plugins.

| Topic | Decision |
| --- | --- |
| Honest states | Already in Round 5: Error, Unknown, Needs input, unavailable data shown as such, never invented. |
| Low-commitment path | Already in Round 5: the sample project, opt-in. |
| Install guide | Copyable steps, each ending in a check that shows it worked, with `hermes rung doctor` last. States what Rung writes and where, and that it sends nothing off the machine. |
| README (after the run) | One outcome line, demo GIF above the fold, two-command install, screenshots, how it works in one diagram, safety and data, limits, changelog. Not in stage 2. |
| Not adopted | Multilingual README, hosted trial, telemetry. |

## Round 7: the done gate as a hook, a docked pane, the full allocation filters (5 Nov 2026)

Closes what Round 2 decided and goals 1 and 2 did not build. Spec: `docs/use-cases-3.md`; definition of done: `docs/acceptance-3.md`, run by `scripts/acceptance-3.sh`.

| Topic | Decision |
| --- | --- |
| Claim | New agent tool `rung_claim`: the calling chat session takes one approved specification. It refuses a specification that is not approved, is human only, is held by another session, or whose profile a hard filter excludes; each refusal names its reason. A session may hold several claims. A claim shows on the specification, under Running and in the dock, with its profile and chat. |
| Report | New agent tool `rung_report`: the session declares a claimed specification done. It refuses while `rung check` fails, naming the blocking rung, and the claim stays open. Once the check passes it closes the claim as reported, with the execution that proves it. A report is never an approval. |
| Release | You release a claim from the pane or with `hermes rung claims release <spec>`; it closes as released. Claims never expire on their own. `hermes rung claims` lists the open ones. |
| Done hook | A `pre_tool_call` hook blocks, while the claimed specification's check fails: `rung_report`; `kanban_complete` from a session that holds an open claim; a `todo_list` item set to completed whose id or content names a claimed specification (an id seen naming it earlier in the session counts too). The block message names the specification and the blocking rung, and the tool does not run. Every other tool, and every call from a session without a claim, passes untouched. No model call: the hook reads the store, read only. If the store cannot be read the hook allows the call; the doctor reports the store. |
| Docked pane | A Rung pane registered in `PANES_AREA`, placement right, collapsible, 237 to 360 px: the open project with its Needs you count, the Needs you items, Running (develop runs and claims, live), the current need's ladder with a need picker, and `Open Rung` to the full page. The current need is the last need opened in the full page, else the first need with an item that needs you, else the first need. Clicking an item opens it in the full page. Same data, status colours and labels as the full page; labels and data only. |
| Tools on profiles | Each profile declares its tools (Hermes toolset names) in Settings as chips. When Rung first lists a profile, the chips are pre-filled read only from that profile's Hermes `platform_toolsets.cli`; they stay editable. A store from stage 2 migrates with no tools declared. |
| Required tools | A specification declares required tools on its view, next to its tags. A profile missing one is excluded: `missing tool <name>`. A specification that requires none excludes nobody on tools. |
| Concurrency | `Max runs` stays the attempt budget of one develop run (UC7 and UC8 are frozen on that meaning). Concurrency is a new per-profile field `At once` (1 to 10, default 2): a profile carrying that many develop runs plus open claims is excluded: `at capacity <n> of <m>`. |
| Independence | A specification can require an independent carrier. Profiles that authored it or any of its tests (agent author, drafting profile or proposer) are then excluded: `author of <id>`. |
| Human only | A specification is human only when you mark it so or when every test under it is manual. No profile is offered; every profile is listed as excluded: `human only`. `Send`, pick and `rung_claim` refuse. |
| Showing exclusions | Develop lists every excluded profile with its reason under the ranking. Settings shows, per profile, the specifications of the open project it is excluded from, each with its reason. The engine, the API, the CLI and the tools refuse an excluded profile with the same reason; nothing bypasses a filter. |
| Pane coverage | Flows tested only below the pane get pane walk-throughs: revert a change, fresh draft, cancel an execution, cancel a run, project form field errors, saving project settings. |

## Round 8: which ladder a profile's chat uses (6 Nov 2026)

Settled during the stage 3 build; Round 7 assumed it without saying it. Each Hermes profile runs its own backend, and Rung's store follows the active home, so a chat as `coder` would otherwise open `coder`'s own empty ladder and could never claim the work of the ladder that lists `coder` as a carrier.

| Topic | Decision |
| --- | --- |
| Carrier ladder | A profile home with no Rung store of its own (no `plugin-data/rung/store` pointer and no `rung.db`) uses its root home's ladder: the root's pointer, else the root's store. Its chats claim, report and check there, and the done hook reads it. A develop run started as `hermes -p <profile>` lands in the ladder that sent it the same way. |
| Own ladder | A profile that has its own store keeps it; `RUNG_STORE` still overrides everything. Nothing is copied or moved between stores. |

## Round 9: the hackathon submission (6 Nov 2026)

Entry rules (Nous announcement, 4 Nov): a PR adding `plugin-catalog/<name>.yaml` to `NousResearch/hermes-agent`, a demo on X under 90 s tagging @NousResearch that shows the plugin working, then the form (plugin title, description, email, Discord username, X post link, PR link). The form can go in as soon as the PR is open. Judged on usefulness, reliability, polish and creativity. Due 11 Nov, 17:00 EST (23:00 Brussels).

| Topic | Decision |
| --- | --- |
| Hermes version | Rung was built and tested on Hermes v0.22.5. v0.23.0 (5 Nov) is what judges and catalog CI run. Test and fix on v0.23.0 in an isolated checkout and Desktop build next to Miguel's own install, rerun all acceptance and readiness there, then declare `requires_hermes: ">=0.23.0"` in plugin.yaml and in the catalog entry. Amended 6 Nov after the pass: declared `">=0.22.5"`, the oldest release Rung passes on, because acceptance, readiness and clean install pass on both v0.22.5 and v0.23.0, and `">=0.23.0"` would stop Rung loading on Miguel's own v0.22.5 install. |
| Demo video | Who makes it and how: decided when we get there, probably Tue 10 Nov. |
| Demo story | The done gate first: an agent claims a specification, tries to mark it done, the hook blocks it naming the failing test, the agent fixes the code, the test passes, the report goes through, and the dock updates live. Then about 20 s from need to release. |
| Public repo | This repo stays private and unchanged, renamed `rung-dev`. The public repo `github.com/miguelangeloazevedo/rung` is generated from it by a repeatable scrub script (git filter-repo). The script is deterministic, so a re-run for a release only appends new commits and a catalog pin stays valid. |
| Catalog PR | Opens as soon as the public repo, the README and the v0.23.0 pass exist (aim Sun 8 Nov). The open PR's pin moves if fixes land later. The form can go in once the PR is open. |
| Listing | The catalog has no regulatory, SDLC or development-practice category (the vocabulary is desktop, memory, platform, web, tools, voice, automation, models, general), so: category `desktop`, title Rung, a 2:1 banner and up to 6 screenshots from the real Desktop with synthetic demo data, README rendered on the listing page. |

Open: who makes the demo video and how (Tue 10 Nov); narration.

## Round 10: navigation contract, first review round (7 Nov 2026)


| Topic | Decision |
| --- | --- |
| Unsaved text | Every form and editor reports unsaved text. Any view change it did not ask for (rail, crumbs, header, dock, status chip, Back, Escape) first asks Discard or Keep editing. An explicit Cancel discards without asking; the move after a save never asks. |
| Way out | Every task view (need, requirement, specification and test editors, new project, settings, project settings) has a visible way out, and Escape takes it. The requirement editor gains Cancel. Build steps 2 to 5 have Back to the previous step, first in the footer. |
| Back | Back returns to the view the person came from, else to the view's parent. Labels that name a place (Back to test, Back to run, Back to build) keep going there. |
| Overlays | A dialog belongs to the view that opened it: any view change closes it, and closing the Raise defect route returns to Home without a history entry. |
| Bad destinations | A missing rung, execution, run, attempt, change or project, a failed load and an unknown view all show one page: what is missing, then Back, Home and Projects. No view waits on Loading after its data failed. |
| Where am I | In-project views carry an h1 with the page's own name after the project name. The project name is a button to the project list. Crumbs are a breadcrumb nav with the current item marked; the strip marks the current step; the rail marks the open rung. After a view change focus moves to the new view's first field, else its title. |
| Settings | Settings is a named button in the header of every in-project view. |
| Not changed | Start screen cross (frozen UC13.5); Archive and Revert stay one click because both are undone in place (Restore, revert again) and frozen UC18 and UC27 click them directly; row verbs (Edit, Open) keep their names because frozen tests find them by exact name and the row gives the item; empty-state actions, the project home and reopening on the last view wait for the projects-view choice; browser Back and links into a view need host routing a plugin cannot set. |

## Round 11: navigation contract, second review round (7 Nov 2026)

| Topic | Decision |
| --- | --- |
| Where Back goes | Back, Cancel and Escape return to the view the person came from, else the view's parent; leaving adds no history entry. A form or editor is never a place to return to: it is not recorded when left. History entries carry their project, so Back never crosses into another project. |
| Settings | Settings is reached from the header of any view, so its Cancel, Save and Escape go to Home (frozen UC07), not back through history. |
| Named Back | `Back to X` always goes to X; when X is where the person came from, that entry is used up. Build steps name their Back: Back to Need, Back to Requirements, Back to Specifications, Back to Tests. After a save or a create the destination replaces the finished form. |
| Escape everywhere | Every view with a visible Back or Cancel takes the same action on Escape (run, attempt, execution, read-out, retired needs, the manual test form, the inline need edit, the missing page). |
| Dialogs | Escape, the cross and a click outside ask Discard or Keep editing when the dialog holds typed text (Raise defect title, Retire reason); its own Cancel closes without asking. A click outside counts only when it starts and ends outside. The rest of Rung is inert while a dialog is open. |
| Missing destinations | Home, Settings, Retired needs, a project's archive list, the rail and the Raise defect dialog show their failed load instead of Loading or an empty list. On the missing page the sentence is the h1 and takes focus. |
| Fields | A field error has the id `fe-<field>` that its field points to; the field is marked invalid, and after a refused save focus moves to the first invalid field. |
| Result line | Create project, Save settings, Save project settings, Save or add a test and Raise defect show what they did on the view they land on, until the next view change. |
| First run | Before the first project, the start screen stays reachable: New project always has Back to it, and Escape takes it, after the start screen was dismissed too. |
| Names and places | The Settings page is titled Settings and its project name is the button to Projects; Retired needs and Project settings carry their name as the header h1. Breadcrumbs are an ordered list of buttons with the current item marked. Every control is at least 24 by 24 pixels. Build step 1 shows the step strip. |
| Declined | Stop instead of Cancel for a running execution or run: frozen UC28 names it Cancel. Row actions carrying their item in the accessible name: frozen tests find Open, Approve and Accept by exact name, and the row names the item. A view showing both breadcrumbs and Back to X: frozen UC9 and UC10 use Back to test. The strip opens steps already reached: a step past an unapproved gate is locked and the engine refuses the move. The status chip and the dock move the app even when unsaved text holds the change, so the question is seen. Window title and skip link: the host owns them. |

## Round 12: front page (7 Nov 2026)

| Topic | Decision |
| --- | --- |
| Front page | Direction C of the three mocks: a cross-project Needs you view, items grouped by project, with the project list beside it. Opening a project leads to its Home (ladder) as today. |
| No projects | With no project yet, the front page is the start screen as it is now (Try the sample project, New project); direction C appears once a project exists. |
| Start screen cross | Supersedes UC13.5 (in acceptance-4): the cross only closes. It leaves Rung for the Hermes view the person came from (the chat home when there is none) and creates nothing; opening Rung again shows the start screen until a project exists. |
