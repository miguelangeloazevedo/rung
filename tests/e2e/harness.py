"""Drive the Rung pane in the Hermes Desktop dev build over CDP (127.0.0.1:9222).

The dev build runs against the isolated Hermes home in `~/.cache/rung-e2e/home` (outside the repo) (scripts/e2e-up.sh). Each test
points Rung at its own fresh store through Rung's store setting (`plugin-data/rung/store`), so no
test ever reads or writes the Rung data of a real profile.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
E2E = Path(os.environ.get("RUNG_E2E_DIR", Path.home() / ".cache" / "rung-e2e"))
HOME = E2E / "home"
EVIDENCE = ROOT / "evidence"
CDP = "http://127.0.0.1:9222"
WIDTH, HEIGHT = 1440, 900
THEME = ("catppuccin", "dark")

sys.path.insert(0, str(ROOT))
os.environ["PATH"] = str(ROOT / ".venv" / "bin") + os.pathsep + os.environ.get("PATH", "")
sys.path.insert(0, str(ROOT / "tests"))


def ensure_env() -> None:
    try:
        urllib.request.urlopen(CDP + "/json/version", timeout=2).read()
        return
    except Exception:
        pass
    r = subprocess.run([str(ROOT / "scripts" / "e2e-up.sh")], capture_output=True, text=True, timeout=400)
    if r.returncode != 0:
        raise RuntimeError("could not start the e2e environment:\n" + r.stdout + r.stderr)


def restart_all() -> None:
    """Stop the Desktop, its backend and every Rung runner, then start them again: a full restart."""
    for args in ([str(ROOT / "scripts" / "e2e-up.sh"), "down"], [str(ROOT / "scripts" / "e2e-up.sh")]):
        r = subprocess.run(args, capture_output=True, text=True, timeout=400)
        if r.returncode != 0:
            raise RuntimeError(" ".join(args) + " failed:\n" + r.stdout + r.stderr)


def pointer_file() -> Path:
    d = HOME / "plugin-data" / "rung"
    d.mkdir(parents=True, exist_ok=True)
    return d / "store"


def use_store(path: Path):
    """Point the running Rung backend at `path` and return an Engine on the same store for setup."""
    from rung_engine import Engine
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = Engine(str(path))
    pointer_file().write_text(str(path) + "\n")
    return engine


def release_store() -> None:
    try:
        pointer_file().unlink()
    except FileNotFoundError:
        pass


def _app_page(browser):
    for _ in range(60):
        for ctx in browser.contexts:
            for pg in ctx.pages:
                if ":5174" in pg.url and not pg.url.startswith("devtools"):
                    return pg
        time.sleep(1)
    raise RuntimeError("Desktop window not found over CDP")


def _size_window(page) -> None:
    """Lay the app out at exactly 1440x900 CSS pixels, scale 1, whatever the real window is."""
    s = page.context.new_cdp_session(page)
    s.send("Emulation.setDeviceMetricsOverride", {"width": WIDTH, "height": HEIGHT, "deviceScaleFactor": 1,
                                                  "mobile": False, "screenWidth": WIDTH, "screenHeight": HEIGHT})
    page._rung_cdp = s  # keep the session (and with it the override) alive for the test


def _prefs(page, theme=THEME) -> bool:
    """Enable the Rung desktop half and pick the comparison theme. Returns True when a reload is needed."""
    return page.evaluate("""([skin, mode]) => {
        let changed = false
        const k = 'hermes.desktop.pluginDecisions.v2'
        const d = JSON.parse(localStorage.getItem(k) || '{}')
        if (d.rung !== true) { d.rung = true; localStorage.setItem(k, JSON.stringify(d)); changed = true }
        if (localStorage.getItem('hermes-desktop-theme-v2') !== skin) { localStorage.setItem('hermes-desktop-theme-v2', skin); changed = true }
        if (localStorage.getItem('hermes-desktop-mode-v1') !== mode) { localStorage.setItem('hermes-desktop-mode-v1', mode); changed = true }
        return changed
    }""", list(theme))


@contextmanager
def desktop(theme=THEME):
    from playwright.sync_api import sync_playwright
    ensure_env()
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP)
        page = _app_page(browser)
        page.set_default_timeout(20000)
        _size_window(page)
        if _prefs(page, theme):
            reload(page)
        default_profile(page)
        yield page


def default_profile(page) -> None:
    """Every test starts on the default Hermes profile: a test that chats as another profile (UC23, UC24,
    UC26) and stops midway would otherwise leave the Desktop on it, and later chats would run as that
    profile."""
    other = "button[aria-pressed=true][aria-label]:not([aria-label^='Switch to']):not([aria-label^='Show all'])"
    names = page.evaluate("""(sel) => [...document.querySelectorAll(sel)].map(b => b.getAttribute('aria-label'))""", other)
    profiles = [n for n in names if n and (HOME / "profiles" / n).is_dir()]
    if not profiles:
        return
    back = page.locator("button[aria-label='Switch to default']")
    if back.count():
        back.first.click()
    wait_until(lambda: not page.locator(f"button[aria-label={json.dumps(profiles[0])}][aria-pressed=true]").count(),
               timeout=60, msg=f"back on the default profile from {profiles[0]}")


def reload(page) -> None:
    """Reload the Desktop window. The first load after the dev build starts compiles the app,
    which can take minutes, so a slow load is waited out rather than failed."""
    for attempt in range(3):
        try:
            page.reload(wait_until="domcontentloaded", timeout=120000)
            return
        except Exception:
            if attempt == 2:
                raise


def open_rung(page, fresh: bool = True):
    """Open Rung the way a person does: the sidebar entry. `fresh` reloads first so no state leaks."""
    if fresh:
        page.evaluate("location.hash = '#/'")
        reload(page)
    dismiss_toasts(page)
    nav = page.get_by_role("link", name="Rung", exact=True)
    if not nav.count():
        nav = page.get_by_text("Rung", exact=True).first
    nav.first.wait_for(state="visible", timeout=30000)
    nav.first.click()
    page.locator(".rung [data-rung-view]").first.wait_for(state="visible", timeout=30000)
    return page.locator(".rung [data-rung-view]").first


def dismiss_toasts(page) -> None:
    """Close Desktop notices (for example "Update ready") that would cover the pane."""
    page.evaluate("""() => {
        for (const el of document.querySelectorAll('[data-sonner-toast] button[aria-label], [role=status] button[aria-label]')) {
            if (/close|dismiss/i.test(el.getAttribute('aria-label'))) el.click()
        }
    }""")


def view(page) -> str:
    return page.locator(".rung [data-rung-view]").first.get_attribute("data-rung-view")


def wait_view(page, name: str, timeout: float = 20):
    end = time.time() + timeout
    while time.time() < end:
        try:
            if view(page) == name:
                return
        except Exception:
            pass
        time.sleep(0.2)
    raise AssertionError(f"view {name!r} not shown (now {view(page)!r})")


def main_area(page):
    return page.locator(".rung [data-testid=main]").first


def click_text(page, text: str, scope=None, exact: bool = True):
    loc = (scope or page.locator(".rung").first).get_by_text(text, exact=exact).first
    loc.click()
    return loc


def button(page, name: str, scope=None):
    return (scope or page.locator(".rung").first).get_by_role("button", name=name, exact=True).first


def needs_you_counts(page) -> tuple[int, int, int]:
    chip = page.locator("[data-testid=rung-status-chip]").first.inner_text()
    tile = page.locator(".rung [data-testid=tile-needs-you-value]").first.inner_text()
    items = page.locator(".rung [data-testid=needs-you-item]").count()
    return int(chip.split()[1]), int(tile), items


def agreed_needs_you(page, timeout: float = 5) -> tuple[int, int, int]:
    """The chip, the tile and the list once the pane has settled: they must agree within a moment."""
    wait_until(lambda: len(set(needs_you_counts(page))) == 1, timeout=timeout,
               msg="chip, tile and Needs you list agree")
    return needs_you_counts(page)


def wait_until(fn, timeout: float = 20, every: float = 0.25, msg: str = "condition"):
    end = time.time() + timeout
    last = None
    while time.time() < end:
        try:
            last = fn()
            if last:
                return last
        except Exception as exc:  # retry through transient DOM states
            last = exc
        time.sleep(every)
    raise AssertionError(f"timed out waiting for {msg} (last: {last!r})")


def evidence(page, uc: int) -> Path:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    out = EVIDENCE / f"uc{uc:02d}.png"
    page.screenshot(path=str(out))
    return out


def copy_fixture(name: str, dest: Path) -> Path:
    src = ROOT / "tests" / "fixtures" / name
    target = dest / name
    shutil.copytree(src, target, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    return target


def configure_stubs(engine, folder: Path, delay: float = 0.6, worker_delay: float = 0.4) -> None:
    """Deterministic drafting and worker stubs, chosen through Rung's own settings."""
    engine.set_setting("drafting", {"kind": "stub", "profile": "", "stub_file": str(folder / ".rung-stub" / "drafts.json"),
                                    "delay": delay})
    engine.set_setting("worker", {"kind": "stub", "stub_dir": str(folder / ".rung-stub"),
                                  "max_turns": 30, "delay": worker_delay})


def standard_profiles(engine) -> None:
    engine.save_profiles([
        {"name": "coder", "labels": ["python", "cli", "tests"], "cost": 2, "max_runs": 2, "enabled": True},
        {"name": "reviewer", "labels": ["review"], "cost": 3, "max_runs": 1, "enabled": True},
        {"name": "writer", "labels": ["docs", "specs"], "cost": 1, "max_runs": 1, "enabled": True},
        {"name": "researcher", "labels": ["research"], "cost": 1, "max_runs": 1, "enabled": False},
    ])


def stored(path: Path, sql: str, args=()):
    import sqlite3
    c = sqlite3.connect(str(path))
    c.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in c.execute(sql, args)]
    finally:
        c.close()


def dump(obj) -> str:
    return json.dumps(obj, indent=1, default=str)


def node(engine, project: str, rid: str) -> dict:
    """A rung as the tree reports it: with its result, coverage and released state."""
    stack = list(engine.tree(project))
    while stack:
        n = stack.pop()
        if n["id"] == rid:
            return n
        stack.extend(n.get("children", []))
    raise KeyError(rid)
