"""UC33 First install: the start screen (FST-01), its cross and Escape close Rung and create nothing, New
project's Back returns to it (FST-02, NAV-12), a first green test from visible controls only (FST-03),
every empty list names what is missing with one action (FST-04), and each control the walk uses is named
the same wherever it shows (FST-05)."""

import time
import os
import re
import subprocess
from pathlib import Path

import harness as H

NEED = "Tidy a CSV export so it imports cleanly"
REQ = "Import the csvtidy package without errors"
SPEC = "Expose csvtidy as an importable package"
CMD = "python3 -c 'import csvtidy'"

# The host's native folder dialog cannot be driven over CDP and its bridge is frozen, so the walk stands in for
# ctx.os.pickOpenPath (the public picker Rung calls) and checks what Rung asked of it.
STAND_IN = """path => { window.__picks = []
  window.__rungOs({ pickOpenPath: async o => { window.__picks.push(o); return path } }) }"""

BUTTONS_JS = """() => [...document.querySelectorAll('.rung button')]
  .filter(b => b.offsetParent !== null)
  .map(b => ({ testid: b.getAttribute('data-testid') || '', text: (b.innerText || '').trim(),
               name: b.getAttribute('aria-label') || '' }))"""


class Walk:
    """Every control the walk clicks, every button seen on every view, and every empty state met."""

    def __init__(self, page):
        self.page = page
        self.used = []
        self.seen = []
        self.empties = []

    def look(self):
        view = H.view(self.page)
        for b in self.page.evaluate(BUTTONS_JS):
            self.seen.append((view, b))

    def click(self, label, scope=None):
        self.look()
        btn = H.button(self.page, label, scope)
        btn.wait_for(timeout=20000)
        self.used.append((H.view(self.page), label, btn.get_attribute("data-testid") or ""))
        btn.click()

    def empty(self, loc, label, action):
        """An empty list or section: the label naming what is missing, and exactly one action."""
        loc.wait_for(timeout=20000)
        text = loc.inner_text()
        assert label in text, text
        buttons = loc.locator("button")
        names = [buttons.nth(i).inner_text().strip() for i in range(buttons.count())]
        assert names == [action], (label, names)
        self.empties.append((H.view(self.page), label, action))


def stable_hash(page, quiet=1.0, cap=8.0):
    """The Hermes route once it has not changed for `quiet` seconds."""
    t0 = time.time(); last = page.evaluate("location.hash"); since = time.time()
    while time.time() - t0 < cap:
        page.wait_for_timeout(200)
        now = page.evaluate("location.hash")
        if now != last:
            last, since = now, time.time()
        elif time.time() - since >= quiet:
            break
    return last


def stored_projects(rung):
    return H.stored(rung.store, "SELECT COUNT(*) AS n FROM projects")[0]["n"]


def test_fst01_fst02_fst03_fst04_fst05_nav12_first_install(rung, page):
    e = rung.engine
    folder = H.copy_fixture("csvtidy", rung.work)
    H.configure_stubs(e, folder)
    w = Walk(page)

    # 1. A fresh store opens on the start screen; the cross returns to the chat home and creates nothing.
    page.evaluate("location.hash = '#/'")
    H.reload(page)
    H.default_profile(page)
    page.evaluate("location.hash = '#/'")
    # The Desktop may restore the profile's last chat after the switch: the chat the test came from is the one
    # showing once the hash stops moving.
    came = stable_hash(page)
    H.open_rung(page, fresh=False)
    H.wait_view(page, "start")
    start = page.locator(".rung [data-testid=start]")
    assert H.button(page, "Try the sample project", start).is_visible()
    assert H.button(page, "New project", start).is_visible()
    cross = page.locator(".rung [data-testid=start-dismiss]")
    assert cross.is_visible()
    cross.click()
    H.wait_until(lambda: page.evaluate("location.hash") == came, msg=lambda: f"back on {came} (now {page.evaluate('location.hash')})")
    assert page.locator(".rung [data-rung-view]").count() == 0
    assert stored_projects(rung) == 0
    H.open_rung(page, fresh=False)
    H.wait_view(page, "start")
    # Escape does the same as the cross.
    page.keyboard.press("Escape")
    H.wait_until(lambda: page.evaluate("location.hash") == came, msg=lambda: f"Escape closes Rung (now {page.evaluate('location.hash')})")
    assert stored_projects(rung) == 0
    H.open_rung(page, fresh=False)
    H.wait_view(page, "start")
    # New project, then Back: the start screen; with text typed, Back asks first.
    w.click("New project", start)
    H.wait_view(page, "project-new")
    w.click("Back")
    H.wait_view(page, "start")
    w.click("New project", page.locator(".rung [data-testid=start]"))
    H.wait_view(page, "project-new")
    form = page.locator(".rung [data-testid=new-project]")
    form.locator("input[name=name]").fill("typed")
    w.click("Back")
    leave = page.locator(".rung [data-testid=leave-dialog]")
    leave.wait_for(timeout=10000)
    H.button(page, "Keep editing", leave).click()
    assert H.view(page) == "project-new" and form.locator("input[name=name]").input_value() == "typed"
    w.click("Back")
    H.button(page, "Discard", page.locator(".rung [data-testid=leave-dialog]")).click()
    H.wait_view(page, "start")
    assert stored_projects(rung) == 0

    # 2. Visible controls only: New project, a need, one requirement, its specification, a command test, run.
    page.evaluate(STAND_IN, str(folder))
    w.click("New project", page.locator(".rung [data-testid=start]"))
    H.wait_view(page, "project-new")
    form = page.locator(".rung [data-testid=new-project]")
    w.click("Choose folder", form)
    H.wait_until(lambda: form.locator("input[name=folder]").input_value() == str(folder), msg="Choose fills the folder")
    picks = page.evaluate("window.__picks")
    assert len(picks) == 1 and picks[0]["directories"] is True, picks
    page.evaluate("window.__rungOs(null)")
    H.wait_until(lambda: form.locator("input[name=name]").input_value() == "csvtidy", msg="name filled in")
    form.locator("input[name=test_command]").fill("python3 -m unittest -q")
    w.click("Create project", form)
    H.wait_view(page, "home")
    w.empty(page.locator(".rung [data-testid=empty-project]"), "No needs yet", "Write the first need")
    w.click("Write the first need", page.locator(".rung [data-testid=empty-project]"))
    H.wait_view(page, "need-new")
    page.locator(".rung textarea[name=need]").fill(NEED)
    sugg = page.locator(".rung [data-testid=suggested] [data-suggestion]")
    try:
        H.wait_until(lambda: sugg.count() > 0, timeout=4, msg="suggestions")
    except AssertionError:
        pass
    for i in range(sugg.count()):
        w.click("Dismiss", sugg.nth(i))
    w.click("Create need")
    H.wait_view(page, "build")
    reqs = page.locator(".rung [data-testid=requirements]")
    reqs.wait_for(timeout=20000)
    w.empty(page.locator(".rung [data-testid=requirements] [data-testid=empty-state]"), "No requirements", "New requirement")
    w.click("New requirement", reqs)
    H.wait_view(page, "req-new")
    page.locator(".rung input[name=req-text]").fill(REQ)
    w.click("Approve")
    H.wait_view(page, "build")
    H.wait_until(lambda: page.locator(".rung [data-testid=requirements] [data-req]").count() == 1, msg="one requirement")
    H.wait_until(lambda: H.button(page, "Approve all").is_enabled() or H.button(page, "Next").is_enabled(),
                 msg=f"Approve all or Next: {e.flow('csvtidy', 'N-1')['steps']['requirements']}")
    w.click("Approve all" if H.button(page, "Approve all").is_enabled() else "Next")
    step = page.locator(".rung [data-testid=spec-step]")
    step.wait_for(timeout=20000)
    page.locator(".rung [data-req=R-1] [data-testid=authoring]").get_by_role("radio", name="I write, AI supports").click()
    w.click("Write", page.locator(".rung [data-req=R-1]"))
    H.wait_view(page, "spec-edit")
    page.locator(".rung input[name=spec-text]").fill(SPEC)
    w.click("Save and approve")
    H.wait_view(page, "build")
    H.wait_until(lambda: H.button(page, "Approve drafted").is_enabled() or H.button(page, "Next").is_enabled(),
                 msg=f"Approve drafted or Next: {e.flow('csvtidy', 'N-1')['steps']['specifications']}")
    w.click("Approve drafted" if H.button(page, "Approve drafted").is_enabled() else "Next")
    tstep = page.locator(".rung [data-testid=test-step]")
    tstep.wait_for(timeout=20000)
    spec_row = page.locator(".rung [data-spec=\"S-1.1\"]")
    spec_row.wait_for(timeout=20000)
    page.wait_for_timeout(1500)  # the drafting stub may propose a test
    proposed = spec_row.locator("[data-test]")
    if proposed.count():
        tid = proposed.first.get_attribute("data-test")
        w.click("Edit", proposed.first)
    else:
        tid = "T-1.1a"
        w.empty(spec_row.locator("[data-testid=empty-state]"), "No tests", "Add test")
        w.click("Add test", spec_row)
    H.wait_view(page, "test-edit")
    page.locator(".rung [data-testid=test-type]").get_by_role("radio", name="Command").click()
    page.locator(".rung input[name=command]").fill(CMD)
    w.click("Save test")
    H.wait_view(page, "build")
    row = page.locator(f".rung [data-test=\"{tid}\"]")
    row.wait_for(timeout=20000)
    for i in range(page.locator(".rung [data-testid=test-step] [data-test][data-status=draft]").count()):
        w.click("Accept", page.locator(".rung [data-testid=test-step] [data-test][data-status=draft]").first)
    H.wait_until(lambda: H.button(page, "Approve tests").is_enabled(), msg="Approve tests enabled")
    w.click("Approve tests")
    page.locator(".rung [data-testid=develop-table]").wait_for(timeout=20000)
    page.locator(".rung [data-testid=rail]").get_by_text(tid, exact=False).first.click()
    H.wait_view(page, "rung")
    w.empty(page.locator(".rung [data-testid=executions] [data-testid=empty-state]"), "No executions yet", "Run tests")
    w.click("Run tests")
    H.wait_view(page, "exec")
    ex = page.locator(".rung [data-testid=execution]")
    H.wait_until(lambda: ex.get_attribute("data-exec-status") == "pass", timeout=60,
                 msg=lambda: f"the test passes: {H.main_area(page).inner_text()[:300]}")
    page.locator(".rung [data-testid=project-name]").first.click()
    H.wait_view(page, "projects")
    w.look()
    page.locator(".rung [data-testid=open-project]").first.click()
    H.wait_view(page, "home")
    fg = page.locator(".rung [data-testid=first-green]")
    fg.wait_for(timeout=20000)
    H.wait_until(lambda: fg.locator("li[data-item=first_green]").get_attribute("data-done") == "1",
                 msg="First green test ticked")
    w.look()
    H.evidence(page, 33)

    # 3. A project search that matches nothing offers Clear search, which restores the list.
    page.locator(".rung [data-testid=project-name]").first.click()
    H.wait_view(page, "projects")
    page.locator(".rung input[name=search]").fill("zzz")
    side = page.locator(".rung [data-testid=project-list]")
    H.wait_until(lambda: side.locator("[data-testid=empty]").count() == 1, msg="no matching projects")
    w.empty(side.locator("[data-testid=empty]").locator(".."), "No matching projects", "Clear search")
    w.click("Clear search", side)
    H.wait_until(lambda: side.locator("[data-testid=project-row]").count() == 1, msg="the list is back")
    w.look()
    assert {x[1] for x in w.empties} >= {"No needs yet", "No requirements", "No matching projects"}, w.empties

    # Each control the walk used is named the same on every view that shows it.
    labels = {}
    for view, b in w.seen:
        if b["testid"]:
            labels.setdefault(b["testid"], set()).add(b["text"])
    for view, label, testid in w.used:
        if testid and testid in labels:
            assert labels[testid] == {label}, (testid, labels[testid])


def test_fst03_choose_folder_on_both_project_forms(rung, page):
    """Choose asks the host for a folder on New project and Project settings; cancel changes nothing, a failed
    pick says so, and without a host picker there is no Choose button (never a control that does nothing)."""
    e = rung.engine
    folder = H.copy_fixture("csvtidy", rung.work)
    other = H.copy_fixture("csvtidy", rung.work / "moved")
    e.create_project("csvtidy", str(folder), "python3 -m unittest -q", ["coder"])
    e.open_project("csvtidy")
    H.open_rung(page)
    try:
        # Project settings: Choose fills the folder; cancel ('' from the host) leaves it.
        page.evaluate(STAND_IN, str(other))
        page.evaluate("window.__rungNavigate('project-settings')")
        H.wait_view(page, "project-settings")
        sec = page.locator(".rung [data-testid=project-settings]")
        H.button(page, "Choose folder", sec).click()
        H.wait_until(lambda: sec.locator("input[name=folder]").input_value() == str(other), msg="settings folder")
        assert page.evaluate("window.__picks")[0]["directories"] is True
        page.evaluate(STAND_IN, "")
        H.button(page, "Choose folder", sec).click()
        page.wait_for_timeout(300)
        assert sec.locator("input[name=folder]").input_value() == str(other)
        H.button(page, "Save", page.locator(".rung [data-rung-view]")).click()
        H.wait_until(lambda: e.project("csvtidy")["folder"] == str(other), msg="saved")
        # New project: a picker that fails names the failure under the field.
        page.evaluate("window.__rungOs({ pickOpenPath: async () => { throw new Error('picker failed') } })")
        page.evaluate("window.__rungNavigate('project-new')")
        H.wait_view(page, "project-new")
        form = page.locator(".rung [data-testid=new-project]")
        H.button(page, "Choose folder", form).click()
        H.wait_until(lambda: "picker failed" in form.locator("[data-testid=choose-error]").inner_text(), msg="failure shown")
        # No picker on this host: no Choose button, the typed path still works.
        page.evaluate("window.__rungOs({})")
        page.evaluate("window.__rungNavigate('home')")
        page.evaluate("window.__rungNavigate('project-new')")
        H.wait_view(page, "project-new")
        form = page.locator(".rung [data-testid=new-project]")
        form.locator("input[name=folder]").wait_for()
        assert form.locator("[data-testid=choose-folder]").count() == 0
    finally:
        page.evaluate("window.__rungOs(null)")
    # The real host: Choose shows because this Hermes has ctx.os.pickOpenPath.
    page.evaluate("window.__rungNavigate('home')")
    page.evaluate("window.__rungNavigate('project-new')")
    H.wait_view(page, "project-new")
    assert page.locator(".rung [data-testid=new-project] [data-testid=choose-folder]").count() == 1


def _hermes_src() -> Path:
    return Path(os.environ.get("HERMES_AGENT_SRC", str(Path.home() / ".hermes/hermes-agent")))


def test_every_host_call_exists_in_the_plugin_sdk():
    """Every ctx, ctx.os and host member the pane calls is declared by the Desktop plugin SDK, at the oldest
    supported release (requires_hermes) and at the source the e2e Desktop runs. A call the SDK lacks would
    fail silently in a real Hermes while a test that types around it passes."""
    root = Path(__file__).resolve().parents[2]
    src = "\n".join(p.read_text() for p in sorted((root / "desktop/src").glob("*.js")))
    used = {
        "ctx": set(re.findall(r"\b(?:ctx|CTX)\.(\w+)", src)) - {"os"},
        "os": set(re.findall(r"\bos\.(\w+)", src)),
        "host": set(re.findall(r"\bhost\.(\w+)", src)),
    }
    assert used["host"] and used["ctx"], used
    floor = re.search(r'requires_hermes:\s*"?>=\s*([0-9.]+)', (root / "plugin.yaml").read_text()).group(1)
    ha = _hermes_src()
    for ref in (f"v{floor}", None):
        def show(path):
            if ref is None:
                return (ha / path).read_text()
            return subprocess.run(["git", "-C", str(ha), "show", f"{ref}:{path}"], capture_output=True, text=True,
                                  check=True).stdout
        plugin = show("apps/desktop/src/contrib/plugin.ts")
        sdk = show("apps/desktop/src/sdk/index.ts")

        def members(text, start):
            body = text[text.index(start):]
            body = body[:body.index("\n}\n")]
            return set(re.findall(r"^\s{2}(?:readonly\s+)?(\w+)\??\s*[:(]", body, re.M))
        have = {"ctx": members(plugin, "export interface PluginContext"),
                "os": members(plugin, "export interface PluginOs"),
                "host": members(sdk, "export const host = {")}
        for kind, names in used.items():
            missing = names - have[kind]
            assert not missing, f"{ref or 'working tree'}: {kind} lacks {sorted(missing)}"
