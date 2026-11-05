# Testing Rung

Every suite runs from the repository root with the project's virtual environment (`.venv`, Python 3.11,
pytest and Playwright). None of them reads or writes the Rung data of a real Hermes profile.

## Suites

| Suite | Command | Needs | Time |
| --- | --- | --- | --- |
| Unit (engine, API, CLI, tools) | `.venv/bin/python -m pytest -q tests --ignore=tests/e2e` | nothing else | ~1.5 min |
| Use cases UC01 to UC22 | `scripts/acceptance.sh` | the e2e environment | ~15 min |
| One use case | `.venv/bin/python -m pytest -q tests/e2e/test_uc14_*.py` | the e2e environment | seconds to a minute |
| Smoke (restart, themes, empty states, cancel, real profile, worst case) | `.venv/bin/python -m pytest -q tests/e2e/smoke` | the e2e environment | ~2 min |
| Clean install | `scripts/smoke-install.sh` | `hermes`, git | ~1 min |
| Gate | `bash ~/.hermes/scripts/rung-gate.sh` | maintainer machine only | ~2 min |

### The e2e environment

`scripts/e2e-up.sh` starts it; `scripts/e2e-up.sh down` stops it. It is a throwaway Hermes home under
`~/.cache/rung-e2e/home` with Rung linked in, a deterministic stub chat model on port 18765 and the Hermes
Desktop dev build exposing CDP on `127.0.0.1:9222`. Every test points the running backend at its own store
under pytest's temporary folder, so tests never share data. The window is laid out at 1440x900.

Only one run at a time: the environment is single tenant (one Desktop, one CDP port). Do not restart it
while another run is attached.

After changing `rung_engine/` restart it (`down`, then up) so the backend loads the new code. After
changing `desktop/src/` rebuild the bundle: `.venv/bin/python scripts/build_desktop.py`.

## Reset

| What | How |
| --- | --- |
| The sample project, nothing else | `hermes rung demo reset` |
| The e2e environment | `scripts/e2e-up.sh down && scripts/e2e-up.sh` |
| A test's data | nothing to do: each test has its own store, removed with pytest's temporary folder |
| Your own install's store | `hermes rung where` names it; move it aside and Rung starts a new one |

## Where evidence lands

| Evidence | Path |
| --- | --- |
| Use case screenshots | `evidence/ucNN.png` (one per use case, fresh each acceptance run) |
| Use case JUnit and logs | `evidence/ucNN.xml`, `evidence/ucNN.log` |
| Readiness JUnit and logs | `evidence/readiness/` |
| Smoke screenshots | `$RUNG_SMOKE_SHOTS`, default `/tmp/rung-smoke` |
| Read-out exports | `<store folder>/exports/` |
| Develop run logs | `<store folder>/logs/run-N.log` |

## Exploratory testing

The feature map in `docs/features/README.md` lists every feature, the view it lives in and the test that
pins it. `docs/charters.md` has one or more charters per feature. The project-local skill

Seed data for exploration comes from the same seams the tests use (`tests/support/seed.py`): the
`csvtidy` and `notes-sync` demo projects, the merge flow, a 500-rung ladder (`seed_large`) and the
worst-case wording used by the smoke suite.

## Reporting a finding

Name the view, the steps from a fresh store, what you saw, and what the stored state says
(`hermes rung --json status`, `hermes rung tree`). A finding becomes a bug once a test that encodes it fails.
