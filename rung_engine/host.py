"""Where Rung keeps its store inside Hermes, and the one Service per process.

The store follows the active Hermes home (`<home>/plugin-data/rung/rung.db`), so every home can
have its own ladder. A profile with no Rung store of its own is a carrier of its root home's ladder
and uses that one, so a chat or a develop run as `coder` claims and checks the work it was sent
(Round 8 of decisions.md). `RUNG_STORE` overrides it for scripts and tests.
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


def _pointed(data_dir: Path) -> Path | None:
    """The store named in `<data_dir>/store` (one line), else `<data_dir>/rung.db` when it exists."""
    try:
        target = (data_dir / "store").read_text().strip()
    except OSError:
        target = ""
    if target:
        return Path(target).expanduser()
    db = data_dir / "rung.db"
    return db if db.is_file() else None


def _root_home(home: Path) -> Path | None:
    return home.parent.parent if home.parent.name == "profiles" else None


def store_path() -> Path:
    """RUNG_STORE; else this home's pointer or store; else, for a profile without either, its root
    home's pointer or store; else this home's default store."""
    env = os.environ.get("RUNG_STORE")
    if env:
        return Path(env).expanduser()
    default = _default_store()
    own = _pointed(default.parent)
    if own is not None:
        return own
    root = _root_home(hermes_home())
    if root is not None:
        shared = _pointed(root / "plugin-data" / "rung")
        if shared is not None:
            return shared
    return default


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


def _profile_home(name: str) -> Path:
    root = hermes_home()
    if root.parent.name == "profiles":
        root = root.parent.parent
    return root if name == "default" else root / "profiles" / name


def hermes_profile_tools(name: str) -> list[str] | None:
    """The toolsets a Hermes profile has on the CLI (`platform_toolsets.cli` in its config), resolved
    the way Hermes resolves them. Read only; None when the profile's config cannot be read."""
    home = _profile_home(name)
    if not home.is_dir():
        return None
    cfg_path = home / "config.yaml"
    try:
        import yaml
        cfg = yaml.safe_load(cfg_path.read_text()) if cfg_path.is_file() else {}
    except Exception:
        return None
    cfg = cfg if isinstance(cfg, dict) else {}
    try:
        from hermes_cli.tools_config import _get_platform_tools
        return sorted(_get_platform_tools(cfg, "cli", include_default_mcp_servers=False))
    except Exception:
        pass
    raw = (cfg.get("platform_toolsets") or {}).get("cli") if isinstance(cfg.get("platform_toolsets"), dict) else None
    if isinstance(raw, list):
        return sorted(str(x) for x in raw if isinstance(x, str) and not x.startswith("hermes-"))
    return None


def service() -> Service:
    path = str(store_path())
    with _LOCK:
        svc = _SERVICES.get(path)
        if svc is None:
            engine = Engine(path)
            engine.tool_source = hermes_profile_tools
            if not engine.profiles():
                engine.sync_profiles(hermes_profiles())
            svc = Service(engine, hermes_bin=hermes_bin(), log_dir=Path(path).parent / "logs")
            svc.reconcile()
            _SERVICES[path] = svc
        return svc


__all__ = ["service", "store_path", "hermes_profiles", "hermes_bin", "pid_alive", "hermes_profile_tools"]
