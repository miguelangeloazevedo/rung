"""UC30 Route walk: every view and state the gallery captures, left by every visible exit and by Escape
(NAV-01 to NAV-04, NAV-13), the missing page for missing destinations (NAV-07), one h1 that is the largest
heading and takes focus (NAV-08), aria-current on breadcrumbs, the step strip and the rail (NAV-09), rows and
links that are focusable, Enter-operated and at least 24 by 24 pixels (NAV-15), live work left running by its
way out (NAV-16), failed loads shown with the project (NAV-17), and a 320 pixel pane (NAV-14)."""

from __future__ import annotations

import time

import harness as H
from support import seed

P = "csvtidy"
FORMS = {"need-new", "req-new", "spec-edit", "test-edit", "project-new", "defect-new"}

# What a named way out goes to (NAV-04): the view, and a check of its params.
NAMED = {
    "Back to Need": ("rung", lambda n: str(n.get("rid", "")).startswith("N-")),
    "Back to Requirements": ("build", lambda n: n.get("step") == "reqs"),
    "Back to Specifications": ("build", lambda n: n.get("step") == "specs"),
    "Back to Tests": ("build", lambda n: n.get("step") == "tests"),
    "Back to build": ("build", lambda n: True),
    "Back to test": ("rung", lambda n: str(n.get("rid", "")).startswith("T-")),
    "Back to run": ("run", lambda n: True),
}

EXITS_JS = """() => {
  const root = document.querySelector('.rung [data-rung-view]')
  if (!root) return []
  return [...root.querySelectorAll('button, [role=button]')]
    .filter(b => b.offsetParent !== null && !b.closest('[role=dialog]') && !b.disabled)
    .map(b => ({ text: (b.innerText || '').trim(), testid: b.getAttribute('data-testid') || '' }))
    .filter(b => b.testid === 'project-name' || ['Back', 'Cancel', 'Home'].includes(b.text) || b.text.startsWith('Back to '))
}"""

STATE_JS = """() => {
  const root = document.querySelector('.rung [data-rung-view]')
  const vis = el => el.offsetParent !== null
  const h1s = root ? [...root.querySelectorAll('h1')].filter(vis) : []
  const size = el => parseFloat(getComputedStyle(el).fontSize)
  const heads = root ? [...root.querySelectorAll('h2, h3, h4, h5, h6')].filter(vis) : []
  const a = document.activeElement
  const loading = root ? [...root.querySelectorAll('*')].some(e => !e.children.length && e.textContent.trim() === 'Loading' && vis(e)) : true
  const cur = sel => root ? [...root.querySelectorAll(sel)].filter(vis).map(c => c.querySelectorAll('[aria-current]').length) : []
  return {
    h1: h1s.map(e => e.innerText.trim()), h1size: h1s.length ? size(h1s[0]) : 0,
    bigger: heads.filter(e => h1s.length && size(e) > size(h1s[0])).map(e => e.tagName + ' ' + e.innerText.trim().slice(0, 30)),
    focusH1: !!(a && a.hasAttribute('data-page-title')), loading,
    crumbs: cur('[data-testid=crumbs]'), strip: cur('[data-testid=build-strip]'),
    missing: !!(root && root.querySelector('[data-testid=missing]')),
  }
}"""

TARGETS_JS = """() => {
  const root = document.querySelector('.rung [data-rung-view]')
  if (!root) return []
  return [...root.querySelectorAll('a, button, [role=button], [onclick]')]
    .filter(el => el.offsetParent !== null && !el.closest('[role=dialog]'))
    .map(el => { const r = el.getBoundingClientRect(); return {
      tag: el.tagName.toLowerCase(), href: el.getAttribute('href'), tab: el.tabIndex, disabled: !!el.disabled || el.getAttribute('aria-disabled') === 'true',
      w: Math.round(r.width * 10) / 10, h: Math.round(r.height * 10) / 10,
      label: (el.getAttribute('aria-label') || el.innerText || '').trim().slice(0, 40), testid: el.getAttribute('data-testid') || '' } })
}"""


def nav(page):
    return page.evaluate("window.__rungNav()")


def settle(page, what, budget=2.0):
    """The view leaves Loading within the budget and focus lands on its h1."""
    t0 = time.time()
    last = None
    while time.time() - t0 < budget + 3:
        last = page.evaluate(STATE_JS)
        if not last["loading"] and last["focusH1"]:
            break
        page.wait_for_timeout(100)
    took = time.time() - t0
    assert not last["loading"], f"{what}: still Loading after {took:.1f}s"
    assert last["focusH1"], f"{what}: focus not on the h1 ({page.evaluate('document.activeElement.outerHTML.slice(0, 120)')})"
    assert took <= budget, f"{what}: Loading for {took:.1f}s"
    return last


def open_from_home(page, view, params):
    page.evaluate("window.__rungNavigate('home')")
    H.wait_until(lambda: nav(page)["view"] == "home" and page.locator(".rung [data-rung-view=home]").count() == 1,
                 msg="home")
    page.evaluate("([v, p]) => window.__rungView(v, p)", [view, params])
    H.wait_until(lambda: nav(page)["view"] == view, msg=f"{view} open")


def check_landing(page, origin, how, state):
    n = nav(page)
    what = f"{origin} by {how} -> {n}"
    assert n["view"] not in FORMS, f"{what}: landed on a form"
    assert n.get("project") == P, f"{what}: another project"
    if how == "project name":
        assert n["view"] == "projects", what
    elif how == "Home":
        assert n["view"] == "home", what
    elif how in NAMED:
        view, ok = NAMED[how]
        assert n["view"] == view and ok(n), what
    elif how == "Escape":
        named = [NAMED[x["text"]] for x in state["exits"] if x["text"] in NAMED]
        assert n["view"] == "home" or any(n["view"] == v and ok(n) for v, ok in named), what
    else:  # Back, Cancel: where the person came from (home)
        assert n["view"] == "home", what
    settle(page, what)


def build_fixture(e, page, csvtidy):
    seed.seed_merge(e, csvtidy, upto="develop")
    H.configure_stubs(e, csvtidy, worker_delay=0.3)
    e.open_project(P)
    tree = e.tree(P)
    first = {}

    def walk(nodes):
        for n in nodes:
            first.setdefault(n["kind"], n["id"])
            walk(n.get("children") or [])
    walk(tree)
    e.edit(P, "R-1", text="Detect the delimiter of each file", approve=True)
    change = e.changes(P, "R-1")[0]["id"]
    e.create_need(P, "Export a summary of removed rows")
    gone = [n["id"] for n in e.tree(P) if n["kind"] == "need"][-1]
    e.retire_need(P, gone, "Covered by another tool")
    test = "T-1.1a"
    e.run_test(P, test, carried_by="coder")
    n = e.executions(P, test)[0]["n"]
    H.open_rung(page)
    page.evaluate(f"window.__rungRest('/projects/{P}/specs/S-4.1/send', {{method: 'POST', body: {{}}}})")
    run = H.wait_until(lambda: (e.runs(P, "S-4.1") or [None])[0], msg="the run starts")
    H.wait_until(lambda: e.run(run["id"])["status"] not in ("queued", "running"), timeout=90, msg="the run ends")
    return {"need": "N-2", "req": first["requirement"], "spec": first["specification"], "test": test, "n": n,
            "run": run["id"], "change": change}


def states(f):
    return [
        ("home", {}), ("projects", {}), ("projects", {"tab": "archived"}), ("settings", {}), ("project-settings", {}),
        ("need-new", {}), ("req-new", {"need": f["need"]}), ("spec-edit", {"req": "R-3", "need": "N-1", "ret": "specs"}),
        ("test-edit", {"spec": f["spec"], "need": "N-1", "ret": "tests"}),
        ("rung", {"rid": "N-1"}), ("rung", {"rid": f["req"]}), ("rung", {"rid": f["spec"]}), ("rung", {"rid": f["test"]}),
        ("spec-edit", {"spec": f["spec"]}), ("test-edit", {"test": f["test"]}),
        ("build", {"need": f["need"], "step": "need"}), ("build", {"need": f["need"], "step": "reqs"}),
        ("build", {"need": f["need"], "step": "specs"}), ("build", {"need": f["need"], "step": "tests"}),
        ("build", {"need": f["need"], "step": "develop"}),
        ("run", {"run": f["run"]}), ("attempt", {"run": f["run"], "n": 1}), ("exec", {"test": f["test"], "n": f["n"]}),
        ("readout", {"need": "N-1"}), ("change", {"change": f["change"], "rid": "R-1"}), ("retired", {}),
        # Missing destinations and the unknown view.
        ("rung", {"rid": "S-99.9"}), ("run", {"run": 99999}), ("attempt", {"run": f["run"], "n": 99}),
        ("exec", {"test": f["test"], "n": 999}), ("change", {"change": 99999, "rid": "R-1"}), ("no-such-view", {}),
    ]


MISSING_FROM = 26  # states(f)[26:] are the missing destinations


def test_nav01_nav02_nav03_nav04_nav07_nav08_nav09_nav13_route_walk(rung, csvtidy, page):
    e = rung.engine
    f = build_fixture(e, page, csvtidy)
    walked = []
    for i, (view, params) in enumerate(states(f)):
        origin = f"{view} {params}"
        open_from_home(page, view, params)
        st = settle(page, origin)
        st["exits"] = page.evaluate(EXITS_JS)
        # NAV-08: one h1, the largest heading.
        assert len(st["h1"]) == 1, f"{origin}: h1s {st['h1']}"
        assert not st["bigger"], f"{origin}: headings larger than the h1: {st['bigger']}"
        # A heading stays a heading: an action on it is a button inside it, never a role on the heading.
        assert page.locator(".rung :is(h1, h2, h3, h4, h5, h6)[role]").count() == 0, f"{origin}: a heading with a role"
        # NAV-09: the current item marked on breadcrumbs, the step strip and the rail.
        assert all(c == 1 for c in st["crumbs"]), f"{origin}: crumbs aria-current {st['crumbs']}"
        assert all(c == 1 for c in st["strip"]), f"{origin}: strip aria-current {st['strip']}"
        sel = params.get("rid")
        if view == "rung" and i < MISSING_FROM:
            cur = page.locator(f".rung [data-testid=rail] [aria-current][data-rung=\"{sel}\"]")
            assert cur.count() == 1, f"{origin}: rail does not mark {sel}"
        # NAV-07: missing destinations show one page with Back, Home and Projects.
        if i >= MISSING_FROM:
            assert st["missing"], f"{origin}: no missing page"
            for b in ("Back", "Home", "Projects"):
                assert H.button(page, b, page.locator(".rung [data-testid=missing]")).is_visible(), (origin, b)
            # It stands alone: no tiles, tree or allocation of a page the person did not reach.
            assert page.locator(".rung .r-tiles, .rung [data-testid=rail]").count() == 0, f"{origin}: missing page shows project content"
            if view == "exec":
                H.evidence(page, 30)
        # NAV-01: a visible way out.
        assert any(x["text"] in ("Back", "Cancel") or x["text"].startswith("Back to ") for x in st["exits"]) \
            or view in ("home", "projects"), f"{origin}: no way out {st['exits']}"
        # NAV-02 to NAV-04, NAV-13: every exit, then Escape.
        for x in st["exits"]:
            how = "project name" if x["testid"] == "project-name" else x["text"]
            open_from_home(page, view, params)
            settle(page, origin)
            loc = page.locator(".rung [data-rung-view] [data-testid=project-name]").first if how == "project name" \
                else H.button(page, x["text"], page.locator(".rung [data-rung-view]").first)
            loc.click()
            H.wait_until(lambda: nav(page)["view"] != view or nav(page) != {"view": view, **params, "project": P},
                         timeout=5, msg=f"{origin}: {how} moves")
            check_landing(page, origin, how, st)
            walked.append((origin, how))
        if view not in ("home", "projects"):
            open_from_home(page, view, params)
            settle(page, origin)
            page.keyboard.press("Escape")
            H.wait_until(lambda: nav(page)["view"] != view or nav(page).get("step") != params.get("step"),
                         timeout=5, msg=f"{origin}: Escape moves")
            check_landing(page, origin, "Escape", st)
            walked.append((origin, "Escape"))
    assert len(walked) > len(states(f)) * 2, walked


def test_nav15_rows_and_links_are_controls_of_24_pixels(rung, csvtidy, page):
    e = rung.engine
    f = build_fixture(e, page, csvtidy)
    small, bad = [], []
    for view, params in states(f)[:MISSING_FROM]:
        open_from_home(page, view, params)
        settle(page, f"{view} {params}")
        for t in page.evaluate(TARGETS_JS):
            if t["tag"] == "a" and not t["href"]:
                bad.append((view, params, t["label"], t["testid"], "anchor without href"))
            if not t["disabled"] and t["tab"] < 0 and t["tag"] != "a":
                bad.append((view, params, t["label"], t["testid"], "not in the Tab order"))
            if t["w"] < 24 or t["h"] < 24:
                small.append((view, params.get("rid") or params.get("step") or "", t["label"], t["testid"], t["w"], t["h"]))
    assert not bad, bad[:10]
    assert not small, small[:20]
    # Reached by Tab and opened by Enter: a rail row on home, an attempt row on the run, a step on the strip.
    for view, params, target, lands in (
            ("home", {}, ".rung [data-testid=rail] [data-rung=\"N-1\"]", "rung"),
            ("run", {"run": f["run"]}, ".rung [data-attempt]", "attempt"),
            ("build", {"need": f["need"], "step": "develop"}, ".rung [data-testid=build-strip] [data-step=Tests]", "build")):
        open_from_home(page, view, params)
        settle(page, view)
        el = page.locator(target).first
        el.wait_for(timeout=10000)
        for _ in range(200):
            page.keyboard.press("Tab")
            if el.evaluate("el => el === document.activeElement"):
                break
        else:
            raise AssertionError(f"Tab never reached {target} on {view}")
        page.keyboard.press("Enter")
        H.wait_until(lambda: nav(page)["view"] == lands and (lands != "build" or nav(page).get("step") == "tests"),
                     msg=f"Enter on {target} opens {lands} ({nav(page)})")


def test_nav16_live_work_is_left_running(rung, csvtidy, page):
    e = rung.engine
    seed.seed_merge(e, csvtidy, upto="develop")
    H.configure_stubs(e, csvtidy, worker_delay=40)
    e.open_project(P)
    t = e.add_test(P, "S-1.1", {"type": "command", "command": "sleep 30"}, status="approved")["id"]
    H.open_rung(page)
    try:
        # A running execution: Back to test, then Escape, leave it running.
        for how in ("Back to test", "Escape"):
            page.evaluate(f"window.__rungNavigate('rung', {{rid: '{t}'}})")
            if how == "Back to test":
                page.locator(".rung [data-testid=run-tests]").first.click()
            else:
                x = e.executions(P, t)[0]
                page.evaluate(f"window.__rungNavigate('rung', {{rid: '{t}'}})")
                page.evaluate(f"window.__rungView('exec', {{test: '{t}', n: {x['n']}}})")
            H.wait_view(page, "exec")
            H.wait_until(lambda: e.executions(P, t)[0]["status"] == "running", msg="the execution runs")
            settle(page, f"exec ({how})")
            assert page.locator(".rung [data-testid=cancel]").first.is_visible()
            if how == "Escape":
                page.keyboard.press("Escape")
            else:
                H.button(page, "Back to test").click()
            H.wait_until(lambda: nav(page)["view"] == "rung" and nav(page)["rid"] == t, msg=f"{how} goes to the test")
            assert e.executions(P, t)[0]["status"] == "running", f"{how} stopped the execution"
        # A live develop run: Back to build, then Escape, leave it running.
        page.evaluate(f"window.__rungRest('/projects/{P}/specs/S-4.1/send', {{method: 'POST', body: {{}}}})")
        run = H.wait_until(lambda: (e.runs(P, "S-4.1") or [None])[0], msg="the run starts")
        for how in ("Back to build", "Escape"):
            page.evaluate("window.__rungNavigate('home')")
            page.evaluate(f"window.__rungView('run', {{run: {run['id']}}})")
            H.wait_view(page, "run")
            settle(page, f"run ({how})")
            H.wait_until(lambda: e.run(run["id"])["status"] in ("queued", "running"), msg="the run is live")
            assert page.locator(".rung [data-testid=stop]").first.is_visible()
            if how == "Escape":
                page.keyboard.press("Escape")
            else:
                H.button(page, "Back to build").first.click()
            H.wait_until(lambda: nav(page)["view"] == "build", msg=f"{how} goes to the build ({nav(page)})")
            assert e.run(run["id"])["status"] in ("queued", "running"), f"{how} stopped the run"
    finally:
        for x in e.executions(P, t):
            if x["status"] == "running":
                e.cancel_execution(P, t, x["n"])
        for r in e.runs(P, "S-4.1"):
            if r["status"] in ("queued", "running"):
                e.cancel_run(r["id"])


def test_nav17_failed_loads_show_the_error_with_the_project(rung, csvtidy, page):
    e = rung.engine
    seed.seed_merge(e, csvtidy, upto="develop")
    e.open_project(P)
    H.open_rung(page)
    H.wait_view(page, "home")
    page.evaluate("window.__rungRefuse(['/state', '/settings'])")
    try:
        for view, params in (("projects", {}), ("project-new", {}), ("settings", {}), ("project-settings", {}),
                             ("build", {"need": "N-2", "step": "develop"}), ("test-edit", {"spec": "S-1.1"})):
            page.evaluate("([v, p]) => window.__rungNavigate(v, p)", [view, params])
            H.wait_until(lambda: nav(page)["view"] == view, msg=view)
            main = page.locator(".rung [data-rung-view]").first

            def shown():
                st = page.evaluate(STATE_JS)
                alerts = page.locator(".rung [data-rung-view] [role=alert]")
                texts = [alerts.nth(i).inner_text() for i in range(alerts.count())]
                return not st["loading"] and sum("refused" in t.lower() for t in texts) == 1 and P in main.inner_text()
            H.wait_until(shown, timeout=10, msg=lambda: f"{view}: the error with the project: {main.inner_text()[:300]}")
    finally:
        page.evaluate("window.__rungRefuse([])")


def test_nav14_a_320_pixel_pane(rung, csvtidy, page):
    e = rung.engine
    seed.seed_merge(e, csvtidy, upto="develop")
    e.open_project(P)
    # A proposal: its card pairs text with Accept and Dismiss, the row that broke into letters at 320 pixels.
    e.propose(P, "N-1", "requirement", "Keep the header row unchanged", "reviewer")
    H.open_rung(page)
    H.wait_view(page, "home")
    page.evaluate("document.querySelector('.rung').style.width = '320px'")
    try:
        for view, params in (("projects", {}), ("home", {}), ("build", {"need": "N-2", "step": "specs"}),
                             ("rung", {"rid": "S-1.1"})):
            page.evaluate("([v, p]) => window.__rungNavigate(v, p)", [view, params])
            H.wait_until(lambda: nav(page)["view"] == view, msg=view)
            settle(page, f"{view} at 320", budget=15)  # layout is under test here, not load time
            got = page.evaluate("""() => {
              const root = document.querySelector('.rung'), R = root.getBoundingClientRect()
              const main = root.querySelector('.r-col-main') || root.querySelector('[data-testid=main]')
              const rail = root.querySelector('[data-testid=rail], .r-side')
              const strip = root.querySelector('[data-testid=build-strip]')
              const out = [...root.querySelectorAll('[data-rung-view] button, [data-rung-view] [role=button]')]
                .filter(b => b.offsetParent !== null)
                .map(b => { const r = b.getBoundingClientRect(); return { t: (b.innerText || b.getAttribute('aria-label') || '').trim().slice(0, 30), l: r.left - R.left, r: R.right - r.right } })
                .filter(x => x.l < -0.5 || x.r < -0.5)
              const m = main && main.getBoundingClientRect(), s = rail && rail.getBoundingClientRect()
              const broken = [...root.querySelectorAll('[data-rung-view] button:not(.text-left), [data-rung-view] [data-status]')]
                .filter(b => b.offsetParent !== null && b.getClientRects().length && b.getBoundingClientRect().height > 2.2 * parseFloat(getComputedStyle(b).lineHeight || '16'))
                .map(b => (b.innerText || '').trim().slice(0, 20))
              const hidden = [...root.querySelectorAll('.rs-label')].filter(l => l.offsetParent === null || l.getBoundingClientRect().width < 1).map(l => l.textContent)
              return { width: R.width, railAfter: !rail || (s.top >= m.bottom - 1 && s.left - R.left < 30), out, hidden, broken,
                       stripFits: !strip || strip.scrollWidth <= strip.clientWidth + 1,
                       hscroll: root.scrollWidth > root.clientWidth + 1 }
            }""")
            assert abs(got["width"] - 320) < 1, got
            assert got["railAfter"], f"{view}: the rail is not under the main column"
            assert got["stripFits"], f"{view}: the step strip does not wrap"
            assert not got["hidden"], f"{view}: step names hidden {got['hidden']}"
            assert not got["broken"], f"{view}: controls broken across lines {got['broken']}"
            assert not got["out"], f"{view}: clipped {got['out'][:8]}"
    finally:
        page.evaluate("document.querySelector('.rung').style.width = ''")
