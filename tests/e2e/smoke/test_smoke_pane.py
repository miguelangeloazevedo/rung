"""Smoke checks after the twelve use cases: restart persistence, themes, empty states, cancel, gateway
restart mid run. They drive the real pane in the Desktop dev build against the isolated e2e home and
throwaway stores, like the use-case tests. Run: .venv/bin/python -m pytest -q tests/e2e/smoke"""

import json
import os
import subprocess
import time
from pathlib import Path

import pytest

import harness as H
from support import seed

SHOTS = Path(os.environ.get("RUNG_SMOKE_SHOTS", "/tmp/rung-smoke"))
HERMES_BIN = os.path.expanduser("~/.hermes/hermes-agent/venv/bin/hermes")
THEMES = [("catppuccin", "dark"), ("catppuccin", "light"), ("github", "light"), ("github", "dark"),
          ("solarized", "dark"), ("everforest", "light"), ("mono", "dark"), ("nous", "dark")]


def shot(page, name):
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS / f"{name}.png"))


def isolated(*args, timeout=180):
    env = dict(os.environ, HERMES_HOME=str(H.HOME))
    env.pop("PYTHONPATH", None)
    return subprocess.run([HERMES_BIN, *args], capture_output=True, text=True, env=env, timeout=timeout)


def test_data_survives_restart(rung, csvtidy):
    seed.seed_csvtidy(rung.engine, csvtidy)
    rung.engine.open_project("csvtidy")
    with H.desktop() as page:
        H.open_rung(page)
        H.wait_view(page, "home")
        before = H.needs_you_counts(page), page.locator(".rung [data-testid=tile-covered-value]").inner_text()
    rung.engine.close()
    # Restart the gateway and the Desktop dev build of the isolated home.
    subprocess.run([str(H.ROOT / "scripts" / "e2e-up.sh"), "down"], check=True, capture_output=True, timeout=120)
    up = subprocess.run([str(H.ROOT / "scripts" / "e2e-up.sh")], capture_output=True, text=True, timeout=600)
    assert "e2e environment up" in up.stdout, up.stdout + up.stderr
    with H.desktop() as page:
        H.open_rung(page)
        H.wait_view(page, "home")
        assert page.locator(".rung [data-testid=project-name]").inner_text() == "csvtidy"
        after = H.needs_you_counts(page), page.locator(".rung [data-testid=tile-covered-value]").inner_text()
        assert after == before
        shot(page, "restart-home")


@pytest.mark.parametrize("theme", THEMES, ids=lambda t: "-".join(t))
def test_theme_status_colours_distinct(rung, csvtidy, theme):
    seed.seed_demo(rung.engine, csvtidy)
    with H.desktop(theme=theme) as page:
        H.open_rung(page)
        H.wait_view(page, "home")
        colours = page.evaluate("""() => {
            const root = document.querySelector('.rung')
            const out = {}
            for (const t of ['pass', 'fail', 'stale', 'needs', 'dim']) {
                const s = document.createElement('span'); s.className = 'text-' + t; s.textContent = 'x'
                root.appendChild(s); out[t] = getComputedStyle(s).color; s.remove()
            }
            out.bg = getComputedStyle(root).backgroundColor
            return out
        }""")
        shot(page, "theme-" + "-".join(theme))
    rgb = {k: [float(x) for x in v[v.index("(") + 1:v.index(")")].split(",")[:3]] for k, v in colours.items()}

    def dist(a, b):
        return sum((x - y) ** 2 for x, y in zip(rgb[a], rgb[b])) ** 0.5

    names = ["pass", "fail", "stale", "needs", "dim"]
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            assert dist(a, b) > 40, f"{theme}: {a} {colours[a]} too close to {b} {colours[b]}"
    p, f, s = rgb["pass"], rgb["fail"], rgb["stale"]
    assert p[1] > p[0] and p[1] > p[2] * 0.8, f"{theme}: pass is not green {colours['pass']}"
    assert f[0] > f[1] and f[0] > f[2], f"{theme}: fail is not red {colours['fail']}"
    assert s[2] > s[1] and s[0] > s[1] * 0.8, f"{theme}: stale is not violet {colours['stale']}"


def test_empty_states(rung, page, tmp_path):
    # No project at all: the start screen, then (dismissed) the new-project form.
    H.open_rung(page)
    H.wait_view(page, "start")
    shot(page, "empty-no-project")
    rung.engine.set_onboarding(start_dismissed=True)
    H.open_rung(page)
    H.wait_view(page, "project-new")
    # A project with nothing in it.
    folder = H.copy_fixture("csvtidy", tmp_path / "w")
    rung.engine.create_project("csvtidy", str(folder), "pytest", ["coder"])
    rung.engine.open_project("csvtidy")
    H.open_rung(page)
    H.wait_view(page, "home")
    text = page.locator(".rung").first.inner_text()
    assert "No needs yet" in text and "Write the first need" in text  # the prototype's project-empty copy
    assert H.needs_you_counts(page) == (0, 0, 0)
    for tile in ("tile-covered-value", "tile-stale-value", "tile-failing-value"):
        assert page.locator(f".rung [data-testid={tile}]").inner_text() in ("0", "0 of 0")
    shot(page, "empty-project")


def _start_slow_run(rung, csvtidy, page, delay):
    e = rung.engine
    seed.seed_merge(e, csvtidy, upto="develop")
    H.configure_stubs(e, csvtidy, worker_delay=delay)
    H.open_rung(page)
    H.wait_view(page, "home")
    page.evaluate("window.__rungNavigate('build', {need: 'N-2', step: 'develop'})")
    row = page.locator(".rung [data-testid=develop-table] [data-spec=\"S-4.1\"]")
    row.wait_for()
    H.button(page, "Send", row).click()
    H.wait_view(page, "run")
    run = e.runs("csvtidy", "S-4.1")[0]
    H.wait_until(lambda: e.run(run["id"])["status"] == "running", timeout=20, msg="run running")
    return e, run["id"]


def _alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def test_cancel_running_loop(rung, csvtidy, page):
    e, run_id = _start_slow_run(rung, csvtidy, page, delay=30.0)
    pid = e.run(run_id)["pid"]
    assert pid and _alive(pid)
    page.locator(".rung [data-testid=stop]").click()
    H.wait_until(lambda: e.run(run_id)["status"] == "cancelled", timeout=30, msg="run cancelled")
    H.wait_until(lambda: not _alive(pid), timeout=30, msg="runner process gone")
    H.wait_until(lambda: "Cancelled" in page.locator(".rung [data-testid=run]").text_content(), timeout=20,
                 msg="pane shows Cancelled")
    # The cancelled attempt left no passing execution behind.
    assert all(x["status"] != "pass" for x in e.executions("csvtidy", "T-4.1a"))
    shot(page, "cancelled-run")


def test_gateway_restart_mid_run(rung, csvtidy, page):
    e, run_id = _start_slow_run(rung, csvtidy, page, delay=6.0)
    pid = e.run(run_id)["pid"]
    r = isolated("gateway", "restart", timeout=240)
    assert r.returncode == 0, r.stdout + r.stderr
    # The supervised run is its own process: it carries on through the restart.
    assert _alive(pid) or e.run(run_id)["status"] == "passed"
    H.wait_until(lambda: e.run(run_id)["status"] == "passed", timeout=120, msg="run finished after the restart")
    assert [a["status"] for a in e.run(run_id)["attempts"]] == ["fail", "pass"]
    # The pane recovers and shows the result.
    H.open_rung(page, fresh=False)
    page.evaluate(f"window.__rungNavigate('run', {json.dumps({'run': run_id})})")
    H.wait_until(lambda: "Finished in" in page.locator(".rung [data-testid=run-time]").inner_text(), timeout=60,
                 msg="pane shows the finished run")
    shot(page, "gateway-restart-run")
