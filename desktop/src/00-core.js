// Rung desktop pane: core helpers, data access, status palette.
import {
  host, atom, useValue, useQuery, queryClient, useTheme,
  hexToOklch, oklchToHex, maxChroma, hueDelta, contrastRatio, readableOn,
  ROUTES_AREA, SIDEBAR_NAV_AREA, STATUSBAR_AREAS, PANES_AREA, PALETTE_AREA
} from '@hermes/plugin-sdk'
import * as React from 'react'

const RUNG_CSS = /*__RUNG_CSS__*/''
const ROUTE = '/rung'
const VIEWS = {}

// ------------------------------------------------------------------ element helpers

// Accessible names for form fields, by their name attribute (fields carry no visible <label for>).
const FIELD_NAMES = {
  name: 'Name', folder: 'Folder', test_command: 'Test command', profile: 'Profile', 'need-text': 'Need', need: 'Need',
  'req-text': 'Requirement', 'req-detail': 'Acceptance', 'spec-text': 'Specification', 'spec-detail': 'Approach',
  steps: 'Steps', command: 'Command', rule: 'Pass rule', value: 'Pass rule value', timeout: 'Timeout',
  limit: 'Output limit', text: 'Judge question', evidence: 'Evidence', 'defect-title': 'Title', category: 'Category',
  cost: 'Cost', max_runs: 'Max runs', test_timeout: 'Default timeout', output_limit: 'Output limit',
  reason: 'Reason', confirm: 'Project name', search: 'Search projects'
}
const NATIVE = { button: 1, a: 1, input: 1, select: 1, textarea: 1, label: 1, option: 1 }

function activate(fn) {
  return e => {
    if (e.target !== e.currentTarget) return
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fn(e) }
  }
}

function h(tag, props, ...kids) {
  let p = props == null ? {} : typeof props === 'string' ? { className: props } : props
  if (typeof tag === 'string') {
    // Anything clickable is reachable and operable from the keyboard, with the same handler.
    if (p.onClick && (!NATIVE[tag] || (tag === 'a' && !p.href))) {
      p = { ...p, role: p.role || 'button', tabIndex: p.tabIndex != null ? p.tabIndex : 0, onKeyDown: p.onKeyDown || activate(p.onClick) }
    }
    // a field points at its error line (fe-<name>), which exists only while there is an error
    if ((tag === 'input' || tag === 'textarea' || tag === 'select') && p.name && !p['aria-describedby'] && p.type !== 'checkbox' && p.type !== 'radio') {
      p = { ...p, 'aria-describedby': 'fe-' + p.name }
    }
    // checkboxes and radios are named by the label that wraps them
    if ((tag === 'input' || tag === 'textarea' || tag === 'select') && !p['aria-label'] && !p.id && p.type !== 'checkbox' && p.type !== 'radio') {
      const named = FIELD_NAMES[p.name] || p.placeholder || p.name
      if (named) p = { ...p, 'aria-label': named }
    }
  }
  return React.createElement(tag, p, ...kids)
}

function cx(...parts) {
  return parts.filter(Boolean).join(' ')
}

function frag(...kids) {
  return React.createElement(React.Fragment, null, ...kids)
}

const useState = React.useState
const useEffect = React.useEffect
const useMemo = React.useMemo
const useRef = React.useRef

// ------------------------------------------------------------------ backend

let CTX = null
const $nav = atom({ view: 'home' })
const $rev = atom(0)

// ------------------------------------------------------------------ navigation contract
// Every view change goes through navigate():
// - a form with unsaved text holds the change behind Discard / Keep editing (opts.force skips the question:
//   an explicit Cancel, or the move after a save);
// - an overlay belongs to the view that opened it and closes with it;
// - the view that is left is remembered, so Back returns to it (opts.replace leaves no entry).
const $leave = atom(null)
const DIRTY = new Set()
const ON_LEAVE = []
const HIST = []
const EXITS = []
let CUR_PROJECT = null
const $notice = atom(null)

// A form reports whether it holds unsaved text while it is mounted.
function useDirty(dirty) {
  const ref = useRef(false)
  ref.current = !!dirty
  useEffect(() => { const f = () => ref.current; DIRTY.add(f); return () => { DIRTY.delete(f) } }, [])
}

// A view names its way out (the action of its Back or Cancel); Escape takes it, asking first if text is unsaved.
// `task` marks a form or an editor: a place that is left, never returned to.
function useExit(fn, task) {
  const ref = useRef(fn)
  ref.current = fn
  useEffect(() => {
    if (!ref.current) return undefined  // no way out to register (a button that is not the view's exit)
    const x = { go: () => ref.current(), task: !!task }
    EXITS.push(x)
    return () => { const i = EXITS.indexOf(x); if (i >= 0) EXITS.splice(i, 1) }
  }, [])
}

// After a refused submit, the first field marked invalid takes focus.
function focusInvalid() {
  setTimeout(() => { const el = document.querySelector('.rung [aria-invalid=true]'); if (el && el.focus) el.focus() }, 30)
}

// A line naming what an action did, shown on the view the action lands on until the next view change.
// Set after the current handler finishes, so it lands on the view the action moves to, whichever order the
// handler calls notify and navigate in.
function notify(text) { setTimeout(() => $notice.set(text), 0) }

function unsaved() {
  for (const f of DIRTY) if (f()) return true
  return false
}

function guard(go, force) {
  if (!force && unsaved()) { $leave.set({ go }); return false }
  go()
  return true
}

// History holds places to return to: a task view (a form or an editor, which registers a way out) is never one,
// since its text is gone once left; each entry remembers its project, so Back never crosses projects.
// Needs you spans every project, so it stays a place to return to from whichever project it opened.
const CROSS = new Set(['projects'])
const ours = e => e._p === CUR_PROJECT || e._p === '*'
function commit(next, replace) {
  const cur = $nav.get()
  if (!replace && cur && !EXITS.some(x => x.task)) { HIST.push({ ...cur, _p: CROSS.has(cur.view) ? '*' : CUR_PROJECT }); if (HIST.length > 50) HIST.shift() }
  for (const f of ON_LEAVE) f()
  $leave.set(null)
  $notice.set(null)
  $nav.set(next)
}

function popHistory() {
  while (HIST.length) {
    const e = HIST.pop()
    if (ours(e)) { const { _p, ...v } = e; return v }
  }
  return null
}

// Whether the view the person came from (the entry Back would use) is this one.
function cameFrom(view) {
  for (let i = HIST.length - 1; i >= 0; i--) if (ours(HIST[i])) return HIST[i].view === view
  return false
}

function sameView(a, view, params) {
  if (!a || a.view !== view) return false
  return Object.entries(params || {}).every(([k, v]) => String(a[k]) === String(v))
}

// Changes the Rung page's view. It never moves the app: a request that finishes after the person went to a
// chat updates the page they left and leaves them where they are.
function navigate(view, params, opts) {
  const o = opts || {}
  return guard(() => commit({ view, ...(params || {}) }, o.replace), o.force)
}

// Back, Cancel and Escape: the view the person came from, else the given parent. Leaving adds no entry.
function goBack(view, params, opts) {
  const o = opts || {}
  return guard(() => {
    const prev = popHistory()
    commit(prev || { view, ...(params || {}) }, true)
  }, o.force)
}

// "Back to X": always X. When X is where the person came from, that entry is used up.
function returnTo(view, params, opts) {
  const o = opts || {}
  return guard(() => {
    const top = HIST[HIST.length - 1]
    if (top && ours(top) && sameView(top, view, params)) HIST.pop()
    commit({ view, ...(params || {}) }, true)
  }, o.force)
}

// After a save or a create: the destination, with no entry for the finished form.
// The move after a successful action, with the line that names what it did on the view it lands on.
function finish(view, params, notice) {
  if (notice) notify(notice)
  return navigate(view, params, { force: true, replace: true })
}

// Opens Rung on a view from outside it (the dock, the status bar): a click, so the app moves.
// When unsaved text holds the change, the app still moves, so the person sees the question.
function openRung(view, params, opts) {
  navigate(view, params, opts)
  if (!String(location.hash || '').includes(ROUTE)) { noteOutside(location.hash); host.navigate(ROUTE) }
}

// The Desktop view the person was on before entering Rung: closing Rung returns there, else to the chat home.
let OUTSIDE = null
function noteOutside(hash) {
  const h = String(hash || '')
  if (!h.includes(ROUTE)) OUTSIDE = h.replace(/^#/, '') || '/'
}
function onHashChange(e) {
  if (!String(location.hash || '').includes(ROUTE)) return
  try { noteOutside(new URL(e.oldURL).hash) } catch (_) { /* no previous view */ }
}
// The Desktop's router moves with pushState, which fires no hashchange; the browser's Navigation API sees every move.
function onNavigate(e) {
  try {
    const to = new URL(e.destination.url).hash
    if (String(to).includes(ROUTE)) noteOutside(new URL(window.navigation.currentEntry.url).hash)
  } catch (_) { /* no previous view */ }
}
function closeRung() {
  host.navigate(OUTSIDE || '/')
}

// Escape on a task view: its way out. Dialogs, menus and fields that use Escape themselves come first.
function onEscape(e) {
  if (e.key !== 'Escape' || e.defaultPrevented || !EXITS.length) return
  if (!String(location.hash || '').includes(ROUTE)) return
  if (document.querySelector('.rung [role=dialog], .rung [role=menu], .rung [role=listbox], .rung [data-layer]')) return
  guard(EXITS[EXITS.length - 1].go)
}

async function rest(path, opts) {
  if (!CTX) throw new Error('Rung is not loaded')
  return CTX.rest(path, opts)
}

function errText(e) {
  const raw = (e && (e.body || e.data || e.detail || e.message)) || String(e)
  if (typeof raw === 'object') return raw.detail || JSON.stringify(raw)
  try {
    const j = JSON.parse(String(raw).replace(/^[^{]*/, ''))
    if (j && j.detail) return j.detail
  } catch (_) { /* plain text */ }
  return String(raw).replace(/^Error:\s*/, '').replace(/^\d{3}[^:]*:\s*/, '')
}

function errInfo(e) {
  const raw = (e && (e.body || e.data || e.detail || e.message)) || String(e)
  let j = typeof raw === 'object' ? raw : null
  if (!j) { try { j = JSON.parse(String(raw).replace(/^[^{]*/, '')) } catch (_) { j = null } }
  return { field: (j && j.field) || null, fields: (j && j.fields) || null, code: (j && j.code) || null }
}

// The result line of each create, save, approve and record (NAV-11), named once here so no door forgets it.
// Views that know a better name (Retired, Archived, Raised...) call notify() after, which replaces this one.
const RESULTS = [
  [/\/rungs\/([^/]+)\/approve$/, m => `Approved ${m[1]}`],
  [/\/needs\/([^/]+)\/approve-requirements$/, m => `Approved the requirements of ${m[1]}`],
  [/\/needs\/([^/]+)\/approve-drafted$/, m => `Approved the specifications of ${m[1]}`],
  [/\/needs\/([^/]+)\/approve-tests$/, m => `Approved the tests of ${m[1]}`],
  [/\/tests\/([^/]+)\/executions\/(\d+)\/approve$/, m => `Approved execution ${m[2]} of ${m[1]}`],
  [/\/rungs\/([^/]+)\/edit$/, m => `Saved ${m[1]}`],
  [/\/projects\/[^/]+\/needs$/, (m, b, d) => `Created ${(d && d.id) || 'the need'}`],
  [/\/needs\/[^/]+\/requirements$/, (m, b, d) => `Added ${(d && d.id) || 'the requirement'}`],
  [/\/rungs\/[^/]+\/spec$/, (m, b, d) => `Added ${(d && d.id) || 'the specification'}`],
  [/\/specs\/[^/]+\/tests$/, (m, b, d) => `Added ${(d && d.id) || 'the test'}`],
  [/\/projects\/[^/]+\/tests\/([^/]+)$/, m => `Saved ${m[1]}`],
  [/\/tests\/([^/]+)\/record$/, (m, b) => `Recorded ${b && b.result === 'fail' ? 'Fail' : 'Pass'} for ${m[1]}`],
  [/\/suggestions\/[^/]+$/, (m, b, d) => b && b.accept ? `Added ${(d && d.id) || 'the suggestion'}` : null],
  [/\/bot\/[^/]+\/items\/\d+$/, (m, b, d) => b && b.accept ? `Added ${(d && d.id) || 'the suggestion'}` : null],
]
function resultLine(path, body, data) {
  const p = decodeURIComponent(String(path).split('?')[0])
  for (const [re, f] of RESULTS) { const m = p.match(re); if (m) return f(m, body, data) }
  return null
}

async function post(path, body) {
  try {
    const data = await rest(path, { method: 'POST', body: body || {} })
    refresh()
    const line = resultLine(path, body, data)
    if (line) notify(line)
    return { ok: true, data }
  } catch (e) {
    refresh()
    return { ok: false, error: errText(e), ...errInfo(e) }
  }
}

// The version of the content the form shows. While `follow` is true (nothing typed yet, the form shows the live
// rung) it follows refetches; once the person edits, refetches never move it, so a write made meanwhile
// elsewhere is refused as a conflict instead of being silently overwritten.
function useBase(v, follow = false) {
  const ref = useRef(null)
  if (v != null && (ref.current == null || follow)) ref.current = v
  return ref.current
}

function refresh() {
  queryClient.invalidateQueries({ queryKey: ['rung'] })
}

function useApi(path, opts) {
  const q = useQuery({
    queryKey: ['rung', path],
    queryFn: () => rest(path),
    enabled: !!path && !(opts && opts.enabled === false),
    staleTime: 0,
    // A missing id or a refused request (4xx) is an answer, not a hiccup: show it at once instead of retrying.
    retry: (n, e) => n < 2 && !(e && e.status >= 400 && e.status < 500) && !/^(Error:\s*)?4\d\d\b/.test(String((e && e.message) || '')),
    refetchInterval: opts && opts.live ? 1000 : false
  })
  return q
}

// ------------------------------------------------------------------ formatting

function ago(ts) {
  if (!ts) return ''
  const s = Math.max(0, Date.now() / 1000 - ts)
  if (s < 45) return 'just now'
  if (s < 3600) return `${Math.max(1, Math.round(s / 60))} min ago`
  if (s < 86400) return `${Math.round(s / 3600)} h ago`
  if (s < 172800) return 'yesterday'
  return `${Math.floor(s / 86400)} days ago`
}

function clock(ts) {
  if (!ts) return ''
  const d = new Date(ts * 1000)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function dur(sec) {
  if (sec == null) return ''
  sec = Math.max(0, Math.round(sec))
  if (sec < 60) return `${sec}s`
  return `${Math.floor(sec / 60)}m ${String(sec % 60).padStart(2, '0')}s`
}

function shortPath(p) {
  if (!p) return ''
  const m = String(p).match(/^\/(?:Users|home)\/[^/]+(\/.*)?$/)
  return m ? '~' + (m[1] || '') : p
}

const KIND_WORD = { need: 'Need', requirement: 'Requirement', specification: 'Specification', test: 'Test' }

// ------------------------------------------------------------------ status palette

const STATUS_HUES = { pass: 150, fail: 27, stale: 305 }
const AMBER = 75

function relLum(hex) {
  const cr = contrastRatio(hex, '#000000')
  return cr == null ? 0 : cr * 0.05 - 0.05
}

function mixHex(a, b, t) {
  // b over a at fraction t, in sRGB, as color-mix(in srgb) and the bg-x/10 tints render it
  const p = x => [1, 3, 5].map(i => parseInt(x.slice(i, i + 2), 16))
  const [x, y] = [p(a), p(b)]
  return '#' + x.map((v, i) => Math.round(v * (1 - t) + y[i] * t).toString(16).padStart(2, '0')).join('')
}

// Every surface status text sits on: page, card, well, button, hover, and the status's own 15% tint.
function surfaces(bg) {
  const dark = relLum(bg) < 0.2
  return dark
    ? [bg, mixHex(bg, '#000000', 0.12), mixHex(bg, '#000000', 0.30), mixHex(bg, '#ffffff', 0.03), mixHex(bg, '#ffffff', 0.09)]
    : [bg, mixHex(bg, '#000000', 0.02), mixHex(bg, '#000000', 0.04), mixHex(bg, '#000000', 0.04), mixHex(bg, '#000000', 0.08)]
}

function readsOn(hex, bg) {
  const all = surfaces(bg)
  const tint = mixHex(all[1], hex, 0.15)
  return [...all, tint].every(s => (contrastRatio(hex, s) || 0) >= 4.5)
}

function fit(H, C, bg) {
  const dark = relLum(bg) < 0.2
  const Ls = []
  if (dark) for (let L = 55; L <= 98; L++) Ls.push(L / 100)
  else for (let L = 70; L >= 10; L--) Ls.push(L / 100)
  let hex = '#888888'
  for (const L of Ls) {
    const c = Math.min(C, Math.max(0, maxChroma(L, H) - 0.001))
    hex = oklchToHex({ l: L, c, h: H })
    if (readsOn(hex, bg)) return hex
  }
  return hex
}

function rendered(cssVar) {
  // The theme's colour as the browser resolves it, whatever notation the theme uses.
  const el = document.createElement('span')
  el.style.color = `var(${cssVar})`
  document.body.appendChild(el)
  const m = getComputedStyle(el).color.match(/\d+(\.\d+)?/g)
  el.remove()
  if (!m || m.length < 3) return null
  return '#' + m.slice(0, 3).map(v => Math.round(+v).toString(16).padStart(2, '0')).join('')
}

function cssHex(name) {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return /^#[0-9a-f]{6}$/i.test(v) ? v : null
}

function computePalette(overrides) {
  const bg = cssHex('--theme-background-seed') || '#171827'
  const accent = cssHex('--theme-midground') || cssHex('--theme-primary') || '#e5a94b'
  const pal = {}
  for (const [k, H] of Object.entries(STATUS_HUES)) pal[k] = fit(H, 0.16, bg)
  const acc = hexToOklch(accent)
  const accentOk = !!acc && acc.c > 0.06 &&
    Math.min(...Object.values(STATUS_HUES).map(H => Math.abs(hueDelta(acc.h, H)))) >= 60
  pal.needs = fit(accentOk ? acc.h : AMBER, 0.16, bg)
  pal.draft = fit(0, 0, bg)
  for (const k of ['needs', 'pass', 'fail', 'stale', 'draft']) {
    const o = overrides && overrides[k === 'needs' ? 'needs_you' : k]
    if (o && o !== 'theme' && /^#[0-9a-f]{6}$/i.test(o)) pal[k] = o
  }
  // Secondary text keeps the theme's colour where it reads on every surface, else the nearest neutral that does.
  const muted = rendered('--ui-text-tertiary')
  pal.muted = muted && readsOn(muted, bg) ? null : fit(0, 0, bg)
  const dark = relLum(bg) < 0.2
  pal.dark = dark
  pal.bg = bg
  pal.source = accentOk ? 'accent' : 'amber'
  return pal
}

function paletteVars(pal) {
  const mix = (pct, other) => `color-mix(in srgb, ${pal.bg} ${100 - pct}%, ${other})`
  return {
    '--r-needs': pal.needs, '--r-pass': pal.pass, '--r-fail': pal.fail, '--r-stale': pal.stale,
    '--r-draft': pal.draft, '--r-on-needs': readableOn(pal.needs), '--r-on-pass': readableOn(pal.pass),
    '--r-fg': 'var(--ui-text-primary)', '--r-fg2': 'var(--ui-text-secondary)',
    '--r-muted': pal.muted || 'var(--ui-text-tertiary)', '--r-dim': pal.draft,
    '--r-line': pal.dark ? mix(14, '#ffffff') : mix(12, '#000000'),
    '--r-line2': pal.dark ? mix(10, '#ffffff') : mix(8, '#000000'),
    '--r-card': pal.dark ? mix(12, '#000000') : mix(2, '#000000'),
    '--r-well': pal.dark ? mix(30, '#000000') : mix(4, '#000000'),
    '--r-btn': pal.dark ? mix(3, '#ffffff') : mix(4, '#000000'),
    '--r-btnh': pal.dark ? mix(9, '#ffffff') : mix(8, '#000000'),
    '--r-page': pal.bg
  }
}

const $colours = atom(null)

function usePalette() {
  const theme = useTheme()
  const overrides = useValue($colours)
  const [tick, setTick] = useState(0)
  useEffect(() => {
    const mo = new MutationObserver(() => setTick(t => t + 1))
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ['style', 'class'] })
    const t = setTimeout(() => setTick(x => x + 1), 50)
    return () => { mo.disconnect(); clearTimeout(t) }
  }, [])
  return useMemo(() => computePalette(overrides), [theme && theme.themeName, theme && theme.resolvedMode, tick, overrides])
}

function Root({ children, className }) {
  const pal = usePalette()
  return h('div', { className: cx('rung', className), style: paletteVars(pal), 'data-rung-palette': pal.source }, children)
}

// status -> colour token for dots and labels
function tone(node) {
  if (!node) return 'dim'
  const st = node.status
  if (node.kind === 'specification' && (node.draft_state === 'failed' || node.draft_state === 'drafting')) return 'needs'  // as the Draft failed and Drafting badges
  if (st === 'stale') return 'stale'
  if (st === 'draft' || st === 'proposed' || st === 'dismissed') return 'dim'
  if (node.kind === 'test') {
    return { pass: 'pass', fail: 'fail', stale: 'stale', pending: 'needs', running: 'needs', error: 'needs' }[node.result] || 'dim'
  }
  if (node.kind === 'specification') {
    if (node.released) return 'pass'
    if ((node.blockers || []).some(b => /failed/.test(b))) return 'fail'
    return 'muted'
  }
  if (node.kind === 'requirement') {
    return { covered: 'pass', failing: 'fail', stale: 'stale', draft: 'dim' }[node.coverage] || 'muted'
  }
  return 'pass'
}

const TONE_BG = { pass: 'bg-pass', fail: 'bg-fail', stale: 'bg-stale', needs: 'bg-needs', dim: 'bg-dim', muted: 'bg-muted', fg: 'bg-fg' }
const TONE_TEXT = { pass: 'text-pass', fail: 'text-fail', stale: 'text-stale', needs: 'text-needs', dim: 'text-dim', muted: 'text-muted', fg: 'text-fg' }
// safelist: bg-pass bg-fail bg-stale bg-needs bg-dim bg-muted bg-fg text-pass text-fail text-stale text-needs text-dim text-muted text-fg
// safelist: bg-pass/10 bg-fail/10 bg-stale/15 bg-needs/10 border-pass/30 border-fail/30 border-stale/30 border-needs/30 border-needs border-pass border-fail border-stale

function capital(s) {
  return s ? s[0].toUpperCase() + s.slice(1) : s
}

function resultWord(r) {
  return { pass: 'pass', fail: 'fail', stale: 'stale', pending: 'pending', not_run: 'not run', running: 'running', error: 'error' }[r] || 'not run'
}
