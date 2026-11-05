"""`hermes rung doctor`: each check by name, its result, and for a failing one the fix.

Read only. It never changes the store, a project or Hermes; the fixes are printed for a person to run.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

from . import db

ROOT = Path(__file__).resolve().parent.parent


def _check(name: str, ok: bool, detail: str, fix: str = "") -> dict:
    return {"name": name, "ok": bool(ok), "detail": detail, "fix": "" if ok else fix}


def run_checks(store: Path, hermes_bin: str | None = None, plugin_root: Path = ROOT) -> list[dict]:
    out = []
    out.append(_check("python", sys.version_info >= (3, 10), f"Python {sys.version.split()[0]}",
                      "run Hermes with Python 3.10 or newer"))

    folder = store.parent
    writable = folder.is_dir() and os.access(folder, os.W_OK)
    out.append(_check("store folder", writable, str(folder),
                      f"create the folder and make it writable: mkdir -p '{folder}'"))

    version, rows, problem = None, None, ""
    if store.exists():
        try:
            conn = sqlite3.connect(f"file:{store}?mode=ro", uri=True)
            try:
                version = int(conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0])
                rows = conn.execute("SELECT name, folder, archived_at FROM projects").fetchall() if version >= 2 else \
                    [(n, f, None) for n, f in conn.execute("SELECT name, folder FROM projects")]
                integrity = conn.execute("PRAGMA quick_check").fetchone()[0]
                if integrity != "ok":
                    problem = f"integrity check: {integrity}"
            finally:
                conn.close()
        except sqlite3.Error as exc:
            problem = str(exc)
        out.append(_check("store", not problem, problem or str(store),
                          f"move '{store}' aside; Rung creates a new store on next start"))
        if version is not None:
            ok = version <= db.SCHEMA_VERSION
            detail = f"schema {version}" + (" (migrates on next open)" if version < db.SCHEMA_VERSION else "")
            out.append(_check("schema", ok, detail if ok else f"schema {version}, this Rung reads {db.SCHEMA_VERSION}",
                              "update Rung: hermes plugins update rung"))
    else:
        out.append(_check("store", writable, f"{store} (created on first start)",
                          f"make '{folder}' writable"))

    for name, pfolder, archived in rows or []:
        if archived is not None:
            continue
        ok = Path(pfolder).expanduser().is_dir()
        out.append(_check(f"project {name} folder", ok, pfolder,
                          f"restore the folder, or change it: Rung pane, {name}, Project settings"))

    bundle = plugin_root / "desktop" / "plugin.js"
    out.append(_check("desktop pane", bundle.is_file() and bundle.stat().st_size > 0, str(bundle),
                      "reinstall the plugin: hermes plugins install <rung source> --enable"))
    manifest = plugin_root / "dashboard" / "manifest.json"
    out.append(_check("dashboard bridge", manifest.is_file(), str(manifest),
                      "reinstall the plugin: hermes plugins install <rung source> --enable"))

    hb = hermes_bin or ""
    found = bool(hb) and (Path(hb).exists() or bool(_which(hb)))
    out.append(_check("hermes", found, hb or "not found",
                      "put the hermes command on PATH; develop runs start profiles through it"))
    return out


def _which(cmd: str) -> str | None:
    import shutil
    return shutil.which(cmd)


def render(checks: list[dict]) -> str:
    lines = []
    for c in checks:
        lines.append(f"{'ok  ' if c['ok'] else 'FAIL'}  {c['name']}: {c['detail']}")
        if not c["ok"]:
            lines.append(f"      fix: {c['fix']}")
    failed = sum(1 for c in checks if not c["ok"])
    lines.append(f"rung doctor: {'PASS' if not failed else f'FAIL ({failed})'}")
    return "\n".join(lines)
