"""`hermes rung doctor`: each check by name, its result, and for a failing one the fix.

Read only. It never changes the store, a project or Hermes; the fixes are printed for a person to run.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
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
    profiles, settings = None, {}
    if store.exists():
        try:
            conn = sqlite3.connect(f"file:{store}?mode=ro", uri=True)
            try:
                version = int(conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0])
                rows = conn.execute("SELECT name, folder, archived_at, test_command FROM projects").fetchall() \
                    if version >= 2 else \
                    [(n, f, None, t) for n, f, t in conn.execute("SELECT name, folder, test_command FROM projects")]
                profiles = [r[0] for r in conn.execute("SELECT name FROM profiles WHERE enabled = 1 ORDER BY name")]
                for k, v in conn.execute("SELECT key, value FROM settings WHERE key IN ('worker', 'drafting')"):
                    try:
                        settings[k] = json.loads(v)
                    except ValueError:
                        settings[k] = v
                integrity = conn.execute("PRAGMA quick_check").fetchone()[0]
                if integrity != "ok":
                    problem = f"integrity check: {integrity}"
            finally:
                conn.close()
        except sqlite3.Error as exc:
            problem = str(exc)
        out.append(_check("store", not problem, problem or str(store),
                          f"move '{store}' aside; Rung creates a new store on next start"))
        out.append(_check("store writable", os.access(store, os.W_OK), str(store),
                          f"make the store writable: chmod u+w '{store}'"))
        if version is not None:
            ok = version <= db.SCHEMA_VERSION
            detail = f"schema {version}" + (" (migrates on next open)" if version < db.SCHEMA_VERSION else "")
            out.append(_check("schema", ok, detail if ok else f"schema {version}, this Rung reads {db.SCHEMA_VERSION}",
                              "update Rung: hermes plugins update rung"))
    else:
        out.append(_check("store", writable, f"{store} (created on first start)",
                          f"make '{folder}' writable"))

    if profiles is not None:
        out.append(_check("profiles", bool(profiles), ", ".join(profiles) or "none enabled",
                          "enable a profile: Rung pane, Rung settings, Profiles"))
        worker = settings.get("worker") if isinstance(settings.get("worker"), dict) else {}
        wk = worker.get("kind", "hermes") if worker or "worker" not in settings else None
        out.append(_check("worker", wk in ("hermes", "stub"), f"worker {wk}",
                          "set the worker: Rung pane, Rung settings, Develop runs"))
        drafting = settings.get("drafting") if isinstance(settings.get("drafting"), dict) else {}
        dk = drafting.get("kind", "stub") if drafting or "drafting" not in settings else None
        dok = dk == "stub" or (dk == "profile" and drafting.get("profile") in profiles)
        out.append(_check("drafting", dok, f"drafting {dk}" + (f" with {drafting.get('profile')}" if dk == "profile" else ""),
                          "set drafting: Rung pane, Rung settings, Drafting"))

    for name, pfolder, archived, command in rows or []:
        if archived is not None:
            continue
        folder_ok = Path(pfolder).expanduser().is_dir()
        out.append(_check(f"project {name} folder", folder_ok, pfolder,
                          f"restore the folder, or change it: Rung pane, {name}, Project settings"))
        cmd_ok, detail = _test_command(command or "", Path(pfolder).expanduser())
        out.append(_check(f"project {name} test command", cmd_ok, detail,
                          f"install it, or change it: Rung pane, {name}, Project settings"))

    bundle = plugin_root / "desktop" / "plugin.js"
    out.append(_check("desktop pane", bundle.is_file() and bundle.stat().st_size > 0, str(bundle),
                      "reinstall the plugin: hermes plugins install <rung source> --enable"))
    manifest = plugin_root / "dashboard" / "manifest.json"
    out.append(_check("dashboard bridge", manifest.is_file(), str(manifest),
                      "reinstall the plugin: hermes plugins install <rung source> --enable"))

    hb = hermes_bin or ""
    found = bool(hb) and (Path(hb).exists() or bool(_which(hb)))
    ver = _hermes_version()
    out.append(_check("hermes", found, (hb or "not found") + (f" (Hermes {ver})" if ver else ""),
                      "put the hermes command on PATH; develop runs start profiles through it"))
    return out


SHELL_WORDS = {"cd", "true", "false", "test", "[", ":", ".", "source", "echo", "exit", "export", "env", "set"}


def _test_command(command: str, folder: Path) -> tuple[bool, str]:
    """The project's test command names a program this machine has: on PATH, in the folder, or in its venv."""
    command = command.strip()
    if not command:
        return False, "no test command"
    try:
        words = shlex.split(command)
    except ValueError:
        return False, f"{command} (unbalanced quotes)"
    words = [w for w in words if not ("=" in w and not w.startswith(("=", "-")) and w.split("=")[0].isidentifier())]
    if not words or words[0] in SHELL_WORDS:
        return True, command
    prog = words[0]
    if "/" in prog:
        p = Path(prog).expanduser()
        p = p if p.is_absolute() else folder / p
        return p.exists(), command
    extra = os.pathsep.join(str(folder / v / "bin") for v in (".venv", "venv"))
    found = shutil.which(prog, path=extra + os.pathsep + os.environ.get("PATH", ""))
    return bool(found), command if found else f"{command} ({prog} not found)"


def _hermes_version() -> str:
    """The installed Hermes package's version, from its distribution metadata; never starts hermes, which
    can take a minute to answer. Empty when the install does not record one."""
    try:
        from importlib.metadata import version
        v = version("hermes-agent")
    except Exception:
        return ""
    return "" if v in ("", "0.0.0") else v


def _which(cmd: str) -> str | None:
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
