// Rung desktop pane: core helpers, data access, status palette.
import {
  host, atom, useValue, useQuery, queryClient, useTheme,
  hexToOklch, oklchToHex, maxChroma, hueDelta, contrastRatio, readableOn,
  ROUTES_AREA, SIDEBAR_NAV_AREA, STATUSBAR_AREAS
} from '@hermes/plugin-sdk'
import * as React from 'react'

const RUNG_CSS = /*__RUNG_CSS__*/''
const ROUTE = '/rung'
const VIEWS = {}

// ------------------------------------------------------------------ element helpers

function h(tag, props, ...kids) {
  const p = props == null ? {} : typeof props === 'string' ? { className: props } : props
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

function navigate(view, params) {
  $nav.set({ view, ...(params || {}) })
  if (!String(location.hash || '').includes(ROUTE)) host.navigate(ROUTE)
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

async function post(path, body) {
  try {
    const data = await rest(path, { method: 'POST', body: body || {} })
    refresh()
    return { ok: true, data }
  } catch (e) {
    refresh()
    return { ok: false, error: errText(e) }
  }
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

function fit(H, C, bg) {
  const dark = relLum(bg) < 0.2
  const Ls = []
  if (dark) for (let L = 55; L <= 95; L++) Ls.push(L / 100)
  else for (let L = 70; L >= 20; L--) Ls.push(L / 100)
  let hex = '#888888'
  for (const L of Ls) {
    const c = Math.min(C, Math.max(0, maxChroma(L, H) - 0.001))
    hex = oklchToHex({ l: L, c, h: H })
    if ((contrastRatio(hex, bg) || 0) >= 4.5) return hex
  }
  return hex
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
    '--r-muted': 'var(--ui-text-tertiary)', '--r-dim': pal.draft,
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
  if (st === 'stale') return 'stale'
  if (st === 'draft' || st === 'proposed' || st === 'dismissed') return 'dim'
  if (node.kind === 'test') {
    return { pass: 'pass', fail: 'fail', stale: 'stale', pending: 'needs', running: 'needs' }[node.result] || 'dim'
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
  return { pass: 'pass', fail: 'fail', stale: 'stale', pending: 'pending', not_run: 'not run', running: 'running' }[r] || 'not run'
}
