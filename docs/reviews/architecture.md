# Architecture review

Review (5 Nov 2026), read-only, covering layering
(engine, API, pane), the single write path, schema versioning and migration, the error model, concurrency,
command execution safety and performance. It probed each claim with code and the unit suite (81 passed),
without the e2e harness. Every finding is pinned by a test in `tests/test_architecture_review.py`.

## Verified as designed

- Layering: the pane talks only to the REST seam (`desktop/src/00-core.js` `rest`, dashboard
  `dashboard/plugin_api.py` to `rung_engine/api.py` `handle`); no SQLite access in the pane or the bundle.
- Migrations run one version per transaction in order; the frozen schema-1 store migrates and reopens
  idempotently (`tests/test_lifecycle.py`).
- Errors are `RungError` with `code`, `status` and `field`; `api.handle` maps them to the response.
- A test folder is re-resolved against the project folder just before a command runs, so a symlink cannot
  lead outside it.
- A runner stopped from outside ends Unknown, a person's Stop ends Cancelled; the service reaps runners.
- Performance at 500 rungs and 2,000 executions: seeding 0.32 s, engine `tree` and `home` about 16 ms, the
  API home call about 54 ms.

## Findings

| # | Area | Severity | Finding | Status | Reason |
| --- | --- | --- | --- | --- | --- |
| A1 | Concurrency | high | Two edits that loaded the same version could both pass the version check before either wrote, so one was lost | fixed | Every `@writes` method holds the engine lock from its checks to its commit, and `edit` re-reads the version inside the write transaction (`_still_version`), which also stops a second process; `edit_test` passes its checked version through. Tests: a two-thread race ends one `ok` and one `conflict`; a second engine on the same store is refused |
| A2 | Command safety | high | A draft command test could run through the API | fixed | `begin_execution` runs only approved tests. The one exception is a person pressing `Run once` in the test editor (`once: true`, human actor only); develop runs, `Run tests`, the CLI and agent tools never run a draft. Test: refused through the API, refused for an agent, allowed for the person's Run once |
| A3 | Command safety | high | Exit 126 or 127 counted as Pass when the pass rule expected that code | fixed | A shell that could not start the command is Error before any pass rule is read. Tests for 126 and 127 |
| A4 | Write guard | medium | A draft finishing after its project was archived wrote into the read-only project | fixed | Archive, delete and retire wait while a develop run, a draft or a test execution is in flight (`_refuse_while_busy`, `rung_engine/lifecycle.py`). Test: archive and delete refused while drafting, allowed after |
| A5 | Schema | medium | A store from a newer release was changed (WAL mode, schema DDL) before being refused | fixed | `db.connect` reads `schema_version` first and refuses a newer store before any statement that writes. Test: the file's bytes and a dropped index are unchanged after refusal |
| A6 | Single write path | medium | Streamed execution output updated the store and the revision in two statements outside `_tx` | fixed | Output updates go through `_tx`, which bumps the revision in the same transaction. Test: the revision moves while output streams |
| A7 | Pane concurrency | medium | Editors froze the version when they first loaded, so a refetch before typing caused a false conflict | fixed | `useBase(v, follow)` follows refetches while the form still shows the live rung (the specification editor, whose fields read the live text until typed) and holds once the person types. The requirement and test editors copy the rung into their form once, so their held version is the version of what the form shows; a save against a newer version is a true conflict and stays refused |
