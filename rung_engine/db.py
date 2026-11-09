"""SQLite storage for the Rung engine. Standard library only."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 5

# Columns added after schema 1, applied to older stores by `migrate`. New stores get them from SCHEMA.
MIGRATIONS = {
    2: [
        ("projects", "archived_at", "REAL"),
        ("rungs", "retired_at", "REAL"),
        ("rungs", "retired_reason", "TEXT"),
        ("rungs", "retired_by", "TEXT"),
        ("attempts", "reason", "TEXT NOT NULL DEFAULT ''"),
    ],
    3: [
        ("profiles", "tools", "TEXT NOT NULL DEFAULT '[]'"),
        ("profiles", "at_once", "INTEGER NOT NULL DEFAULT 2"),
    ],
    # Evidence identity (Round 22): what each result applies to, and the files a test was approved with.
    4: [
        ("executions", "basis_start", "TEXT NOT NULL DEFAULT ''"),
        ("executions", "basis_end", "TEXT NOT NULL DEFAULT ''"),
        ("executions", "reason", "TEXT NOT NULL DEFAULT ''"),
        ("rungs", "assets", "TEXT"),
    ],
    # How to try the result (Round 24, U12): an instruction and an optional command a person starts.
    5: [
        ("projects", "try_it", "TEXT NOT NULL DEFAULT '{}'"),
        # Components a milestone touches (SYS-02); the architecture itself is in new tables.
        ("milestones", "system", "TEXT NOT NULL DEFAULT '{}'"),
        # Isolated runs (SYS-05, B12): the project's run mode, a run's workspace, an attempt's local results.
        ("projects", "run_mode", "TEXT NOT NULL DEFAULT 'shared'"),
        ("runs", "workspace", "TEXT NOT NULL DEFAULT ''"),
        ("attempts", "local_results", "TEXT NOT NULL DEFAULT '[]'"),
        # The plan (SYS-04): its attempt budget and the runs it started.
        ("projects", "plan", "TEXT NOT NULL DEFAULT '{}'"),
    ],
}

# Data steps run in the same transaction as a version's columns. Version 4: a manual test written before
# required checks existed keeps the meaning it had (not needed to verify, a recorded failure still blocks), so
# no stored green or red changes when the store is opened; tests written from now on are required by default.
# Data steps rewrite stored values; a release adds none unless it must (RES-04: an upgraded store keeps every
# existing value). Schema 4 adds columns only: a manual test written before it has no `required` key, which
# the engine reads as optional, the meaning it had.
DATA_STEPS: dict[int, list[str]] = {}


class StoreTooNew(RuntimeError):
    pass

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    pk            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL UNIQUE,
    folder        TEXT NOT NULL,
    test_command  TEXT NOT NULL,
    profiles      TEXT NOT NULL DEFAULT '[]',
    created_at    REAL NOT NULL,
    last_activity REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS profiles (
    name     TEXT PRIMARY KEY,
    labels   TEXT NOT NULL DEFAULT '[]',
    cost     INTEGER NOT NULL DEFAULT 5,
    max_runs INTEGER NOT NULL DEFAULT 5,
    enabled  INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS rungs (
    pk           INTEGER PRIMARY KEY,
    project_pk   INTEGER NOT NULL REFERENCES projects(pk) ON DELETE CASCADE,
    rid          TEXT NOT NULL,
    kind         TEXT NOT NULL,
    parent_pk    INTEGER REFERENCES rungs(pk) ON DELETE CASCADE,
    num          INTEGER NOT NULL,
    text         TEXT NOT NULL,
    detail       TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL,
    version      INTEGER NOT NULL DEFAULT 1,
    author_kind  TEXT NOT NULL,
    author_name  TEXT NOT NULL,
    approved_by  TEXT,
    approved_at  REAL,
    proposer     TEXT,
    source_chat  TEXT,
    data         TEXT NOT NULL DEFAULT '{}',
    valid_from   INTEGER NOT NULL DEFAULT 0,
    assets       TEXT,
    created_at   REAL NOT NULL,
    updated_at   REAL NOT NULL,
    UNIQUE (project_pk, rid)
);

CREATE TABLE IF NOT EXISTS rung_versions (
    pk       INTEGER PRIMARY KEY,
    rung_pk  INTEGER NOT NULL REFERENCES rungs(pk) ON DELETE CASCADE,
    version  INTEGER NOT NULL,
    text     TEXT NOT NULL,
    detail   TEXT NOT NULL,
    data     TEXT NOT NULL DEFAULT '{}',
    at       REAL NOT NULL,
    by_name  TEXT NOT NULL,
    by_kind  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS changes (
    pk            INTEGER PRIMARY KEY,
    project_pk    INTEGER NOT NULL REFERENCES projects(pk) ON DELETE CASCADE,
    rung_pk       INTEGER NOT NULL REFERENCES rungs(pk) ON DELETE CASCADE,
    seq           INTEGER NOT NULL,
    before_text   TEXT NOT NULL,
    after_text    TEXT NOT NULL,
    before_detail TEXT NOT NULL,
    after_detail  TEXT NOT NULL,
    from_version  INTEGER NOT NULL,
    to_version    INTEGER NOT NULL,
    stale         TEXT NOT NULL DEFAULT '[]',
    at            REAL NOT NULL,
    by_name       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS suggestions (
    pk         INTEGER PRIMARY KEY,
    project_pk INTEGER NOT NULL REFERENCES projects(pk) ON DELETE CASCADE,
    parent_pk  INTEGER REFERENCES rungs(pk) ON DELETE CASCADE,
    target     TEXT NOT NULL,
    text       TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'open',
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    pk           INTEGER PRIMARY KEY,
    project_pk   INTEGER NOT NULL REFERENCES projects(pk) ON DELETE CASCADE,
    spec_pk      INTEGER NOT NULL REFERENCES rungs(pk) ON DELETE CASCADE,
    profile      TEXT NOT NULL,
    picked_by    TEXT NOT NULL,
    status       TEXT NOT NULL,
    max_attempts INTEGER NOT NULL,
    timeout_s    INTEGER NOT NULL,
    worker       TEXT NOT NULL DEFAULT '{}',
    pid          INTEGER,
    log_path     TEXT,
    commit_ref   TEXT,
    reason       TEXT,
    cancel       INTEGER NOT NULL DEFAULT 0,
    created_at   REAL NOT NULL,
    started_at   REAL,
    ended_at     REAL
);

CREATE TABLE IF NOT EXISTS attempts (
    pk             INTEGER PRIMARY KEY,
    run_pk         INTEGER NOT NULL REFERENCES runs(pk) ON DELETE CASCADE,
    n              INTEGER NOT NULL,
    status         TEXT NOT NULL,
    prompt         TEXT NOT NULL DEFAULT '',
    fed_in         TEXT NOT NULL DEFAULT '',
    fed_forward    TEXT NOT NULL DEFAULT '',
    files_changed  TEXT NOT NULL DEFAULT '[]',
    commands       TEXT NOT NULL DEFAULT '[]',
    worker_output  TEXT NOT NULL DEFAULT '',
    started_at     REAL NOT NULL,
    ended_at       REAL,
    UNIQUE (run_pk, n)
);

CREATE TABLE IF NOT EXISTS executions (
    pk          INTEGER PRIMARY KEY,
    test_pk     INTEGER NOT NULL REFERENCES rungs(pk) ON DELETE CASCADE,
    n           INTEGER NOT NULL,
    seq         INTEGER NOT NULL,
    kind        TEXT NOT NULL,
    status      TEXT NOT NULL,
    exit_code   INTEGER,
    output      TEXT NOT NULL DEFAULT '',
    command     TEXT NOT NULL DEFAULT '',
    carried_by  TEXT NOT NULL,
    run_pk      INTEGER REFERENCES runs(pk) ON DELETE SET NULL,
    attempt     INTEGER,
    context     TEXT NOT NULL DEFAULT '',
    commit_ref  TEXT NOT NULL DEFAULT '',
    basis_start TEXT NOT NULL DEFAULT '',
    basis_end   TEXT NOT NULL DEFAULT '',
    reason      TEXT NOT NULL DEFAULT '',
    note        TEXT NOT NULL DEFAULT '',
    recorder    TEXT,
    approved_by TEXT,
    approved_at REAL,
    started_at  REAL NOT NULL,
    ended_at    REAL,
    UNIQUE (test_pk, n)
);

CREATE TABLE IF NOT EXISTS picks (
    pk        INTEGER PRIMARY KEY,
    spec_pk   INTEGER NOT NULL REFERENCES rungs(pk) ON DELETE CASCADE,
    profile   TEXT NOT NULL,
    picked_by TEXT NOT NULL,
    at        REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS defects (
    pk          INTEGER PRIMARY KEY,
    project_pk  INTEGER NOT NULL REFERENCES projects(pk) ON DELETE CASCADE,
    did         TEXT NOT NULL,
    title       TEXT NOT NULL,
    note        TEXT NOT NULL DEFAULT '',
    category    TEXT NOT NULL DEFAULT 'Implementation',
    test_pk     INTEGER NOT NULL REFERENCES rungs(pk) ON DELETE CASCADE,
    spec_pk     INTEGER NOT NULL REFERENCES rungs(pk) ON DELETE CASCADE,
    executions  TEXT NOT NULL DEFAULT '[]',
    created_by  TEXT NOT NULL,
    at          REAL NOT NULL,
    UNIQUE (project_pk, did)
);

CREATE TABLE IF NOT EXISTS events (
    pk          INTEGER PRIMARY KEY,
    project_pk  INTEGER REFERENCES projects(pk) ON DELETE CASCADE,
    kind        TEXT NOT NULL,
    data        TEXT NOT NULL DEFAULT '{}',
    by_name     TEXT NOT NULL,
    at          REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS claims (
    pk          INTEGER PRIMARY KEY,
    project_pk  INTEGER NOT NULL REFERENCES projects(pk) ON DELETE CASCADE,
    spec_pk     INTEGER NOT NULL REFERENCES rungs(pk) ON DELETE CASCADE,
    session_id  TEXT NOT NULL,
    chat        TEXT NOT NULL DEFAULT '',
    profile     TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'open',
    opened_at   REAL NOT NULL,
    closed_at   REAL,
    closed_by   TEXT,
    proof       TEXT NOT NULL DEFAULT '[]'
);

-- Bot help (Round 13): Place, Draft and Suggest jobs. Proposals only: nothing here is read by the
-- check, the done hook or a test result; a running Suggest counts toward its profile's At once.
CREATE TABLE IF NOT EXISTS bot_jobs (
    pk          INTEGER PRIMARY KEY,
    project_pk  INTEGER NOT NULL REFERENCES projects(pk) ON DELETE CASCADE,
    kind        TEXT NOT NULL,
    rung_pk     INTEGER REFERENCES rungs(pk) ON DELETE CASCADE,
    profile     TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'running',
    input       TEXT NOT NULL DEFAULT '{}',
    result      TEXT,
    error       TEXT NOT NULL DEFAULT '',
    basis       TEXT NOT NULL DEFAULT '[]',
    created_at  REAL NOT NULL,
    finished_at REAL
);

-- Integration milestones (decisions Round 23): a declared journey over approved specifications, with its own
-- approved cross-component checks and their runs. Every change to scope or checks is a new version.
CREATE TABLE IF NOT EXISTS milestones (
    pk           INTEGER PRIMARY KEY,
    project_pk   INTEGER NOT NULL REFERENCES projects(pk) ON DELETE CASCADE,
    mid          TEXT NOT NULL,
    num          INTEGER NOT NULL,
    title        TEXT NOT NULL,
    journey      TEXT NOT NULL DEFAULT '',
    architecture TEXT NOT NULL DEFAULT '',
    scope        TEXT NOT NULL DEFAULT '[]',
    system       TEXT NOT NULL DEFAULT '{}',
    status       TEXT NOT NULL DEFAULT 'draft',
    version      INTEGER NOT NULL DEFAULT 1,
    approved_by  TEXT,
    approved_at  REAL,
    created_at   REAL NOT NULL,
    updated_at   REAL NOT NULL,
    UNIQUE(project_pk, mid)
);

CREATE TABLE IF NOT EXISTS milestone_checks (
    pk           INTEGER PRIMARY KEY,
    milestone_pk INTEGER NOT NULL REFERENCES milestones(pk) ON DELETE CASCADE,
    cid          TEXT NOT NULL,
    text         TEXT NOT NULL DEFAULT '',
    data         TEXT NOT NULL DEFAULT '{}',
    assets       TEXT,
    status       TEXT NOT NULL DEFAULT 'active',
    created_at   REAL NOT NULL,
    UNIQUE(milestone_pk, cid)
);

CREATE TABLE IF NOT EXISTS milestone_runs (
    pk          INTEGER PRIMARY KEY,
    check_pk    INTEGER NOT NULL REFERENCES milestone_checks(pk) ON DELETE CASCADE,
    n           INTEGER NOT NULL,
    version     INTEGER NOT NULL,
    status      TEXT NOT NULL,
    command     TEXT NOT NULL DEFAULT '',
    exit_code   INTEGER,
    output      TEXT NOT NULL DEFAULT '',
    reason      TEXT NOT NULL DEFAULT '',
    note        TEXT NOT NULL DEFAULT '',
    carried_by  TEXT NOT NULL DEFAULT '',
    basis_start TEXT NOT NULL DEFAULT '',
    basis_end   TEXT NOT NULL DEFAULT '',
    started_at  REAL NOT NULL,
    ended_at    REAL,
    UNIQUE(check_pk, n)
);

-- Architecture baseline (Round 24, SYS-02): components and contracts, each a series of versions a person
-- approves. Approved versions stay as history.
CREATE TABLE IF NOT EXISTS arch (
    pk          INTEGER PRIMARY KEY,
    project_pk  INTEGER NOT NULL REFERENCES projects(pk) ON DELETE CASCADE,
    kind        TEXT NOT NULL,
    name        TEXT NOT NULL,
    created_at  REAL NOT NULL,
    UNIQUE(project_pk, kind, name)
);

CREATE TABLE IF NOT EXISTS arch_versions (
    pk          INTEGER PRIMARY KEY,
    arch_pk     INTEGER NOT NULL REFERENCES arch(pk) ON DELETE CASCADE,
    version     INTEGER NOT NULL,
    data        TEXT NOT NULL DEFAULT '{}',
    status      TEXT NOT NULL DEFAULT 'draft',
    by_name     TEXT NOT NULL DEFAULT '',
    approved_by TEXT,
    approved_at REAL,
    created_at  REAL NOT NULL,
    UNIQUE(arch_pk, version)
);

-- Contract checks (Round 24, SYS-06): approved commands run against a contract's real artifacts; each result
-- keeps the contract version and the code basis it was recorded on.
CREATE TABLE IF NOT EXISTS contract_checks (
    pk          INTEGER PRIMARY KEY,
    arch_pk     INTEGER NOT NULL REFERENCES arch(pk) ON DELETE CASCADE,
    cid         TEXT NOT NULL,
    command     TEXT NOT NULL,
    timeout     INTEGER NOT NULL DEFAULT 120,
    status      TEXT NOT NULL DEFAULT 'draft',
    by_name     TEXT NOT NULL DEFAULT '',
    approved_by TEXT,
    approved_at REAL,
    created_at  REAL NOT NULL,
    UNIQUE(arch_pk, cid)
);

CREATE TABLE IF NOT EXISTS contract_runs (
    pk          INTEGER PRIMARY KEY,
    check_pk    INTEGER NOT NULL REFERENCES contract_checks(pk) ON DELETE CASCADE,
    n           INTEGER NOT NULL,
    contract_version INTEGER NOT NULL,
    status      TEXT NOT NULL,
    exit_code   INTEGER,
    output      TEXT NOT NULL DEFAULT '',
    basis       TEXT NOT NULL DEFAULT '',
    carried_by  TEXT NOT NULL DEFAULT '',
    started_at  REAL NOT NULL,
    ended_at    REAL,
    UNIQUE(check_pk, n)
);

CREATE INDEX IF NOT EXISTS bot_jobs_profile ON bot_jobs(profile, kind, status);
CREATE INDEX IF NOT EXISTS claims_session ON claims(session_id, status);
CREATE INDEX IF NOT EXISTS claims_spec ON claims(spec_pk, status);
CREATE INDEX IF NOT EXISTS rungs_parent ON rungs(parent_pk);
CREATE INDEX IF NOT EXISTS executions_run ON executions(run_pk, attempt);
CREATE INDEX IF NOT EXISTS rungs_status ON rungs(project_pk, status);
CREATE INDEX IF NOT EXISTS rungs_project ON rungs(project_pk, kind);
CREATE INDEX IF NOT EXISTS executions_test ON executions(test_pk, n);
CREATE INDEX IF NOT EXISTS runs_status ON runs(status);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    """Open the store. Autocommit mode; the engine opens explicit transactions."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000")
    # A store written by a newer release is refused before anything here changes it.
    try:
        row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
    except sqlite3.Error:
        row = None
    if row is not None and int(row[0]) > SCHEMA_VERSION:
        conn.close()
        raise StoreTooNew(f"the store is schema {int(row[0])}; this Rung reads up to {SCHEMA_VERSION}")
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    except sqlite3.DatabaseError:
        pass
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    conn.execute("INSERT OR IGNORE INTO meta(key, value) VALUES ('schema_version', '1')")
    conn.execute("INSERT OR IGNORE INTO meta(key, value) VALUES ('seq', '0')")
    conn.execute("INSERT OR IGNORE INTO meta(key, value) VALUES ('rev', '0')")
    migrate(conn)
    return conn


def connect_readonly(path: str | Path) -> sqlite3.Connection:
    """Open an existing store for reading only: no schema, no migration, no journal change. Used by the
    done hook, which must never write. Raises when the file is missing or unreadable."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(str(path))
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5, isolation_level=None,
                           check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA query_only = ON")
    return conn


def schema_version(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()[0])


def migrate(conn: sqlite3.Connection) -> int:
    """Bring a store up to SCHEMA_VERSION, one version per transaction. A store written by a newer
    release is refused rather than guessed at. Every store, new or old, takes the same path."""
    have = schema_version(conn)
    if have > SCHEMA_VERSION:
        conn.close()
        raise StoreTooNew(f"the store is schema {have}; this Rung reads up to {SCHEMA_VERSION}")
    for version in range(have + 1, SCHEMA_VERSION + 1):
        conn.execute("BEGIN IMMEDIATE")
        try:
            for table, column, decl in MIGRATIONS.get(version, []):
                cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
                if column not in cols:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
            for stmt in DATA_STEPS.get(version, []):
                conn.execute(stmt)
            conn.execute("UPDATE meta SET value = ? WHERE key = 'schema_version'", (str(version),))
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        conn.execute("COMMIT")
    return SCHEMA_VERSION
