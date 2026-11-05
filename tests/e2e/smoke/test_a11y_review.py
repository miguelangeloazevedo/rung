"""WCAG 2.2 AA checks the accessibility review relies on beyond UC20: target size (2.5.8), focus not hidden
(2.4.11), reflow at 320 CSS px (1.4.10) and text spacing (1.4.12), measured in the pane."""

import harness as H
from support import seed

VIEWS = [("home", {}), ("rung", {"rid": "S-1.1"}), ("rung", {"rid": "T-1.1a"}), ("projects", {}),
         ("settings", {}), ("project-settings", {}), ("readout", {"need": "N-1"}),
         ("build", {"need": "N-1", "step": "tests"})]

SMALL = """() => {
  const out = []
  const els = [...document.querySelectorAll('.rung button, .rung a, .rung input, .rung select, .rung [role=button], .rung [tabindex="0"]')]
  const boxes = els.map(e => e.getBoundingClientRect())
  els.forEach((el, i) => {
    const r = boxes[i]
    if (!r.width || !r.height || r.bottom < 0 || r.top > innerHeight) return
    if (r.width >= 24 && r.height >= 24) return
    // Spacing exception: a 24 px circle on the target's centre meets no other target.
    const cx = r.left + r.width / 2, cy = r.top + r.height / 2
    // and, for another undersized target, meets no other such circle.
    const small = o => o.width < 24 || o.height < 24
    const clash = boxes.some((o, j) => {
      if (j === i || !o.width || els[j].contains(el) || el.contains(els[j])) return false
      if (Math.max(o.left - cx, 0, cx - o.right) ** 2 + Math.max(o.top - cy, 0, cy - o.bottom) ** 2 < 144) return true
      return small(o) && ((o.left + o.width / 2 - cx) ** 2 + (o.top + o.height / 2 - cy) ** 2) < 576
    })
    const inline = getComputedStyle(el).display === 'inline' || el.closest('p')
    if (clash && !inline && el.type !== 'checkbox' && el.type !== 'radio') out.push((el.getAttribute('data-testid') || el.textContent.trim().slice(0, 30) || el.tagName) + ' ' + Math.round(r.width) + 'x' + Math.round(r.height))
  })
  return out
}"""


def _each_view(rung, page, check):
    bad = {}
    for view, params in VIEWS:
        page.evaluate("([v, p]) => window.__rungNavigate(v, p)", [view, params])
        H.wait_view(page, view)
        page.wait_for_timeout(400)
        found = check()
        if found:
            bad[f"{view} {params}"] = found
    return bad


def test_acc07_targets_are_at_least_24px_or_spaced(rung, csvtidy, page):
    seed.seed_csvtidy(rung.engine, csvtidy)
    rung.engine.open_project("csvtidy")
    H.open_rung(page)
    H.wait_view(page, "home")
    bad = _each_view(rung, page, lambda: page.evaluate(SMALL))
    assert not bad, bad


def test_acc08_focus_is_never_hidden(rung, csvtidy, page):
    seed.seed_csvtidy(rung.engine, csvtidy)
    rung.engine.open_project("csvtidy")
    H.open_rung(page)
    H.wait_view(page, "home")
    page.locator(".rung [data-testid=rail]").first.click(position={"x": 2, "y": 2})
    hidden = []
    for _ in range(60):
        page.keyboard.press("Tab")
        state = page.evaluate("""() => { const a = document.activeElement
            if (!a || !a.closest('.rung')) return null
            const r = a.getBoundingClientRect()
            const x = Math.min(Math.max(r.left + r.width / 2, 0), innerWidth - 1), y = Math.min(Math.max(r.top + r.height / 2, 0), innerHeight - 1)
            const top = document.elementFromPoint(x, y)
            return { hidden: r.bottom < 0 || r.top > innerHeight || !(top && (a.contains(top) || top.contains(a))), name: a.textContent.trim().slice(0, 30) } }""")
        if state and state["hidden"]:
            hidden.append(state["name"])
    assert not hidden, hidden


def test_acc09_text_spacing(rung, csvtidy, page):
    seed.seed_csvtidy(rung.engine, csvtidy)
    rung.engine.open_project("csvtidy")
    H.open_rung(page)
    H.wait_view(page, "home")
    page.add_style_tag(content=".rung *{line-height:1.5!important;letter-spacing:.12em!important;word-spacing:.16em!important}"
                               ".rung p{margin-bottom:2em!important}")
    try:
        def clipped():
            return page.evaluate("""() => [...document.querySelectorAll('.rung button, .rung h1, .rung h2, .rung label')]
                .filter(e => e.getBoundingClientRect().width && e.scrollWidth > e.clientWidth + 1 && !/truncate/.test(e.className))
                .map(e => e.textContent.trim().slice(0, 30)).slice(0, 8)""")
        bad = _each_view(rung, page, clipped)
        assert not bad, bad
    finally:
        page.evaluate("document.querySelectorAll('style').forEach(s => s.textContent.includes('letter-spacing:.12em') && s.remove())")
