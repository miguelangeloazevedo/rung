"""Accessibility measurements taken from the rendered pane: names from the browser's own accessibility
tree, contrast from computed colours, focus visibility from computed styles."""

from __future__ import annotations

CONTRAST_JS = r"""
() => {
  const root = document.querySelector('.rung')
  const parse = s => { const m = s.match(/rgba?\(([^)]+)\)/); if (!m) return null
    const p = m[1].split(/[ ,\/]+/).filter(Boolean).map(Number); return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1] }
  const over = (fg, bg) => [0, 1, 2].map(i => fg[i] * fg[3] + bg[i] * (1 - fg[3])).concat(1)
  const lum = c => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4) }
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]) }
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05) }
  const bgOf = el => {
    // What is painted under the text: every element at its centre, top to bottom, until an opaque one.
    const r = el.getBoundingClientRect()
    let under = document.elementsFromPoint(r.left + Math.min(r.width / 2, 6), r.top + r.height / 2)
    if (!under.includes(el)) { under = []; for (let e = el; e; e = e.parentElement) under.push(e) }  // scrolled out of view
    const stack = []
    for (const e of under) {
      const c = parse(getComputedStyle(e).backgroundColor)
      if (c && c[3] > 0) { stack.push(c); if (c[3] >= 1) break }
    }
    // Nothing opaque in the page: the window itself is painted in the theme's background.
    let bg = parse(getComputedStyle(document.documentElement).backgroundColor)
    if (!bg || bg[3] < 1) { const seed = getComputedStyle(document.documentElement).getPropertyValue('--theme-background-seed').trim()
      bg = /^#[0-9a-f]{6}$/i.test(seed) ? [1, 3, 5].map(i => parseInt(seed.slice(i, i + 2), 16)).concat(1) : [255, 255, 255, 1] }
    if (stack.length && stack[stack.length - 1][3] >= 1) bg = stack.pop()
    while (stack.length) bg = over(stack.pop(), bg)
    return bg
  }
  const faded = el => { for (let e = el; e && e !== document.body; e = e.parentElement) {
    if (parseFloat(getComputedStyle(e).opacity) < 1) return true
    if (e.disabled || e.getAttribute('aria-disabled') === 'true') return true } return false }
  const out = []
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
  const seen = new Set()
  while (walker.nextNode()) {
    const t = walker.currentNode
    const el = t.parentElement
    if (!t.textContent.trim() || seen.has(el)) continue
    seen.add(el)
    const r = el.getBoundingClientRect()
    if (!r.width || !r.height || getComputedStyle(el).visibility === 'hidden') continue
    if (el.closest('.sr-only') || el.closest('[aria-hidden=true]') || faded(el)) continue
    const st = getComputedStyle(el)
    const fg = parse(st.color)
    if (!fg) continue
    const bg = bgOf(el)
    const c = ratio(over(fg, bg), bg)
    const size = parseFloat(st.fontSize), bold = parseInt(st.fontWeight) >= 700
    const large = size >= 24 || (bold && size >= 18.66)
    out.push({ text: t.textContent.trim().slice(0, 40), ratio: Math.round(c * 100) / 100, need: large ? 3 : 4.5,
               cls: (el.className || '').toString().slice(0, 80) })
  }
  return out
}
"""

FOCUS_JS = r"""
() => {
  const el = document.activeElement
  if (!el || !el.closest('.rung')) return { inside: false }
  const st = getComputedStyle(el)
  const outline = st.outlineStyle !== 'none' && parseFloat(st.outlineWidth) > 0
  const ring = st.boxShadow && st.boxShadow !== 'none'
  return { inside: true, visible: outline || ring, tag: el.tagName, text: (el.innerText || el.value || '').slice(0, 40),
           testid: el.getAttribute('data-testid') }
}
"""

COLOUR_ONLY_JS = r"""
() => {
  // A status dot (an empty element painted in a status colour) must sit beside text that names the status.
  const bad = []
  for (const el of document.querySelectorAll('.rung span, .rung div')) {
    const cls = (el.className || '').toString()
    if (!/\bbg-(pass|fail|stale|needs)\b/.test(cls) || el.textContent.trim()) continue
    const r = el.getBoundingClientRect()
    if (!r.width || r.width > 16) continue
    const holder = el.parentElement
    if (!holder || !holder.textContent.trim()) bad.push(cls.slice(0, 60))
  }
  return bad
}
"""

ROLES = ("button", "link", "textbox", "checkbox", "radio", "switch", "combobox", "tab", "menuitem", "listbox",
         "searchbox", "spinbutton", "slider")


def unnamed_controls(page) -> list[dict]:
    """Interactive nodes under the pane whose accessible name, as Chromium computes it, is empty."""
    s = page.context.new_cdp_session(page)
    try:
        doc = s.send("DOM.getDocument", {"depth": 0})
        node = s.send("DOM.querySelector", {"nodeId": doc["root"]["nodeId"], "selector": ".rung"})
        bad = []
        for role in ROLES:
            res = s.send("Accessibility.queryAXTree", {"nodeId": node["nodeId"], "role": role})
            for n in res.get("nodes", []):
                if n.get("ignored"):
                    continue
                name = ((n.get("name") or {}).get("value") or "").strip()
                if not name:
                    bad.append({"role": role, "node": n.get("backendDOMNodeId")})
        return bad
    finally:
        s.detach()


def contrast_failures(page) -> list[dict]:
    return [x for x in page.evaluate(CONTRAST_JS) if x["ratio"] < x["need"]]


def focus(page) -> dict:
    return page.evaluate(FOCUS_JS)


def colour_only(page) -> list[str]:
    return page.evaluate(COLOUR_ONLY_JS)
