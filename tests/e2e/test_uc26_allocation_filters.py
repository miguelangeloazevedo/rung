"""UC26 Allocation filters: profile tools (pre-filled from Hermes), `At once`, required tools,
independence and human only as hard filters, each exclusion named in Develop, Settings, the REST
API and `rung_claim`."""

import time

import pytest

import chatting as C
import harness as H
from rung_engine.service import Service
from support import seed


@pytest.fixture
def bare(tmp_path):
    """A store with no profiles yet: the live backend lists the isolated home's Hermes profiles itself."""
    store = tmp_path / "store" / "rung.db"
    engine = H.use_store(store)
    yield engine, tmp_path
    try:
        engine.close()
    finally:
        H.release_store()


def settings_row(page, name):
    return page.locator(f".rung [data-testid=main] tr[data-profile={name}]").first


def excluded(scope) -> dict:
    return dict(scope.evaluate("""el => [...el.querySelectorAll('[data-excluded]')]
        .map(x => [x.getAttribute('data-excluded'), x.querySelector('[data-reason]').getAttribute('data-reason')])"""))


def ranked(row) -> list:
    return row.evaluate("""el => [...el.querySelectorAll('.mono.text-fg')].map(x => x.innerText)""")


def rest(page, method, path, body=None):
    return page.evaluate("""async ([m, p, b]) => { try { return {ok: true, data: await window.__rungRest(p, {method: m, body: b || undefined})} }
        catch (e) { return {ok: false, error: String((e && (e.body || e.message)) || e)} } }""", [method, path, body])


def test_alc01_alc02_alc03_alc04_alc05_alc06_alc07_alc08_allocation_filters(bare, page):
    e, tmp = bare
    folder = H.copy_fixture("csvtidy", tmp / "work")
    # The backend's first listing pre-fills tools from each Hermes profile's toolsets.
    H.open_rung(page)
    H.wait_until(lambda: any(p["name"] == "coder" for p in e.profiles()), timeout=30, msg="Hermes profiles listed")
    coder_tools = e.profile("coder")["tools"]
    assert {"todo", "kanban", "terminal"} <= set(coder_tools), coder_tools
    seed.seed_csvtidy(e, folder, with_history=False)
    H.configure_stubs(e, folder, worker_delay=6)
    e.set_setting("drafting", {**e.settings()["drafting"], "profile": "coder"})
    e.save_profiles([
        {"name": "reviewer", "labels": ["review", "python"], "cost": 4, "max_runs": 3, "tools": ["browser", "file", "web"]},
        {"name": "writer", "labels": ["docs", "specs"], "cost": 3, "max_runs": 3, "tools": ["terminal", "file"]},
        {"name": "researcher", "labels": ["research"], "cost": 6, "max_runs": 3, "enabled": False, "tools": ["web"]},
    ])
    e.open_project("csvtidy")

    # 1. Settings: tool chips and At once; edit, save, reload, persisted.
    H.open_rung(page)
    page.evaluate("window.__rungNavigate('settings')")
    settings_row(page, "reviewer").wait_for(timeout=20000)
    chips = settings_row(page, "coder").locator("[data-tool]")
    assert {chips.nth(i).get_attribute("data-tool") for i in range(chips.count())} == set(coder_tools)
    assert settings_row(page, "writer").locator("input[name=at_once]").input_value() == "2"
    settings_row(page, "reviewer").locator("[data-remove=browser]").click()
    settings_row(page, "writer").locator("input[name=at_once]").fill("1")
    H.button(page, "Save").click()
    H.wait_until(lambda: e.profile("writer")["at_once"] == 1 and "browser" not in e.profile("reviewer")["tools"],
                 msg="saved")
    H.open_rung(page)  # reloads the window first
    page.evaluate("window.__rungNavigate('settings')")
    settings_row(page, "reviewer").wait_for(timeout=20000)
    assert settings_row(page, "reviewer").locator("[data-tool=browser]").count() == 0
    assert settings_row(page, "writer").locator("input[name=at_once]").input_value() == "1"

    # 2. Setup: S-2.1's current text is a fresh draft by the drafting stub as coder, approved by you.
    e.approve_requirements("csvtidy", "N-1")
    svc = Service(e, inline_runs=True)
    svc.set_authoring("csvtidy", "R-2", "ai", wait=True)
    svc.regenerate("csvtidy", "S-2.1", wait=True)
    svc.wait_idle()
    assert e.rung("csvtidy", "S-2.1")["drafted_by"] == "coder"
    e.approve("csvtidy", "S-2.1")
    # N-1's remaining requirement R-3 gets a specification and a test, so N-1's Develop step opens.
    s31 = e.write_spec("csvtidy", "R-3", "Count dropped rows and print the count to stderr")["id"]
    e.approve("csvtidy", s31)
    e.add_test("csvtidy", s31, {"type": "command", "command": "python3 -m unittest -q"}, status="approved")
    e.approve_tests("csvtidy", "N-1")
    # On S-2.1, declare required tool terminal and an independent carrier.
    page.evaluate("window.__rungNavigate('rung', {rid: 'S-2.1'})")
    car = page.locator(".rung [data-testid=carrier]").first
    car.wait_for(timeout=20000)
    car.locator("[data-testid=required-tools-add]").click()
    car.locator("[data-testid=required-tools-input]").fill("terminal")
    page.keyboard.press("Enter")
    H.wait_until(lambda: e.rung("csvtidy", "S-2.1").get("allocation", e.suggest("csvtidy", "S-2.1")) is not None
                 and "terminal" in e.suggest("csvtidy", "S-2.1")["required_tools"], msg="terminal required")
    car.locator("[data-testid=independent]").click()
    H.wait_until(lambda: e.suggest("csvtidy", "S-2.1")["independent"], msg="independent carrier")

    # 3. Develop ranks the eligible profiles and lists every excluded one with its reason.
    page.evaluate("window.__rungNavigate('build', {need: 'N-1', step: 'develop'})")
    row = page.locator(".rung [data-testid=develop-table] [data-spec=\"S-2.1\"]").first
    row.wait_for(timeout=20000)
    want = {"coder": "author of S-2.1", "reviewer": "missing tool terminal", "researcher": "disabled"}
    has = lambda got: all(w in got.get(k, "").split("; ") for k, w in want.items())
    H.wait_until(lambda: has(excluded(row)),
                 msg=f"excluded: {excluded(row) if row.count() else None}")
    sug = e.suggest("csvtidy", "S-2.1")
    assert [s["profile"] for s in sug["suggestions"]] == ["writer"]
    assert {x["profile"]: x["reason"] for x in sug["excluded"]} == excluded(row)
    H.evidence(page, 26)  # 8. Develop with the ranking and the excluded profiles (retaken below at the end)

    # 4. writer busy elsewhere: at capacity 1 of 1, out of the ranking; back when the run ends.
    r = rest(page, "POST", "/projects/csvtidy/specs/S-1.1/send", {"agent": "writer"})
    assert r["ok"], r
    H.wait_until(lambda: excluded(row).get("writer") == "at capacity 1 of 1", timeout=20,
                 msg=f"writer at capacity: {excluded(row)}")
    assert not e.suggest("csvtidy", "S-2.1")["suggestions"]
    H.wait_until(lambda: "writer" not in excluded(row), timeout=120, msg="writer back once the run ends")
    assert [s["profile"] for s in e.suggest("csvtidy", "S-2.1")["suggestions"]] == ["writer"]

    # 7. The REST API and rung_claim refuse an excluded profile with the reason the pane shows.
    for path in ("/projects/csvtidy/specs/S-2.1/pick", "/projects/csvtidy/specs/S-2.1/send"):
        r = rest(page, "POST", path, {"agent": "coder"})
        assert not r["ok"] and "author of S-2.1" in r["error"], (path, r)
    C.use_profile(page, "coder")
    try:
        C.new_session(page)
        out = C.turn(page, "claim rung S-2.1")
        assert "coder is not eligible for S-2.1: author of S-2.1" in out, out
        assert not e.claims("csvtidy")
    finally:
        C.use_profile(page, "default")

    # 5. S-1.1 human only: no profile offered, each listed human only, no Send.
    H.open_rung(page)
    page.evaluate("window.__rungNavigate('rung', {rid: 'S-1.1'})")
    car = page.locator(".rung [data-testid=carrier]").first
    car.wait_for(timeout=20000)
    car.locator("[data-testid=human-only]").click()
    H.wait_until(lambda: e.suggest("csvtidy", "S-1.1")["human_only"], msg="S-1.1 human only")
    assert page.locator(".rung [data-testid=develop]").count() == 0
    page.evaluate("window.__rungNavigate('build', {need: 'N-1', step: 'develop'})")
    r11 = page.locator(".rung [data-testid=develop-table] [data-spec=\"S-1.1\"]").first
    r11.wait_for(timeout=20000)
    H.wait_until(lambda: excluded(r11) and all("human only" in v.split("; ") for v in excluded(r11).values()), msg=f"each excluded: human only: {excluded(r11)}")
    assert set(excluded(r11)) >= {"coder", "reviewer", "writer"}
    assert not e.suggest("csvtidy", "S-1.1")["suggestions"]
    assert r11.get_by_role("button", name="Send").count() == 0
    assert rest(page, "POST", "/projects/csvtidy/specs/S-1.1/send", {"agent": "writer"})["ok"] is False

    # 6. Settings: per profile, what it is excluded from in csvtidy, with the reason.
    page.evaluate("window.__rungNavigate('settings')")
    ex = page.locator(".rung [data-testid=settings-exclusions]").first
    ex.wait_for(timeout=20000)
    got = ex.evaluate("""el => Object.fromEntries([...el.querySelectorAll('[data-profile]')].map(p => [p.getAttribute('data-profile'),
        Object.fromEntries([...p.querySelectorAll('[data-excluded-spec]')].map(x => [x.getAttribute('data-excluded-spec'),
          x.querySelector('[data-reason]').getAttribute('data-reason')]))]))""")
    assert got["coder"]["S-2.1"] == "author of S-2.1" and got["reviewer"]["S-2.1"] == "missing tool terminal"
    assert "human only" in got["writer"]["S-1.1"].split("; ") and "disabled" in got["researcher"]["S-2.1"].split("; ")

    # 8. The screenshot: Develop with the ranking and the excluded profiles.
    page.evaluate("window.__rungNavigate('build', {need: 'N-1', step: 'develop'})")
    row = page.locator(".rung [data-testid=develop-table] [data-spec=\"S-2.1\"]").first
    row.wait_for(timeout=20000)
    time.sleep(0.5)
    row.scroll_into_view_if_needed()
    H.evidence(page, 26)
