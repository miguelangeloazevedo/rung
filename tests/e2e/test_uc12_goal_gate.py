"""UC12 Rung as a goal gate: `hermes rung check` exits 0 only when a specification is released,
and works as a `/goal gate add` gate in a Hermes session."""

import json
import os
import subprocess
import urllib.request

import harness as H
from support import seed

R2_NEW = "Normalise every date to ISO 8601 with a time zone"
GATE = "hermes rung check S-2.1"


HERMES_BIN = os.path.expanduser("~/.hermes/hermes-agent/venv/bin/hermes")
STUB_LOG = "http://127.0.0.1:18765/v1/log"


def hermes(*args):
    """The real `hermes` CLI against the isolated test home (never a real profile)."""
    env = dict(os.environ, HERMES_HOME=str(H.HOME))
    env.pop("PYTHONPATH", None)
    return subprocess.run([HERMES_BIN, "rung", *args], capture_output=True, text=True, env=env, timeout=120)


def model_calls() -> int:
    with urllib.request.urlopen(STUB_LOG, timeout=5) as r:
        return len(json.load(r))


def chat(page, text):
    box = page.locator("[contenteditable=true][aria-label=Message]").first
    box.wait_for(timeout=30000)
    box.click()
    page.keyboard.type(text)
    page.keyboard.press("Enter")


def transcript(page) -> str:
    """Text of the session pane that holds the composer (the chat transcript)."""
    return page.evaluate("""() => {
        const box = document.querySelector('[contenteditable=true][aria-label=Message]');
        const pane = box && box.closest('.isolate.h-full');
        return pane ? pane.innerText : document.body.innerText;
    }""")


def says(page, needle, before: int, timeout=90):
    """Wait until the transcript holds more occurrences of `needle` than `before`."""
    H.wait_until(lambda: transcript(page).lower().count(needle.lower()) > before, timeout=timeout,
                 msg=f"chat shows {needle!r}")


def count(page, needle) -> int:
    return transcript(page).lower().count(needle.lower())


def test_goal_gate(rung, csvtidy, page):
    e = rung.engine
    seed.seed_csvtidy(e, csvtidy)
    e.open_project("csvtidy")
    assert e.check("csvtidy", "S-2.1")["ok"]

    # 1. Stale: non-zero, and it names the blocking rung.
    e.edit("csvtidy", "R-2", text=R2_NEW, approve=True)
    calls0 = model_calls()
    r = hermes("check", "S-2.1")
    assert r.returncode != 0
    assert "S-2.1" in r.stdout and "stale" in r.stdout.lower(), r.stdout
    # Approved as still valid, but its test has not passed since the change: still non-zero, names T-2.1a.
    e.approve("csvtidy", "S-2.1")
    r = hermes("check", "S-2.1")
    assert r.returncode != 0 and "T-2.1a" in r.stdout, r.stdout
    # 3. --all is non-zero while any approved specification fails the check.
    r = hermes("check", "--all")
    assert r.returncode != 0 and "S-2.1" in r.stdout, r.stdout
    # 4. No model call happened during the checks.
    assert model_calls() == calls0

    # 5. In a Hermes session: set a goal, add the check as a gate; the gate fails.
    H.open_rung(page)
    H.wait_view(page, "home")
    page.evaluate("location.hash = '#/'")
    H.dismiss_toasts(page)
    page.get_by_text("New session", exact=True).first.click()
    H.wait_until(lambda: count(page, "Goal set") == 0, timeout=20, msg="a fresh session")
    n = count(page, "Goal set")
    # The stub model takes a few seconds over a goal turn that says "slowly"; the gate is added meanwhile.
    chat(page, "/goal Release S-2.1 in Rung, slowly")
    says(page, "Goal set", n)
    session_route = page.evaluate("location.hash")
    n = count(page, GATE)
    chat(page, f"/goal gate add {GATE}")
    says(page, GATE, n)
    # The turn ends, the gate runs and fails: the goal keeps going with the gate output.
    H.wait_until(lambda: count(page, "a quality gate failed") > 0 or count(page, "failing") > 0, timeout=60,
                 msg="the gate fails in the session")
    n = count(page, "failing")
    chat(page, "/goal gate list")
    says(page, "failing (exit 1", count(page, "failing (exit 1"))

    # 2. After the tests pass, it exits 0, and so does --all once every specification passes.
    H.open_rung(page, fresh=False)
    page.locator(".rung [data-testid=rail]").get_by_text("T-2.1a", exact=False).first.click()
    H.wait_view(page, "rung")
    H.button(page, "Run tests").click()
    H.wait_until(lambda: e.check("csvtidy", "S-2.1")["ok"], timeout=60, msg="T-2.1a passes")
    r = hermes("check", "S-2.1")
    assert r.returncode == 0, r.stdout
    assert e.check_all("csvtidy")["ok"]
    r = hermes("check", "--all")
    assert r.returncode == 0, r.stdout

    # The gate passes at the next turn boundary and the goal is done.
    page.evaluate(f"location.hash = {json.dumps(session_route)}")
    page.locator("[contenteditable=true][aria-label=Message]").first.wait_for(timeout=30000)
    # After three failures Hermes pauses the goal; resume it now the tests pass.
    H.wait_until(lambda: count(page, "Goal paused") > 0 or count(page, "attempt 3/3") > 0, timeout=60, msg="goal paused")
    H.wait_until(lambda: count(page, "Goal paused") > 0, timeout=60, msg="goal paused")
    chat(page, "/goal resume")
    done0 = 0
    H.wait_until(lambda: count(page, "Goal achieved") + count(page, "Goal done") > done0, timeout=90,
                 msg="the goal is done once the gate passes")
    n = count(page, "passing")
    chat(page, "/goal gate list")
    says(page, "passing", n)
    H.evidence(page, 12)
