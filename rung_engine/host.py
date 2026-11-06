"""Where Rung keeps its store inside Hermes, and the one Service per process.

The store follows the active Hermes home (`<home>/plugin-data/rung/rung.db`), so every home can
have its own ladder. A profile with no Rung store of its own is a carrier of its root home's ladder
and uses that one, so a chat or a develop run as `coder` claims and checks the work it was sent
(Round 8 of decisions.md). `RUNG_STORE` overrides it for scripts and tests.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
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


def _read_config(path: Path) -> dict:
    """A profile's config.yaml as written, read through Hermes's public config module (Hermes 0.23
    ships no PyYAML); PyYAML only where that reader is missing."""
    try:
        from hermes_cli.config import read_user_config_raw
        data = read_user_config_raw(path)
    except ImportError:
        import yaml
        data = yaml.safe_load(path.read_text())
    return data if isinstance(data, dict) else {}


# `hermes tools list` rows: "  ✓ enabled  terminal  ..." (the key is the word after the state).
_TOOL_ROW = re.compile(r"^\s*✓\s+enabled\s+([a-z0-9_][a-z0-9_.-]*)\b")
_CLI_TOOLS: dict[tuple, list[str] | None] = {}


def _cli_tools(name: str, cfg_path: Path) -> list[str] | None:
    """The profile's enabled CLI toolsets as `hermes -p <name> tools list` resolves them (defaults
    included), cached per config version. None when the command cannot answer."""
    try:
        st = cfg_path.stat()
        key = (name, str(cfg_path), st.st_mtime_ns, st.st_size)
    except OSError:
        key = (name, str(cfg_path), None, None)
    if key in _CLI_TOOLS:
        return _CLI_TOOLS[key]
    try:
        out = subprocess.run([hermes_bin(), "-p", name, "tools", "list", "--platform", "cli"],
                             capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
        names = [m.group(1) for line in out.stdout.splitlines() if (m := _TOOL_ROW.match(line))]
        got = sorted(set(names)) if out.returncode == 0 and names else None
    except (OSError, subprocess.SubprocessError):
        got = None
    _CLI_TOOLS[key] = got
    return got


def _tool_plan(name: str) -> tuple[list[str] | None, Path | None]:
    """(explicit tools, None) when the profile's config lists plain CLI toolsets; (None, config path)
    when only Hermes can resolve them (defaults, composite toolsets); (None, None) for no profile."""
    home = _profile_home(name)
    if not home.is_dir():
        return None, None
    cfg_path = home / "config.yaml"
    try:
        cfg = _read_config(cfg_path) if cfg_path.is_file() else {}
    except Exception:
        cfg = {}  # unreadable here: Hermes itself still answers
    pts = cfg.get("platform_toolsets")
    raw = pts.get("cli") if isinstance(pts, dict) else None
    if isinstance(raw, list) and raw and all(isinstance(x, str) and x and not x.startswith("hermes-") for x in raw):
        return sorted(set(raw)), None
    return None, cfg_path


def _explicit_tools(name: str) -> list[str] | None:
    """A profile's tools when its config states them; never starts hermes."""
    return _tool_plan(name)[0]


def hermes_profile_tools(name: str) -> list[str] | None:
    """The toolsets a Hermes profile has on the CLI. An explicit `platform_toolsets.cli` list of plain
    toolset names is read from the profile's config; otherwise (Hermes defaults, composite toolsets)
    Hermes resolves them through `hermes tools list`. Read only; None when neither can answer."""
    explicit, cfg_path = _tool_plan(name)
    if explicit is not None or cfg_path is None:
        return explicit
    return _cli_tools(name, cfg_path)


def _fill_default_tools(engine: Engine, names: list[str]) -> threading.Thread | None:
    """Resolve, off the request path, the tools of new profiles whose config does not list them: each
    `hermes tools list` takes seconds, and a first open must not wait for one per profile. A profile
    someone gave tools in the meantime keeps them."""
    todo = [(n, p) for n in names for e, p in [_tool_plan(n)] if e is None and p is not None]
    if not todo:
        return None

    def work():
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4) as pool:
            for name, got in zip([n for n, _ in todo], pool.map(lambda np: _cli_tools(*np), todo)):
                if got:
                    try:
                        engine.fill_profile_tools(name, got)
                    except Exception:
                        pass

    t = threading.Thread(target=work, name="rung-profile-tools", daemon=True)
    t.start()
    return t


def service() -> Service:
    path = str(store_path())
    with _LOCK:
        svc = _SERVICES.get(path)
        if svc is None:
            engine = Engine(path)
            engine.tool_source = _explicit_tools
            if not engine.profiles():
                names = hermes_profiles()
                engine.sync_profiles(names)
                _fill_default_tools(engine, names)
            svc = Service(engine, hermes_bin=hermes_bin(), log_dir=Path(path).parent / "logs")
            svc.reconcile()
            _SERVICES[path] = svc
        return svc


__all__ = ["service", "store_path", "hermes_profiles", "hermes_bin", "pid_alive", "hermes_profile_tools"]
