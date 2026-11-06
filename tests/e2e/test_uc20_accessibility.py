"""UC20 Keyboard and screen reader: names, focus, dialogs, contrast and reduced motion, measured in the pane."""

import json

import pytest

import a11y as A
import harness as H
from support import seed

NEED = "Merge two CSV exports by a shared key"
SUGGESTED = ["Match rows by a chosen key column", "Report keys found in only one file", "Keep the first file's column order"]
R5_EDITED = "Report keys found in only one of the two files"
THEMES = [("catppuccin", "dark"), ("catppuccin", "light"), ("github", "light"), ("github", "dark")]


class Keys:
    """Keyboard only: Tab until the wanted element has focus, checking each focused pane element shows focus."""

    def __init__(self, page):
        self.page = page
        self.unseen = []

    def to(self, js_match: str, limit: int = 250, back: bool = False):
        for _ in range(limit):
            self.page.keyboard.press("Shift+Tab" if back else "Tab")
            f = A.focus(self.page)
            if f["inside"] and not f["visible"]:
                self.unseen.append(f)
            if self.page.evaluate(f"(() => {{ const el = document.activeElement; return !!el && ({js_match}) }})()"):
                return
        raise AssertionError(f"focus never reached {js_match}")

    def button(self, name: str, within: str = ".rung"):
        self.to(f"!!el.closest({json.dumps(within)}) && (el.innerText || '').trim() === {json.dumps(name)}")

    def press(self, key="Enter"):
        self.page.keyboard.press(key)


def test_acc01_acc02_acc04_keyboard_journey(rung, csvtidy, page):
    e = rung.engine
    seed.seed_csvtidy(e, csvtidy)
    e.open_project("csvtidy")
    H.open_rung(page)
    H.wait_view(page, "home")
    page.locator(".rung [data-testid=tile-needs-you]").wait_for()
    named = {}
    k = Keys(page)
    named["home"] = A.unnamed_controls(page)
    assert not A.colour_only(page)
    # New need
    k.button("New need")
    k.press()
    H.wait_view(page, "need-new")
    k.to("el.name === 'need'")
    page.keyboard.type(NEED)
    sugg = page.locator(".rung [data-testid=suggested] [data-suggestion]")
    H.wait_until(lambda: sugg.count() == 3, timeout=15, msg="three suggestions")
    named["need-new"] = A.unnamed_controls(page)
    for text in SUGGESTED[:2]:
        k.button("Accept", f'[data-suggestion="{text}"]')
        k.press()
        row = page.locator(f".rung [data-suggestion=\"{text}\"]")
        H.wait_until(lambda: row.get_attribute("data-mark") == "accepted", msg="accepted mark")
    k.button("Dismiss", f'[data-suggestion="{SUGGESTED[2]}"]')
    k.press()
    k.button("Create need")
    k.press()
    H.wait_view(page, "build")
    reqs = page.locator(".rung [data-testid=requirements] [data-req]")
    H.wait_until(lambda: reqs.count() == 2, msg="two requirements")
    named["build-reqs"] = A.unnamed_controls(page)
    assert not A.colour_only(page)
    # New requirement
    k.button("New requirement")
    k.press()
    H.wait_view(page, "req-new")
    k.to("el.name === 'req-text'")
    page.keyboard.type(SUGGESTED[2])
    named["req-new"] = A.unnamed_controls(page)
    k.button("Approve")
    k.press()
    H.wait_view(page, "build")
    H.wait_until(lambda: reqs.count() == 3, msg="three requirements")
    # Edit R-5
    k.button("Edit", '[data-req="R-5"]')
    k.press()
    H.wait_view(page, "rung")
    page.locator(".rung [data-testid=req-editor]").wait_for()
    k.to("el.name === 'req-text'")
    page.keyboard.press("ControlOrMeta+A")
    page.keyboard.type(R5_EDITED)
    named["req-edit"] = A.unnamed_controls(page)
    k.button("Approve")
    k.press()
    H.wait_view(page, "build")
    H.wait_until(lambda: page.locator(".rung [data-req=R-5] [data-testid=req-text]").inner_text() == R5_EDITED,
                 msg="edited R-5")
    # Approve all
    k.button("Approve all")
    k.press()
    H.wait_until(lambda: page.locator(".rung [data-testid=spec-step]").count() == 1, msg="Specifications opened")
    named["build-specs"] = A.unnamed_controls(page)
    assert [r["status"] for r in H.stored(rung.store, "SELECT status FROM rungs WHERE kind='requirement' "
                                                      "AND parent_pk=(SELECT pk FROM rungs WHERE rid='N-2')")] == \
        ["approved"] * 3
    assert not k.unseen, f"focused without a visible focus indicator: {k.unseen[:5]}"
    H.evidence(page, 20)
    assert not {v: n for v, n in named.items() if n}, named


VIEWS = [
    ("rung", {"rid": "T-2.1a"}), ("rung", {"rid": "S-2.1"}), ("rung", {"rid": "R-2"}), ("rung", {"rid": "N-1"}),
    ("exec", {"test": "T-2.1a", "n": 2}), ("readout", {"need": "N-1"}), ("projects", {}), ("settings", {}),
    ("project-settings", {}), ("retired", {}), ("build", {"need": "N-1", "step": "develop"}),
]


def test_acc02_acc04_every_view_named(rung, csvtidy, page):
    e = rung.engine
    seed.seed_csvtidy(e, csvtidy)
    notes = H.copy_fixture("notes-sync", rung.work)
    seed.seed_notes_sync(e, notes)
    e.open_project("csvtidy")
    H.open_rung(page)
    H.wait_view(page, "home")
    bad = {}
    for view, params in VIEWS:
        page.evaluate("([v, p]) => window.__rungNavigate(v, p)", [view, params])
        H.wait_view(page, view)
        page.wait_for_timeout(600)
        miss = A.unnamed_controls(page)
        dots = A.colour_only(page)
        if miss or dots:
            bad[f"{view} {params}"] = {"unnamed": miss, "colour_only": dots}
    assert not bad, bad


def test_acc03_dialogs_trap_focus_and_return_it(rung, csvtidy, page):
    e = rung.engine
    seed.seed_csvtidy(e, csvtidy)
    notes = H.copy_fixture("notes-sync", rung.work)
    seed.seed_notes_sync(e, notes)
    e.open_project("csvtidy")
    H.open_rung(page)
    H.wait_view(page, "home")
    k = Keys(page)

    def check(dialog_testid, opener_js):
        dialog = page.locator(f".rung [data-testid={dialog_testid}]")
        dialog.wait_for()
        inside = f"!!el.closest('[data-testid={dialog_testid}]')"
        assert page.evaluate(f"(() => {{ const el = document.activeElement; return {inside} }})()"), "focus taken"
        for _ in range(12):
            page.keyboard.press("Tab")
            assert page.evaluate(f"(() => {{ const el = document.activeElement; return {inside} }})()"), "focus kept"
        for _ in range(4):
            page.keyboard.press("Shift+Tab")
            assert page.evaluate(f"(() => {{ const el = document.activeElement; return {inside} }})()"), "focus kept"
        assert page.get_attribute(f".rung [data-testid={dialog_testid}]", "role") == "dialog"
        page.keyboard.press("Escape")
        dialog.wait_for(state="detached")
        assert page.evaluate(f"(() => {{ const el = document.activeElement; return !!el && ({opener_js}) }})()"), \
            "focus returned to the opener"

    # Retire
    page.evaluate("window.__rungNavigate('rung', {rid: 'N-1'})")
    H.wait_view(page, "rung")
    k.to("el.getAttribute('data-testid') === 'retire'")
    k.press()
    check("retire-dialog", "el.getAttribute('data-testid') === 'retire'")
    assert e.tree("csvtidy")  # Escape retired nothing
    # Raise defect
    page.evaluate("window.__rungNavigate('rung', {rid: 'T-2.1a'})")
    H.wait_view(page, "rung")
    k.button("Raise defect")
    k.press()
    check("defect-modal", "(el.innerText || '').trim() === 'Raise defect'")
    # Delete confirmation
    page.evaluate("window.__rungNavigate('project-settings')")
    H.wait_view(page, "project-settings")
    k.to("el.getAttribute('data-testid') === 'delete-project'")
    k.press()
    check("delete-dialog", "el.getAttribute('data-testid') === 'delete-project'")
    assert sorted(p["name"] for p in e.projects()) == ["csvtidy", "notes-sync"]


@pytest.mark.parametrize("theme", THEMES, ids=lambda t: "-".join(t))
def test_acc05_contrast(rung, csvtidy, theme):
    e = rung.engine
    seed.seed_csvtidy(e, csvtidy)
    e.edit("csvtidy", "R-2", text="Normalise every date to ISO 8601 with a time zone")
    e.open_project("csvtidy")
    with H.desktop(theme=theme) as page:
        H.open_rung(page)
        H.wait_view(page, "home")
        page.locator(".rung [data-testid=needs-you-item]").first.wait_for()
        bad = {}
        for view, params in [("home", {}), ("rung", {"rid": "T-2.1a"}), ("exec", {"test": "T-2.1a", "n": 2}),
                             ("readout", {"need": "N-1"}), ("build", {"need": "N-1", "step": "develop"})]:
            page.evaluate("([v, p]) => window.__rungNavigate(v, p)", [view, params])
            H.wait_view(page, view)
            page.wait_for_timeout(600)
            fails = A.contrast_failures(page)
            if fails:
                bad[view] = fails[:8]
        assert not bad, f"{theme}: {bad}"


def test_acc06_reduced_motion_stops_animation(rung, csvtidy, page):
    e = rung.engine
    seed.seed_merge(e, csvtidy, upto="develop")
    H.configure_stubs(e, csvtidy, worker_delay=20.0)
    s = page.context.new_cdp_session(page)
    s.send("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]})
    try:
        H.open_rung(page, fresh=False)
        # No reload (the reduced-motion emulation stays on this page), so the pane keeps the view the
        # previous test left it on: start from home explicitly.
        page.evaluate("window.__rungNavigate('home')")
        H.wait_view(page, "home")
        page.evaluate("window.__rungNavigate('build', {need: 'N-2', step: 'develop'})")
        row = page.locator(".rung [data-testid=develop-table] [data-spec=\"S-4.1\"]")
        row.wait_for()
        H.button(page, "Send", row).click()
        H.wait_view(page, "run")
        page.locator(".rung [data-testid=run-time]").wait_for()
        running = page.evaluate("""() => [...document.querySelectorAll('.rung *')]
            .filter(el => { const st = getComputedStyle(el); return st.animationName !== 'none' && st.animationPlayState === 'running' })
            .length""")
        assert running == 0
        page.locator(".rung [data-testid=stop]").click()
    finally:
        s.send("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "no-preference"}]})
        s.detach()
