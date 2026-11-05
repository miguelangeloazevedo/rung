"""Where Rung keeps its store inside Hermes, and the one Service per process.

The store follows the active Hermes home (`<home>/plugin-data/rung/rung.db`), so every profile
has its own ladder. `RUNG_STORE` overrides it for scripts and tests.
"""

from __future__ import annotations

import os
import shutil
import sys
import threading
from pathlib import Path

from .core import Engine
from .service import Service, pid_alive

_LOCK = threading.Lock()
_SERVICES: dict[str, Service] = {}


def hermes_home() -> Path:
    try:
        from hermes_constants import get_hermes_home
        return Path(get_hermes_home())
    except Exception:
        return Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")


def store_path() -> Path:
    """RUNG_STORE, else the path written in `<plugin-data>/rung/store` (one line), else the default."""
    env = os.environ.get("RUNG_STORE")
    if env:
        return Path(env).expanduser()
    default = _default_store()
    pointer = default.parent / "store"
    try:
        target = pointer.read_text().strip()
    except OSError:
        target = ""
    return Path(target).expanduser() if target else default


def _default_store() -> Path:
    try:
        from plugins.plugin_storage import plugin_data_dir
        return plugin_data_dir("rung") / "rung.db"
    except Exception:
        d = hermes_home() / "plugin-data" / "rung"
        d.mkdir(parents=True, exist_ok=True)
        return d / "rung.db"


def hermes_bin() -> str:
    found = shutil.which("hermes")
    if found:
        return found
    cand = Path(sys.executable).parent / "hermes"
    return str(cand) if cand.exists() else "hermes"


def hermes_profiles() -> list[str]:
    """Names of the Hermes profiles on this machine (default plus ~/.hermes/profiles/*)."""
    names = ["default"]
    root = hermes_home()
    # A profile home lives under <root>/profiles/<name>; walk up to the root when inside one.
    if root.parent.name == "profiles":
        root = root.parent.parent
    pdir = root / "profiles"
    if pdir.is_dir():
        names += sorted(p.name for p in pdir.iterdir() if p.is_dir() and not p.name.startswith("."))
    return names


def service() -> Service:
    path = str(store_path())
    with _LOCK:
        svc = _SERVICES.get(path)
        if svc is None:
            engine = Engine(path)
            if not engine.profiles():
                engine.sync_profiles(hermes_profiles())
            svc = Service(engine, hermes_bin=hermes_bin(), log_dir=Path(path).parent / "logs")
            svc.reconcile()
            _SERVICES[path] = svc
        return svc


__all__ = ["service", "store_path", "hermes_profiles", "hermes_bin", "pid_alive"]
