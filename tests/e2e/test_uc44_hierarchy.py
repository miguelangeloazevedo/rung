"""UC44 Hierarchy (decisions Round 24, U13): every view the gallery captures has one h1 naming its object or
question and at most one primary action (exactly one where the view has an action); at 1280 by 800, at the dock's
width and at 200 percent zoom the h1 and primary action are reachable without horizontal page scrolling; wide
tables scroll in their own region; truncated text shows in full on keyboard focus."""

from __future__ import annotations

import json
import os

import harness as H
from test_uc30_route_walk import MISSING_FROM, build_fixture, nav, open_from_home, settle, states

# Views a person only reads: no primary action is expected there (HIE-01 "or none on a read-only view").
READ_ONLY = {"run", "attempt", "exec", "change", "retired", "projects"}
DOCK_WIDTH = 420

PROBE_JS = """() => {
  const root = document.querySelector('.rung [data-rung-view]')
  const vis = el => el.offsetParent !== null && el.getClientRects().length
  const W = window.innerWidth
  const h1 = root ? [...root.querySelectorAll('h1')].filter(vis) : []
  const prim = root ? [...root.querySelectorAll('[data-primary]')].filter(b => vis(b) && !b.closest('[role=dialog]')) : []
  const box = el => { const r = el.getBoundingClientRect(); return { l: Math.round(r.left), r: Math.round(r.right) } }
  const se = document.scrollingElement
  const rr = document.querySelector('.rung')
  return {
    h1: h1.map(e => e.innerText.trim()), h1box: h1.map(box),
    primary: prim.map(b => (b.innerText || b.getAttribute('aria-label') || '').trim()), pbox: prim.map(box), W,
    pageScroll: se.scrollWidth > se.clientWidth + 1 || (rr && rr.scrollWidth > rr.clientWidth + 1),
    paneScroll: root ? root.scrollWidth > root.clientWidth + 1 : false,
  }
}"""

TRUNC_JS = """() => {
  const root = document.querySelector('.rung [data-rung-view]')
  if (!root) return []
  return [...root.querySelectorAll('.truncate')].filter(el => el.offsetParent !== null && el.scrollWidth > el.clientWidth + 1)
    .slice(0, 6).map((el, i) => { el.setAttribute('data-trunc-probe', String(i)); return i })
}"""


def _cdp(page):
    return page.context.new_cdp_session(page)


def _size(cdp, w, h, scale=1):
    cdp.send("Emulation.setDeviceMetricsOverride", {"width": w, "height": h, "deviceScaleFactor": scale, "mobile": False})


def test_hie01_hie02_hie03_hie04_hierarchy(rung, csvtidy, page):
    e = rung.engine
    f = build_fixture(e, page, csvtidy)
    cdp = _cdp(page)
    report, problems = [], []
    walk = [(v, p) for i, (v, p) in enumerate(states(f)) if i < MISSING_FROM]
    try:
        for size, (w, hgt, dock) in {"1280x800": (1280, 800, False), "dock": (1280, 800, True),
                                      "zoom200": (640, 400, False)}.items():
            _size(cdp, w, hgt)
            page.evaluate("w => { document.querySelector('.rung').style.width = w }", f"{DOCK_WIDTH}px" if dock else "")
            for view, params in walk:
                origin = f"{size} {view} {params}"
                open_from_home(page, view, params)
                settle(page, origin, budget=15)
                st = page.evaluate(PROBE_JS)
                report.append({"at": origin, **st})
                if len(st["h1"]) != 1 or not st["h1"][0] or st["h1"][0].lower() == "rung":
                    problems.append(f"{origin}: h1 {st['h1']}")
                if len(st["primary"]) > 1:
                    problems.append(f"{origin}: {len(st['primary'])} primary actions {st['primary']}")
                if size == "1280x800" and view not in READ_ONLY and len(st["primary"]) != 1:
                    problems.append(f"{origin}: no primary action")
                if st["pageScroll"]:
                    problems.append(f"{origin}: the page scrolls sideways")
                for b in st["h1box"] + st["pbox"]:
                    if b["l"] < 0 or b["r"] > st["W"] + 1:
                        problems.append(f"{origin}: h1 or primary outside the viewport {b} of {st['W']}")
                if size == "zoom200" and view == "rung" and params.get("rid") == "N-1":
                    H.evidence(page, 44)
                # HIE-04: truncated text met on the way shows in full on focus.
                if size == "1280x800":
                    page.wait_for_timeout(400)  # the view's truncated texts are found after it settles
                    for i in page.evaluate(TRUNC_JS):
                        el = page.locator(f".rung [data-trunc-probe='{i}']")
                        full = el.evaluate("""el => {
                          const f = el.matches(FOCUSABLE) ? el : el.closest(FOCUSABLE)
                          if (!f) return { focused: false, fits: false, why: 'not focusable' }
                          f.focus()
                          const a = document.activeElement
                          return { focused: a === f && a !== document.body, fits: el.scrollWidth <= el.clientWidth + 1 } }""".replace(
                            "FOCUSABLE", "'a,button,input,textarea,select,[tabindex],[role=button],[role=link]'"))
                        if not (full["focused"] and full["fits"]):
                            problems.append(f"{origin}: truncated text {el.inner_text()[:40]!r} {full}")
    finally:
        page.evaluate("document.querySelector('.rung').style.width = ''")
        cdp.send("Emulation.clearDeviceMetricsOverride")
    if os.environ.get("RUNG_HIE_REPORT"):
        open(os.environ["RUNG_HIE_REPORT"], "w").write(json.dumps({"report": report, "problems": problems}, indent=1))
    assert not problems, "\n".join(problems[:40])
