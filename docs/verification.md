# What "verified" means in Rung

Rung's gate (`hermes rung check S-2.1`, the `rung_check` tool, the done hook, the pane) answers one question:
does the evidence that a person approved still hold for the code as it is now? One engine function,
`Engine.verification()`, answers it; every surface reads that answer and none rebuilds it.

## Four separate facts

| Fact | Means | Shown as |
| --- | --- | --- |
| Contract approved | A person approved the specification and the tests that check it. | Approved (neutral) |
| Execution passed | One run of one test passed, on one state of the code. | `#3 pass` in the history, kept for good |
| Verification current | Every required test's newest result is a pass on the code as it is now, with the test's files as approved. | Verified (green), Released, Covered |
| Accepted | A person approved each required manual result. | Waiting for you until then |

A pass in the history stays a pass. It stops counting for verification when the code or the test it ran on has
changed since.

## The rule

A specification is verified when all of these hold:

1. It is approved and nothing above it (requirement, need) is stale.
2. It has at least one accepted test, and at least one of them can release it (a command test, or a manual test).
3. For every required test, the newest result of the current test version is a pass:
   - recorded on the project's current code basis (see below), and not changed under it while it ran;
   - for a command test, run with its protected files as a person approved them;
   - for a manual test, approved by a person.
4. No optional test's newest decided result is a failure.

AI judged tests are advisory: their pass never verifies anything, their failure blocks.

## Per test: newest result decides

| Newest result of a required test | History kept | Verification | Blocker code | Next action |
| --- | --- | --- | --- | --- |
| Pass on the current basis | yes | counts | | |
| Pass on another basis | yes | Out of date | `out_of_date` | Run tests |
| Pass while a file it ran against changed | yes | Out of date | `out_of_date` | Run tests |
| Fail | yes | Failed | `failed` | Open failing test |
| Never run (command) | | Not checked | `not_run` | Run tests |
| Never run (required manual) | | Waiting for you | `manual_missing` | Record manual result |
| Manual pass waiting for approval | yes | Waiting for you | `manual_pending` | Approve manual result |
| Running | yes | Checking | `checking` | |
| Could not run | yes | Could not verify | `could_not_verify` | Open test |
| Not run: its protected files changed | yes | Could not verify | `verification_changed` | Review test files |
| Cancelled | yes, as cancelled | the result before it decides | | |

Upstream edits (Round 4's staleness) still apply first: a test whose specification was edited after its pass has
no result for the current version until it runs again.

## Code basis

Each execution records a digest of the project's files when it starts and when it ends.

- Files: every file in the project folder except those its `.gitignore` files ignore (the root one, nested ones
  and `.git/info/exclude`, read without starting git, so the read-only done hook computes the same value). Generated and runtime files are never part of it (`.git`, `node_modules`, `__pycache__`,
  virtual environments, caches, `dist`, `build`, `*.pyc`, `*.db`, `*.sqlite`, `*.log`). A `.rungignore` file in
  the project folder lists more, one pattern per line.
- Uncommitted changes count: the basis is the content, not a commit.
- A file a check creates (its own output) does not change what it applies to; a file that existed and changed
  while it ran does.
- Over 20,000 files or 256 MB the basis reads `unknown`; a pass then counts and carries the `basis_unknown` flag.
- Results recorded before Rung 0.4 have no basis; they count and carry the `legacy` flag.

When a develop run passes, the engine runs every other out-of-date command test again (no model involved), so
work on one specification cannot leave another's pass standing on code it changed. `hermes rung recheck` does the
same on request.

## Protected test files

When a person approves a command test, Rung records the content of the files it is judged by:

- files named in its command (a test file, a script, a fixture), including ones that do not exist yet;
- test modules its command imports;
- every test file, when the command runs a discovering runner (`pytest`, `python -m unittest`, `npm test`,
  `go test`, `cargo test`, `jest`, `vitest`, `mocha`, `rspec`, `phpunit`);
- runner configuration (`pytest.ini`, `tox.ini`, `conftest.py`, `jest.config.*`, `vitest.config.*`, `.mocharc.*`,
  `phpunit.xml`).

If any of them changed, appeared or disappeared since, the test still runs, so a person can see what the changed
test says, but its result counts for nothing either way: the output starts by naming the files, the
specification is Could not verify and shows Review test files. A develop run that changed them stops as Needs input. A
person can look at the change and accept it (`Accept changed files`), after which results are judged against the
new files.

## When the code cannot be read

If the project folder is missing, or holds more files than Rung reads (after `.gitignore` and `.rungignore`),
there is no basis to compare. Nothing is verified then: the specification shows Could not verify with the
blocker `basis_unknown` and the next action Repair project folder. A result recorded while the code could not be
read is Out of date once it can.

## Integration milestones

Each specification can be verified while the system is not: an API returns `short_url` and the page reads `url`.
A milestone names a user journey, the approved specifications it spans and its own checks, which exercise the
journey across them.

| State | Meaning |
| --- | --- |
| Draft | Being written, or changed since approval (its version went up). |
| Not ready for integration | An included specification is not verified now. |
| Ready for integration | Every included specification is verified; the checks have not run on this code. |
| Verifying | A check is running. |
| Integration failed | A required check failed on the code as it is now. |
| Could not verify | A check could not run, or its approved files changed. |
| Awaiting manual | Only required manual checks are missing. |
| Out of date | Its newest result ran on code that has changed since. |
| Verified | Every included specification is verified and every required check passed on this code and this version. |

`hermes rung milestone M-1 --run` runs its command checks and exits 0 only when it is Verified. While a check
runs no develop run starts in that project.

## Enforcement is a separate fact

Verification says whether the work is done. Enforcement says whether the done hook is watching a chat at all.
`hermes rung enforcement SESSION`:

| Case | Result |
| --- | --- |
| No session id | `unbound`: nothing to enforce. |
| Session holds no open claim | `unbound`. |
| Session holds claims, store reads | `enforced`; each claim says verified or blocked, with its blockers. |
| Store missing or unreadable | `degraded`: the hook lets every call through; nothing is verified. |
| A tool the hook does not watch | Always passes; only `rung_report`, `kanban_complete` and `todo_list` are judged. |
| Hermes restarts | Claims live in the store and are judged again; what a session's todo items named is kept in memory only, so a todo item renamed across a restart is judged by its new text. |

## What it does not promise

- It is an integrity check for cooperative local work, not a security boundary. A process running as the same OS
  user can change any file, the Rung store included.
- The basis covers the project folder. It does not cover the interpreter, installed packages, environment
  variables or services the tests reach.
- Cancelling stops processes. It does not undo file changes.
- Approvals are local actions in the Desktop pane; there is no separate identity check.
- The done hook watches `rung_report`, `kanban_complete` and `todo_list` for a session holding a claim. Another
  way of declaring work finished is not seen. If the store cannot be read, the hook lets the call through and
  `hermes rung doctor` reports the store.

## Reading it

- `hermes rung check S-2.1` (exit 0 only when verified) and `hermes rung check --all`.
- `hermes rung verify S-2.1`: state, required checks satisfied, every blocker with its code, the next action.
- `hermes rung milestone M-1`: the milestone's state, its blockers and next action.
- `GET /api/plugins/rung/projects/<project>/verification/<spec>`: the same as JSON.
- The pane: the specification's Verification section; a test's Judged by list; `pass · out of date` in the
  history.

## A small task stays small

`Quick task` (REST `POST /projects/<p>/quick`) writes one need, one requirement, one specification and one to five
tests in one transaction, as drafts below the person's own need. The card is a view of those rungs: `Approve`
sends every id with the version the card showed and is refused, approving nothing, when any of them changed;
`Build and verify` starts the ordinary develop run; the verdict is the same evaluator as everywhere. `Show full
ladder` opens the same need. An edit to an approved check resets its approval and its earlier results stop
counting, under the same rules as the ladder. Built: SYS items are not involved.

## When is a need complete

A need is complete only when it is approved, every requirement it asks for is approved and has at least one
specification, and every specification under those requirements is verified now (the same evaluator). Anything
else is listed by id with its reason: `no_specification`, `not_approved` or `not_verified` with the
specification and its state. A person can take a requirement out of scope with a reason; it stays listed as out of
scope, never silently dropped, and can be put back. The need view, Home's Needs list and `hermes rung verify N-1`
(exit 0 only when complete) read the one method, `Engine.need_completeness`.

## The dock leads with this chat

The dock's first section is the focused chat (the Desktop's public `host.state.focusedStoredSessionId` and
`focusedSessionProfile`). A chat that holds a claim shows each task with its outcome, the one verification result,
its first blocker and its next action; the blocker opens that specification's Verification section; the ladder
starts collapsed while the chat holds a task. A chat with no claim reads `Not bound`, shows the project's next
task and offers `Bind to task`: the confirmation names the chat, the profile and that done is refused until the
specification is verified. Only `Bind` opens a claim, through the same rules as the agent's `rung_claim`
(REST `POST /projects/<p>/rungs/<S>/bind`), so the done hook enforces it for that chat.

