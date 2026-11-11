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
| Not adopted | Binding a pass to the commit it ran on (code drift staleness). Reversed in Round 22: a pass now applies to the content of the project's files it ran on, not to a commit. |
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

## Round 13: bot help and first install (approved with acceptance 4, 7 Nov 2026)

| Topic | Decision |
| --- | --- |
| One seam | Every bot action asks a Hermes profile through the drafting seam (stub in tests) and only proposes: nothing is stored as approved, nothing is saved without a person's Save or Accept, and none of it is read by `rung check`, the done hook or allocation. |
| Paste text | `Paste text` on the project home and the Needs you page opens a dialog: you paste text, `Place` asks the drafting profile which rung it is (Need, Requirement, Specification or Test) and where it goes (the parent), with one line why. The engine checks the answer (the parent exists, is not retired, and the kind fits under it) and offers only valid places. `Open as new <kind>` opens that kind's New form under the parent, prefilled and unsaved; you can change the kind and the parent before opening. |
| Draft | Every New form (need, requirement, specification, test) has `Draft`: it fills the empty fields from the parent chain and names the profile that drafted. Fields you typed are never replaced without asking Replace or Keep. Drafting can be cancelled; the form stays unsaved and the leave question applies as to typed text. |
| Suggest | `Suggest` on a need (its page and the Requirements step) sends the need and its requirements to the best placed profile and returns exactly three possibly missing requirements. The profile is chosen by the Round 7 allocation rules applied to the need: disabled, at capacity (a running Suggest counts toward `At once`) and author of any requirement of the need exclude a profile; the eligible ones rank as Develop ranks. The result names the profile and why it was chosen (its rank and the excluded profiles with reasons). Each item has Accept (adds a draft requirement, approved as any other) and Dismiss. Suggest can be cancelled while it runs. With no eligible profile it says so and lists each profile with its reason; nothing runs. A result older than the need's current requirements is marked `Changed since`; its items can still be accepted. |
| Empty states | Every view and section that can be empty names what is missing and offers the one action that fills it, never an explanation. |
| First install | From a fresh install, a person reaches a first green test on their own project with visible controls only: start screen, New project, a need, a requirement, a specification, a test, run. The route walk checks every view and state has a visible way out. |
| UC13.5 and ONB-03 | Superseded by acceptance 4 (Round 12): with no projects the start screen's cross leaves Rung for the view the person came from and creates nothing; the start screen shows again on the next open until a project exists. `test_uc13` asserts the new behaviour, named in acceptance 4. |

## Round 14: third navigation review, corrections and declines (7 Nov 2026)

Three independent reviewers (40 findings) on the scrubbed public code, the gallery and the front page mock. Each correction applies to the pattern, not the example.

| Topic | Decision |
| --- | --- |
| A visible way out is the Escape action | One `ExitBtn` renders any Back, `Back to X` or Cancel and registers the same action for Escape: every build step, the locked step, the page Back in the header. |
| Read views have a Back | Need, specification, command test and change pages show Back in the header (to where you came from, else the parent); Escape takes it. The need's inline edit closes on Escape, asking first when text is typed. |
| Back asks, Cancel discards | Only a control named Cancel, and the move after a save, skip the Discard or Keep editing question. Back on project settings and on New project (no project yet) now asks. The Delete dialog counts the typed confirmation as typed text. |
| Live work | A live run shows `Back to build` and a running execution `Back to test`, which leave the work running; `Cancel` stays the stop control (frozen UC28 names it). Escape matches the way out. |
| Need is one page | `Back to Need` and the strip's Need step open the need page. |
| Result lines | `notify` lands after the move, whatever the order; `finish(view, params, notice)` carries it. Added for add, approve and save of requirements and specifications, approve all, record, revert, retire, restore, archive and delete. The line is a `role=status` element that is always in the page. |
| Missing page | One sentence built from the kind and id (`Specification S-99.9 is not in csvtidy`); an unknown view reads `Page not found` without the internal view name. |
| Failed loads | Every view that reads `/settings` or `/state` shows the load error (Missing with the project, or the error line), never Loading or an empty list; the archive list keeps its hooks before any early return. |
| Keyboard | An anchor without an href is treated as a button by `h()` (role, tab stop, Enter and Space). Clickable rows already were. Escape closes the topmost dialog wherever focus is; when the opener is gone, focus goes to the page h1. An open profile menu holds Escape as before (frozen UC06). |
| Headings and labels | The page name is the h1 and the largest heading; the project name before it is a small link with no hidden words in its name. Requirement and Specification fields have visible labels; the need field is named Need. The test editor uses the shared breadcrumbs. |
| Empty filtered lists | A project search that matches nothing offers `Clear search` (Projects and the archive). |
| Carried into acceptance 4 | 320 pixel reflow (NAV-14), focusable rows (NAV-15), live views' way out (NAV-16), failed loads (NAV-17, FRT-08), the front page's units, run link, last opened marker, contrast and `Open <id>` names (FRT-02 to FRT-04), Escape on the start screen and New project's Back (FST-02), `Clear search` (FST-04), field errors on every form (NAV-10), `aria-current` (NAV-09). |
| Declined | Cancel asking before discarding (Round 10: Cancel is the explicit discard). Renaming the run and execution `Cancel` to Stop (frozen UC28). Renaming the locked step's Back (frozen UC03 clicks `Back`). `Open <id>` names on the existing Home and archive rows (frozen UC14 and UC18 find `Open` by exact name; the new front page has them). Focusing the first field on every view change (Round 11 and NAV-08: the h1; new-rung forms already focus their first field). An error summary and an `Error:` window title (forms have at most five fields, each error is tied to its field and focused; the window title belongs to the Desktop). Search across rungs (new scope, not navigation). Raise defect losing text on a view change: the gallery used the forced test hook; visible routes ask. |

## Round 15: acceptance 4 approved and frozen (7 Nov 2026)

| Topic | Decision |
| --- | --- |
| Freeze | Miguel approved `docs/use-cases-4.md` (43 IDs), `docs/acceptance-4.md` (UC30 to UC36) and `scripts/acceptance-4.sh` as committed in `7ead5ed`; their checksums join the frozen set outside the repo. Rounds 13 and 14 stand as written. |

## Round 16: where Rung opens (7 Nov 2026)

| Topic | Decision |
| --- | --- |
| Opening page | Rung keeps reopening the last opened project (frozen PRJ-04, UC2 step 4). `Needs you` across projects replaces the Projects page: the project name in every header opens it, and Rung opens on it only when no project is current. |
| Counts | The page's total is the sum of its project groups; each group equals that project's Home tile. The chip and the dock keep counting the current project (frozen Needs you count rule). |
| Contract | FRT-01, FRT-05 and UC32 step 2 amended with Miguel's approval; acceptance 4 re-frozen. |

## Round 17: final review, corrections and declines (7 Nov 2026)

Three independent reviewers (34 findings, 8 rated major) on the scrubbed public code and a gallery covering Needs you, Paste text, Draft, Suggest, Choose folder, failed loads and a 320 pixel pane. Each correction applies to the pattern, not the example.

| Topic | Decision |
| --- | --- |
| Missing page stands alone | A missing id, a failed load and an unknown view show the header, the sentence (an h1 at page size) and the way on; no tiles, tree or allocation of a page the person did not reach. A missing execution names the test and number (`Execution T-1.1a #7 does not exist`). |
| Back on Needs you | Opened from a view (the project name), the page shows Back to it; Escape takes it. |
| Status and logs | Loading, every bot progress line and the suggestion line are `role=status`; live run output and execution output are `role=log`. |
| One word per job | The New need suggestion line reads `Suggesting`; `Drafting` stays for drafts (frozen SPC-01). A new Draft clears the previous `Drafted by`. The Draft question is titled `Replace typed text?` with Keep and Replace. Leaving a view while its bot job runs cancels it and says so (`Drafting cancelled`). |
| Prefill | Paste text's prefill lasts for the next view only; a form opened later never receives it. The placed line names the project when there are several. |
| Labels | A field's visible label is its accessible name (shared `Field`); Paste text's field is Text. The picker reads `Choose folder`. Dialog titles are h2 under the page h1. Settings names the project link `<project>, Needs you` like the header. |
| Landmarks and state words | The traceability tree and the build strip are labelled nav landmarks. Tree dots carry their status word for screen readers and on hover. The Allocation link is named for its destination. |
| Steps at every width | Build step names stay visible at every width, wrapping instead of hiding. |
| First green | Each checklist step opens the view where it is done (New need, then the need's build steps). |
| Result lines | Create need, approve (need, Needs you, specification, stale rung, manual result), accept, regenerate and fresh draft, pick, run, run once, run tests, Develop and Send all end on a line naming what changed. |
| Cards with buttons | A Needs you card holding Approve and Raise defect is not itself a button: its title is the keyboard's way in, a click on the card still opens it. |
| Declined | The missing page's `Projects` button (frozen NAV-07 names Back, Home and Projects). The chip counting across projects (Round 16: the chip counts the current project). An `Error:` prefix (Round 14). An action on `Nothing needs you` (nothing is missing; New project is in the list beside it). Suggest's exclusions repeating Allocation's (two decisions with their own rules: Suggest excludes the requirements' authors, Allocation ranks for the specification). A `not saved` marker on drafted fields (the form is unsaved until Save, and leaving asks). The running Draft and Suggest gallery shots showed the finished state because the stub was faster than the capture; the gallery now slows it. |

## Round 18: confirmation review, corrections and declines (7 Nov 2026)

Three independent reviewers (21 findings, 3 rated major) on the Round 17 code and a fresh gallery.

| Topic | Decision |
| --- | --- |
| 320 pixel rows | A control, a badge and an id never break inside themselves; in a narrow pane a row pairing text with actions wraps whole. Accept, Dismiss, `Proposed`, ids and status words broke into letters on Home. The route walk now fails on any control taller than two lines, or an id on more than one line, at 320 pixels (every id span carries `whitespace-nowrap`). |
| Headings stay headings | A heading that opens something holds a button that carries the action (`h()` does it for every heading); the need title was a heading with a button role. |
| Failed shared load | The line under the header gains Retry. The view keeps the data it loaded itself (NAV-17: the error shows on the view). |
| Result lines | Every door is named once in `post()`: dismiss, regenerate, authoring, send, pick, run, run tests, allocation, release and cancel join approve, save and record; the per-button notices added in Round 17 are gone (one had a second name for approving an execution). |
| Bot help | The stop control reads `Cancel placing`, `Cancel draft` or `Cancel suggest`, never a second `Cancel`. A failed cancel or a failed poll keeps Cancel and says why. A second click before the job exists starts nothing. `Cancelled` is a status line and takes focus from the control it replaced. The Replace question has Cancel beside Keep and Replace. |
| Step names | A build step's name carries its state (`Specifications, done`, `Tests, locked`). |
| Provenance | `by <profile> · from chat "<chat>"` shows only the parts that exist; no placeholder words. |
| Missing page Back | Back never falls back to the page that failed: a failed Home goes on to Needs you. |
| Declined | Replacing a view by the missing page when only `/state` or `/settings` failed (NAV-17; the view's own data loaded). Why the profile was chosen for Place and Draft (BOT-06 asks it of Suggest; BOT-01 and BOT-04 name the profile). The stub's fixed reason sentence (synthetic stub; a profile writes its own). Renaming `Draft` and `Keep` (frozen BOT-04, BOT-05). `Open <id>` names on existing rows and cards (Round 14). The project link's name (Round 16). A header without Dock, Settings and New need on the missing page (the project exists; one header on every project view). Already fixed in Round 17: the Needs you card holding buttons; focus inside Paste text (its dialog keeps focus). |

## Round 19: second confirmation review, corrections and declines (7 Nov 2026)

Three independent reviewers (22 findings, 2 rated major) on the Round 18 code and a fresh gallery.

| Topic | Decision |
| --- | --- |
| Result lines, one source | Every single action is named by the table in `post()`; no view writes its own line after it (Record added `Recorded a result on`, which replaced `Recorded Pass for`). Create project, project settings, archive, restore, delete, Settings, retire, raise defect and revert joined the table; a row that does not apply lets the search go on (Dismiss on a suggestion was dead). An action made of several posts posts quietly and names itself once (Send all; a new rung saved and approved says `Approved`). A unit test holds the rule. |
| Saved names its object | `Saved Settings`, `Saved the settings of <project>`; no bare `Saved`. |
| Fields are named | A caption directly before a field names it, in the one constructor `h()`: input, textarea, select in its wrapper, radio group, group of checkboxes and the folder field. The route walk fails on any field without a name in any view. |
| Missing and failed pages | Home and Projects on the missing page replace it, so Back never returns to it. A missing execution names test and number. A page that failed to load (not a missing id) also offers Retry. The backend-unavailable screen has `Close Rung` beside Retry. |
| Bot help | Leaving a running job says `Drafting cancelled` only after the cancel returns, else `Could not cancel drafting: <reason>`. No Retry while the job still runs; Cancel is the only control then. |
| Wide tables | Settings' profile table and the Develop table scroll inside their own labelled region; the 320 pixel route walk now covers Settings and Develop. |
| Allocation | The Allocation heading holds the button to Settings (no clickable block around a heading). |
| One name | Needs you's empty state no longer adds `Priority queue`. |
| Declined | `Write the first need` beside `New need` (frozen acceptance.md UC01 step 3). The chip's count is the current project's (frozen FRT-05; the harness reads `Rung: N`). `Suggesting` on New need (it comes from the drafting profile, not a keyword match). `Accept R-4` style names on row actions (frozen UC03 finds `Accept` and `Dismiss` by name within the row; Round 14). Settings' Back lands on Home (frozen UC07). `Keep my text` (frozen BOT-05 names `Keep`). Clearing `Drafted by` on every keystroke (it names the last draft until the next one). The proposal card's click (it already follows the Round 17 rule: not a button, its title is). Count differences between gallery shots (different seeded states). `refused: /state` (the test hook's refusal text, not a product message). |

## Round 20: the test command is optional and explained (8 Nov 2026)

| Topic | Decision |
| --- | --- |
| Optional | A project no longer needs a test command. New project and Project settings mark it `optional`; the engine accepts it empty on create and lets it be cleared later; doctor reports `not set` as a pass. Frozen PRJ-02 names only the folder and duplicate names, so no frozen criterion changes. |
| Still prefilled | Rung keeps filling it in when it recognises the folder (pytest, npm test, cargo test, go test, make test, unittest). |
| Explained on request | A `?` button beside the label (`About the test command`) opens a dialog: what it is, five examples, that Rung puts it in the command tests it drafts and each test keeps its own command, and `Not sure? Leave it empty.` The form itself stays labels and data. |

## Round 21: real drafting and develop profiles in the happy flow (8 Nov 2026)

Recording the happy-flow video with real Hermes profiles (not the stubs) exposed two defects.

| Topic | Decision |
|---|---|
| Child working folder | Hermes's file and terminal tools anchor to `TERMINAL_CWD` before the process cwd, and the gateway's value (often the home folder) was inherited by every drafting and develop child: one file search took 105 s and specifications failed at the 180 s limit. `scrubbed_env(folder)` now sets `TERMINAL_CWD` to the project folder for both. |
| Test drafting | Approve drafted drafted every test inside the request; a profile takes seconds per specification, so the Desktop gave up after 30 s and showed an error while the work went on. Tests are now drafted in the background: the Tests step shows Drafting per specification, Approve tests waits (409 while drafting), a failure shows with Retry, and `/rev` tells the pane when the state changes. `POST .../propose-tests` stays synchronous for API callers unless the body asks for `background`. |
| Drafting prompts | Drafts are read on screen and approved by a person: short sentences, grounded in the project's files, one rung each, and each draft sees its siblings (other requirements, other specifications) so names and formats agree without overlap. |
| Approve, then next step | Each approval posts, then moves to the next step before the flow is fetched again, so the step rendered from the old flow and flashed "The Tests step is locked" (seen in the recording). While a fetch is in flight, a step that reads as locked shows Loading; it reads as locked only once the fresh flow says so. One rule in the build router covers every approve-and-advance move. |
| Test row layout | A long drafted command squeezed the row's controls into one-letter columns. The command wraps; the type tag and Accepted keep their width. A global rule keeping every control's label from breaking mid-word was tried and dropped: it let long text inside clickable rows overflow the pane (worst-case smoke, RES-07). |
| Drafted pass rules | A drafted test whose pass rule has the wrong shape is kept without it (exit code 0) instead of failing approval; drafted commands are what a person would type, short, and keep their data out of the project folder. |
| What the worker is told | The develop prompt listed each command test but not its pass rule, and failure feedback said only "fail (exit 0)": a test that checks the output could not be met except by guessing (a real builder guessed twice, then asked for input, correctly). The prompt now names each test's pass condition, and the feedback says why a test failed. The deterministic judgement is unchanged. |
| Drafted tests check the specification | Probing a web feature (a link shortener's click counts), one specification got only the project's whole test suite as its test: it passed before any work, so it proved nothing. The test prompt now says each command test checks the specification's own behaviour, fails on the code as it is and passes once the specification is met, and never the whole suite alone. |

## Round 22: a green result means verified now (9 Nov 2026)

An outside assessment reproduced seven ways the gate said `ok` while the work was not verified: code changed after a pass; a worker rewrote its own test to `assert True`; a newer Could not run left an older pass in charge; a required manual check never run; a check running or cancelled; seen failing counted across test versions. Each is now a regression test (`tests/test_evidence.py`). The contract is written out in `docs/verification.md`.

| Topic | Decision |
| --- | --- |
| One evaluator | `Engine.verification()` is the only place that decides whether a specification is verified. The gate, `check --all`, the tree, coverage, tiles, Needs you, the read-out, the done hook and the develop run's own finish all read it. It returns a state, typed blockers (stable codes apart from the wording), the required checks satisfied, the basis and one next action. `check` keeps its keys and adds `verification`, `codes`, `basis` and `next_action`. |
| Newest result decides | Per test, the newest result of the current test version decides; a cancelled execution leaves no evidence, so the result before it decides, and that result must still match the code. Running blocks (Checking); Could not run blocks and is shown as Could not verify, never as a behaviour failure. |
| Code basis | Every result records a digest of the project's files (a walk that honours `.gitignore` without starting git, so the read-only done hook computes the same value; generated and runtime files and anything in `.rungignore` left out). A pass counts only while the basis now is the basis it ran on; otherwise it is Out of date, kept in history, and the next action is Run tests. Uncommitted changes count. A file created while a check runs is its output; a file changed under a running check makes that result Out of date. Binding to a commit (Round 5's decline) is not used: a commit misses uncommitted work. |
| Rechecked, not reopened | A develop run that passes runs every other out-of-date command test again (the engine, no model), so one specification's work cannot silently leave another's pass standing on old code; the run's result is then read by the same evaluator. `hermes rung recheck` and `POST .../recheck` do the same on request. |
| Protected test files | When a person approves a command test Rung records the content of the files it is judged by: files its command names, test modules it imports, a discovering runner's test files and the runner's configuration. A change to any of them (changed, created or deleted) does not stop the test running, so a person sees what the changed test says, but that result counts for nothing, pass or fail: the output names the files and the specification is Could not verify until a person accepts them (first built as refusing to run; frozen UC09 watches a run of a test file it edits, and seeing the output is what a person needs to judge the change) (`Accept changed files` on the test, `POST .../accept-files`); a develop run that changes them stops as Needs input. The worker's prompt names the protected files. |
| Required manual checks | A manual test is required unless marked optional. A required one blocks until a person records a pass and approves it (`Waiting for you`). An optional one never blocks unless its newest decided result is a failure. A manual test stored before this round has no `required` key and reads as optional, so no stored result changes meaning; the upgrade rewrites no stored value (RES-04), and every manual test written since stores the key; results recorded before the basis existed count and are flagged `legacy`. |
| Seen failing | Read for the current test version only: a failure of an earlier version of the test does not make the new one seen failing. |
| Colour means evidence | Approved and Drafted are neutral; green is kept for current evidence (pass, Verified, Released, Covered). Out of date uses the stale hue. A specification shows a Verification section with its state, its blockers and one next action button. |
| Limits kept explicit | The protection is an integrity check for cooperative local work, not a security boundary: a process with the same OS user can change anything, the store included. The basis covers the project folder only, not the interpreter, installed packages or services outside it. Cancelling stops processes; it does not roll back files. |


## Round 23: integration milestones, enforcement health, unreadable code never verifies (9 Nov 2026)

The same assessment asked for a system-level check over specifications that are each green on their own (SYS-01 M0), for the done hook's coverage to be reported as a separate fact from verification (R05), and for no positive result when the evidence cannot be read. A synthetic fixture, `linkpair`, shows the gap: its API returns `short_url`, its page reads `url`, both specifications are Verified and the journey fails with `KeyError: 'url'` (`tests/test_milestones.py`).

| Topic | Decision |
| --- | --- |
| Milestone | A milestone is a declared outcome: a user journey, optional architecture notes, a scope of approved specifications and its own checks (command or manual). It is a separate object, not a fifth ladder level, so a specification can serve several milestones and the ladder's meaning does not change. Ids are `M-1`, checks `M-1.a`. |
| Approval and versions | A person approves a milestone. Editing its scope, journey or checks raises its version and returns it to Draft; earlier runs stay in history marked `earlier version` and prove nothing for the new version. Check files are protected the same way as test files (Round 22). |
| One evaluator | Its verdict reads `Engine.verification()` for every included specification, never a second rule. States: Draft, Not ready for integration (an included specification is not verified now), Ready for integration, Verifying, Integration failed, Could not verify, Awaiting manual, Out of date (a pass or failure on code that has changed since), Verified. Each blocker has a stable code and there is one next action, as for a specification. |
| One state of the folder | All command checks of a run are reserved in one write transaction with the busy check, so a develop run cannot start while integration runs (`busy`), and a milestone does not run while a develop run changes the folder. |
| Doors | REST under `/projects/<p>/milestones`, `hermes rung milestone [M-1] [--run] [--export]` (exit 0 only when verified), the pane (Milestones on Home, a list, a form, the milestone view), a Markdown report in Rung's exports folder. No model is asked for any verdict. |
| Enforcement is its own fact | `hermes rung enforcement SESSION` reports `enforced` (the session holds claims and the store reads; each claim says whether it is verified now), `unbound` (no session id or no open claim) or `degraded` (the store cannot be read: the hook lets every call through, nothing is verified). The hook stays read only and fail open for unrelated tools. |
| One verdict per page | A page asks for the same specification from tiles, coverage, tree and lists. The verdict is memoised per specification for one state of the store (SQLite `data_version` plus this connection's changes) and one code basis, so any commit from any process or any file change recomputes it. Found by RES-05: Round 22's evaluator had doubled the large-project Home load (147 to 265 ms in the engine); memoised it is 71 ms. |
| Unreadable code never verifies | When the project's files cannot be read whole (the folder is missing, or more files than the limit after `.gitignore` and `.rungignore`), the specification is Could not verify with the blocker `basis_unknown` and the next action Repair project folder. A result recorded while the code could not be read counts as Out of date. Before this round both were read as a pass. |

## Round 24: stage 5, the rest of the outside assessment (9 Nov 2026)


| Topic | Decision |
| --- | --- |
| Scope | Usability first (B11, B14, B18, U02, U04, U12, U13, R11), then SYS-02 to SYS-13 in dependency order (02, 03, 05, 04, 06, 07, 08, 09, 10, 11, 12, 13). SYS-14 to SYS-16 get design notes in `docs/design/`, no code. |
| Acceptance | `docs/use-cases-5.md`, `docs/acceptance-5.md`, `scripts/acceptance-5.sh`: UC37 to UC56 in that fixed order. `ACCEPTANCE-5 THROUGH` names the unbroken passing run from UC37; a public update ships only use cases inside it. |
| Allocation (R11) | The frozen score text (`tags · load · rel · cost`, UC06) stays until the amendment; each part gains a plain description on focus and hover, and the suggestion explains fit and exclusions. |
| First page (U02) | The sample's ladder is frozen by UC13 (four approved rungs, one test). The proof is `Break the sample` and `Repair the sample`: sample-only file swaps that show a pass going Out of date, failing, and verifying again, with no bot. This replaces the brief's two-pass-one-fail sample, which would have changed the frozen sample. |
| Roadmap | `docs/roadmap.md` holds every brief item not done, with its dependency and criterion; built items move to `docs/verification.md`. |
| Time box | Stop at Tue 10 Nov 20:00 Brussels; video and dossier refresh start by Tue 14:00 with whatever is left. |

## Round 25: SYS-06 to SYS-13 (9 Nov 2026)

| Topic | Decision |
| --- | --- |
| Contract checks (SYS-06) | Ordinary commands attached to an approved contract; a person approves each. A result keeps the contract version and the code basis; either changing makes it Out of date. |
| Milestone extensions (SYS-07 to SYS-10) | Journeys, regression baseline, quality obligations and environment live on the milestone and feed its one verdict; there is no second completion authority. |
| Quality values | A measure is a pattern on the check's own output. No number found reads Could not verify, never passed. Security and accessibility obligations may be a required human review instead of a threshold. |
| Change impact (SYS-11) | Named component paths scope the evidence basis, plus every file outside all components. No paths means the whole project. Naming components is itself a basis change. Check everything ignores impact. |
| Scoped milestone verdict | A milestone with a component scope whose only gap is out-of-date specifications reads Out of date; an unscoped milestone keeps Not ready. |
| System report (SYS-12) | Deterministic, built from stored verdicts on the current basis; Accepted only when every milestone is verified now; each open item is named. |
| Budgets (SYS-13) | Attempts, minutes or both, set only by a person. An interrupted run is shown as such and is never counted as passed; resuming starts only unverified work. |

## Round 26: labels, machine load and the demo (9 Nov 2026)

| Topic | Decision |
| --- | --- |
| Machine load | While the verification chain runs, video renders from other sessions (ffmpeg, hyperframes, remotion) are reniced to the lowest priority; they keep running. Each chain stage waits for a settled load first. Why: the e2e timing budgets (a 1,040-row Home in two seconds) failed only when other work saturated the machine; the budgets stay as they are. |
| Demo | The Shortly demo is re-recorded as a longer cut of two to three minutes: the Shortly story plus contracts, the plan with a budget and a milestone journey. Never uploaded. |

## Round 27: the way to the Plan (10 Nov 2026)

| Topic | Decision |
| --- | --- |
| Plan entry | Recording the demo with real profiles found that the Plan (and its budget) could only be opened from the milestones list, which Home shows once something is verified or a milestone exists: on a new project there was no way to it. The Develop step now has a Plan button beside Send all, and Home's Milestones section offers Plan, Architecture and System report whether or not a milestone exists (the next take found Architecture had the same gap). Back returns where the person was (`tests/e2e/smoke/test_develop_plan_link.py`). |
| Demo journey check | The milestone's journey check in the demo (`journey/check_clicks.py`) is written by the person, starts Shortly for real and follows a short link three times over HTTP. It lives in `journey/`, listed in the demo project's `.rungignore`, so adding it does not put the specifications' evidence out of date. |
| Plan: a manual check left | A specification whose commands pass on the current code and whose only gap is a manual test reads Needs you in the plan ("commands pass; T-1.1c needs a person"), not Ready, so Start ready work does not start another run for it. Found recording the demo: with one place for the builder, Start ready work restarted that specification five times and the next one never ran (`tests/test_system.py::test_sys04_plan_leaves_a_manual_check_to_the_person`). |

## Round 28: the command environment (11 Nov 2026)

| Topic | Decision |
| --- | --- |
| Command environment | The catalog review of 3928b7ae asked that project commands stop inheriting the whole environment: tests, contract checks, milestone checks, the regression baseline, environment probes and migrations run code from the project being edited, and that code received every Hermes provider key. Each now runs with `PATH`, `HOME`, `LANG`, `LC_*`, `TMPDIR`, the project's own virtual environment (`VIRTUAL_ENV` when it lies inside the project, else `.venv` or `venv` with a `pyvenv.cfg`, its `bin` first on `PATH`) and the variables a person names for the project. `run_command` without an environment uses the same minimal set; there is no path back to the inherited one (`tests/test_command_env.py`). |
| Per-project variables | Project settings has an optional Environment variables field: names only, separated by spaces or commas, up to 50, each a valid variable name. Only a person sets it (REST, the pane); agents have no door to it. Values are read when a command starts and are never stored. A change is in the project's history (`tests/e2e/smoke/test_project_env_vars.py`). |
| Out of scope | Child Hermes runs (develop, drafting by a profile) are Hermes itself with the profile's own credentials; they keep the scrubbed environment they had. |
