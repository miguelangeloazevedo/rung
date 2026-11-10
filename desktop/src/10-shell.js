// Rung desktop pane: layout shell, header, tiles, build strip, traceability rail.

// The project header's buttons: one size and look, at least 24 pixels tall.
const HEAD_BTN = 'inline-flex items-center min-h-[24px] px-2 py-0.5 rounded text-[11px] font-medium bg-card border border-line text-muted hover:text-fg'

const SOLID = { primary: 1, primaryLg: 1, acceptSolid: 1 }

function Btn({ kind, onClick, disabled, children, title, testid, className, label, current }) {
  const base = {
    primary: 'px-3 py-1.5 rounded-[6px] bg-needs text-on-needs font-semibold text-xs',
    primaryLg: 'px-3.5 py-1.5 rounded-[6px] bg-needs text-on-needs text-xs font-semibold',
    secondary: 'px-3 py-1.5 rounded-[6px] bg-btn border border-line text-fg text-xs font-medium hover:bg-btnh',
    quiet: 'px-3.5 py-1.5 rounded-[6px] bg-btn border border-line text-muted text-xs font-medium hover:bg-btnh',
    outline: 'px-3.5 py-1.5 rounded-[6px] border border-needs text-needs text-xs font-medium',
    accept: 'px-3 py-1 rounded bg-btn border border-needs text-needs text-xs font-medium',
    acceptSolid: 'px-3 py-1 rounded bg-needs text-on-needs text-xs font-semibold',
    ghost: 'px-2.5 py-1 rounded text-xs text-muted hover:text-fg',
    ghostLine: 'px-2.5 py-1 rounded text-xs text-muted border border-line',
    small: 'px-2.5 py-1 rounded-[6px] bg-btn border border-line text-fg text-xs font-medium hover:bg-btnh',
    head: HEAD_BTN
  }[kind || 'secondary']
  return h('button', {
    type: 'button',
    className: cx(base, 'whitespace-nowrap shrink-0', disabled && 'opacity-40 cursor-not-allowed', className),
    'aria-disabled': disabled ? 'true' : undefined,
    'data-locked': disabled ? '1' : undefined,
    // U13: a solid accent button is the view's one primary action (HIE-01 counts these).
    'data-primary': SOLID[kind] ? '1' : undefined,
    'data-testid': testid,
    'aria-label': label,
    'aria-current': current ? 'page' : undefined,
    title,
    onClick: e => { e.stopPropagation(); if (!disabled && onClick) onClick(e) }
  }, children)
}

const BADGE = {
  // Approval is a contract fact, not evidence: neutral. Green is kept for current evidence (decisions Round 22).
  approved: ['Approved', 'bg-btn text-fg border border-line'],
  stale: ['Stale', 'bg-stale/15 text-stale border border-stale/30'],
  draft: ['Draft', 'bg-dim/15 text-dim border border-dim/30'],
  proposed: ['Proposed', 'text-needs border border-needs'],
  dismissed: ['Dismissed', 'bg-btn text-dim border border-line'],
  pass: ['Pass', 'bg-pass/10 text-pass border border-pass/30'],
  fail: ['Fail', 'bg-fail/10 text-fail border border-fail/30'],
  pending: ['Pending approval', 'bg-needs/10 text-needs border border-needs/30'],
  not_run: ['Not run', 'bg-btn text-dim border border-line'],
  running: ['Running', 'text-needs border border-needs'],
  drafting: ['Drafting', 'bg-needs/10 text-needs border border-needs/30'],
  drafted: ['Drafted', 'bg-btn text-fg border border-line'],
  covered: ['Checks satisfied', 'bg-pass/10 text-pass border border-pass/30'],
  failing: ['Failing', 'bg-fail/10 text-fail border border-fail/30'],
  open: ['Open', 'bg-btn text-muted border border-line'],
  released: ['Verified', 'bg-pass/10 text-pass border border-pass/30'],
  cancelled: ['Cancelled', 'bg-btn text-muted border border-line'],
  failed: ['Failed', 'bg-fail/10 text-fail border border-fail/30'],
  passed: ['Passed', 'bg-pass/10 text-pass border border-pass/30'],
  queued: ['Queued', 'text-needs border border-needs'],
  error: ['Error', 'bg-needs/10 text-needs border border-needs/30'],
  unknown: ['Unknown', 'bg-btn text-fg border border-line'],
  needs_input: ['Needs input', 'bg-needs/10 text-needs border border-needs/30'],
  no_change: ['No change', 'bg-btn text-muted border border-line'],
  partial: ['Partial', 'bg-needs/10 text-needs border border-needs/30'],
  draft_failed: ['Draft failed', 'bg-needs/10 text-needs border border-needs/30'],
  seen_failing: ['Seen failing', 'bg-btn text-fg border border-line'],
  not_seen_failing: ['Not seen failing', 'bg-btn text-muted border border-line'],
  archived: ['Archived', 'bg-btn text-muted border border-line'],
  retired: ['Retired', 'bg-btn text-muted border border-line'],
  verified: ['Verified', 'bg-pass/10 text-pass border border-pass/30'],
  out_of_date: ['Out of date', 'bg-stale/15 text-stale border border-stale/30'],
  could_not_verify: ['Could not verify', 'bg-needs/10 text-needs border border-needs/30'],
  awaiting_manual: ['Waiting for you', 'bg-needs/10 text-needs border border-needs/30'],
  checking: ['Checking', 'text-needs border border-needs'],
  unverified: ['Not checked', 'bg-btn text-dim border border-line'],
  contract: ['Needs review', 'bg-btn text-fg border border-line'],
  read_only: ['Read only', 'bg-btn text-muted border border-line'],
  proven: ['Proven', 'bg-pass/10 text-pass border border-pass/30'],
  not_proven: ['Not proven', 'bg-btn text-muted border border-line'],
  complete: ['Complete', 'bg-pass/10 text-pass border border-pass/30'],
  not_complete: ['Not complete', 'bg-btn text-fg border border-line'],
  out_of_scope: ['Out of scope', 'bg-btn text-muted border border-line'],
  broken: ['Broken', 'bg-stale/15 text-stale border border-stale/30']
}

function SeenFailing({ value, small }) {
  if (value == null) return null
  return h(Badge, { status: value ? 'seen_failing' : 'not_seen_failing', small, testid: 'seen-failing' })
}

function Badge({ status, label, small, onClick, struck, testid }) {
  const [word, cls] = BADGE[status] || [status, 'bg-btn text-muted border border-line']
  return h('span', {
    className: cx('inline-flex items-center px-2 py-0.5 rounded font-medium whitespace-nowrap shrink-0', small ? 'text-[10px]' : 'text-[11px]', cls, onClick && 'cursor-pointer', struck && 'line-through'),
    'data-status': status,
    'data-testid': testid,
    onClick: onClick ? e => { e.stopPropagation(); onClick() } : undefined
  }, label || word)
}

function Dot({ t, size }) {
  return h('span', { className: cx(size === 'lg' ? 'w-2 h-2' : 'w-1.5 h-1.5', 'rounded-full shrink-0', TONE_BG[t] || 'bg-dim') })
}

function SectionTitle({ children, tone: t, right, dot }) {
  return h('div', 'flex items-center justify-between',
    h('h2', { className: cx('text-xs font-semibold uppercase tracking-wider flex items-center gap-1.5', t ? TONE_TEXT[t] : 'text-muted') },
      dot ? h('span', { className: cx('w-1.5 h-1.5 rounded-full', TONE_BG[dot] || 'bg-dim', dot === 'needs' && t !== 'needs' && 'animate-pulse') }) : null,
      children),
    right != null ? h('span', 'text-[11px] text-muted', right) : null)
}

// A card that opens something. A card holding its own buttons (`nested`) is not itself a button: a mouse click
// on it still opens, and its title is the keyboard's way in (no button inside a button).
function Card({ children, className, onClick, testid, style, nested }) {
  if (nested) return React.createElement('div', { className: cx('bg-card border border-line rounded-[6px]', onClick && 'cursor-pointer', className), onClick, 'data-testid': testid, style }, children)
  return h('div', {
    className: cx('bg-card border border-line rounded-[6px]', onClick && 'cursor-pointer', className),
    onClick, 'data-testid': testid, style
  }, children)
}

// ------------------------------------------------------------------ header and tiles

// The page's own name: the h1 of every in-project view, after the project it belongs to.
function usePageTitle(project) {
  const nav = useValue($nav)
  // Reads the rung the view already loads, without fetching it: a second fetching observer mounted by the error
  // page would reset a failed load to pending and the view would loop between Loading and the error.
  const rq = useApi(nav.view === 'rung' && nav.rid ? `/projects/${encodeURIComponent(project)}/rungs/${encodeURIComponent(nav.rid)}` : null, { enabled: false })
  const v = nav.view
  if (v === 'home' || v === 'defect-new') return 'Home'
  if (v === 'rung') return rq.data ? `${KIND_WORD[rq.data.kind] || 'Rung'} ${nav.rid}` : nav.rid || ''
  if (v === 'need-new') return 'New need'
  if (v === 'req-new') return 'New requirement'
  if (v === 'spec-edit') return nav.spec ? `Edit ${nav.spec}` : 'New specification'
  if (v === 'test-edit') return nav.test ? `Edit ${nav.test}` : 'New test'
  if (v === 'build') return `${STEPS[{ need: 0, reqs: 1, specs: 2, tests: 3, develop: 4 }[nav.step] ?? 1]} · ${nav.need}`
  if (v === 'readout') return `Results and evidence · ${nav.need}`
  if (v === 'change') return `Change · ${nav.rid}`
  if (v === 'run') return `Run ${nav.run}`
  if (v === 'attempt') return `Run ${nav.run} · attempt ${nav.n}`
  if (v === 'exec') return `Execution ${nav.test} #${nav.n}`
  return VIEWS[v] ? '' : 'Not found'
}

// The page name is the h1 and the largest text; the project name before it is the way to the project list.
// `back` is the view's way out: a Back button that Escape also takes.
function Header({ project, right, ro, title, back, backExit, extra }) {
  const auto = usePageTitle(project)
  const name = title === undefined ? auto : title
  return h('div', 'flex flex-wrap items-center justify-between gap-2',
    h('div', 'flex items-center gap-2 min-w-0',
      h('button', {
        type: 'button',
        className: 'inline-flex items-center min-h-[24px] text-xs font-semibold text-muted hover:text-fg mono',
        'data-testid': 'project-name',
        title: 'Needs you',
        'aria-label': `${project}, Needs you`,
        onClick: () => navigate('projects')
      }, project),
      name ? h('span', { className: 'text-line', 'aria-hidden': 'true' }, '/') : null,
      name ? h('h1', { className: 'text-xl font-bold tracking-tight text-fg truncate', title: name, 'data-page-title': '1', tabIndex: -1 }, name) : null),
    h('div', 'flex flex-wrap items-center gap-2',
      back ? h(ExitBtn, { kind: 'head', testid: 'page-back', onClick: back, exit: backExit !== false }, 'Back') : null,
      h(DockToggle),
      h('button', {
        type: 'button', 'data-testid': 'open-settings',
        className: HEAD_BTN,
        onClick: () => navigate('settings')
      }, 'Settings'),
      ro ? h(Badge, { status: 'read_only', testid: 'read-only' }) : null,
      ro ? null : extra,
      right === undefined && !ro
        ? h('button', {
          type: 'button',
          className: HEAD_BTN,
          onClick: () => navigate('need-new')
        }, 'New need')
        : ro ? null : right))
}

function DockToggle() {
  const open = useValue($dockOpen)
  return h('button', {
    type: 'button', 'aria-pressed': open ? 'true' : 'false', 'data-testid': 'dock-toggle',
    className: cx('inline-flex items-center min-h-[24px] px-2 py-0.5 rounded text-[11px] font-medium border', open ? 'bg-needs/10 text-needs border-needs/30' : 'bg-card border-line text-muted hover:text-fg'),
    onClick: () => setDock(!open)
  }, 'Dock')
}

function Tile({ label, value, of, t, hot, testid }) {
  return h('div', {
    className: cx('rounded-[6px] p-3 flex flex-col justify-between', hot ? 'border-2 border-needs bg-needs/10' : 'bg-card border border-line'),
    'data-testid': testid
  },
  h('span', { className: cx('text-[11px]', hot ? 'font-semibold text-needs' : 'font-medium text-muted') }, label),
  h('div', 'flex items-baseline gap-1.5 mt-1',
    h('span', { className: cx('text-2xl font-bold', TONE_TEXT[t] || 'text-fg'), 'data-testid': testid && testid + '-value' }, String(value)),
    of != null ? h('span', 'text-xs text-muted', `of ${of}`) : null))
}

function Tiles({ tiles }) {
  const t = tiles || { covered: 0, requirements: 0, stale: 0, failing: 0, needs_you: 0 }
  const all = t.requirements > 0 && t.covered === t.requirements
  return h('div', 'r-tiles grid grid-cols-4 gap-3',
    all
      ? h('div', { className: 'bg-card border-2 border-pass rounded-[6px] p-3 flex flex-col justify-between', 'data-testid': 'tile-covered' },
        h('span', 'text-[11px] font-semibold text-pass', 'Checks satisfied'),
        h('div', 'flex items-baseline gap-1.5 mt-1',
          h('span', { className: 'text-2xl font-bold text-pass', 'data-testid': 'tile-covered-value' }, String(t.covered)),
          h('span', 'text-xs text-muted', `of ${t.requirements}`)))
      : h(Tile, { label: 'Checks satisfied', value: t.covered, of: t.requirements, testid: 'tile-covered' }),
    h(Tile, { label: 'Stale', value: t.stale, t: t.stale ? 'stale' : null, testid: 'tile-stale' }),
    h(Tile, { label: 'Failing', value: t.failing, t: t.failing ? 'fail' : null, testid: 'tile-failing' }),
    h(Tile, { label: 'Needs you', value: t.needs_you, t: t.needs_you ? 'needs' : null, hot: t.needs_you > 0, testid: 'tile-needs-you' }))
}

// ------------------------------------------------------------------ build strip

const STEPS = ['Need', 'Requirements', 'Specifications', 'Tests', 'Develop']
const STEP_VIEWS = ['need', 'reqs', 'specs', 'tests', 'develop']

function Strip({ current, reached, need, done: doneList }) {
  // current: 0..4, reached: highest unlocked index, done: per-step completion from the engine
  const kids = []
  STEPS.forEach((name, i) => {
    const done = doneList ? !!doneList[i] && i !== current : i < current && i <= reached
    const on = i === current
    const locked = i > reached
    if (i > 0) kids.push(h('div', { key: 'l' + i, className: cx('flex-1 h-[1px] mx-2 min-w-2', i <= Math.min(current, reached) ? 'bg-pass' : 'bg-line') }))
    kids.push(h('div', {
      key: 's' + i,
      className: cx('flex items-center gap-2 shrink-0 rs-step', on && 'rs-on', locked ? 'cursor-not-allowed' : 'cursor-pointer'),
      'data-step': name, title: name, 'aria-label': done ? `${name}, done` : locked ? `${name}, locked` : name, 'data-locked': locked ? '1' : undefined, 'aria-disabled': locked ? 'true' : undefined,
      'aria-current': on ? 'step' : undefined, tabIndex: locked ? -1 : 0,
      onClick: () => {
        if (locked) return
        if (i === 0) navigate(need ? 'rung' : 'need-new', need ? { rid: need } : null)
        else navigate('build', { need, step: STEP_VIEWS[i] })
      }
    },
    done
      ? h('span', 'w-5 h-5 rounded-full bg-pass text-on-pass flex items-center justify-center text-[11px] font-bold', '✓')
      : on
        ? h('span', 'w-5 h-5 rounded-full border-2 border-needs bg-needs/10 text-needs flex items-center justify-center text-[10px] font-bold', String(i + 1))
        : h('span', 'w-5 h-5 rounded-full border border-line text-dim flex items-center justify-center text-[10px] font-medium', String(i + 1)),
    h('span', { className: cx('text-xs whitespace-nowrap rs-label', done ? 'font-semibold text-pass' : on ? 'font-semibold text-needs' : 'font-medium text-dim') }, name)))
  })
  return h('nav', { className: 'rs-strip flex flex-wrap items-center justify-between gap-y-2 bg-card border border-line rounded-[6px] px-6 py-3', 'data-testid': 'build-strip', 'aria-label': 'Build steps' }, ...kids)
}

// ------------------------------------------------------------------ traceability rail

function TreeTest({ n, sel }) {
  const t = tone(n)
  return h('div', {
    className: cx('pl-3 ml-0.5 py-1 border-l border-line flex items-center gap-1.5 cursor-pointer', sel === n.id && 'bg-needs/10 rounded'),
    'aria-current': sel === n.id ? 'page' : undefined,
    'data-rung': n.id, 'data-tone': t, 'data-label': rungLabel(n),
    onClick: () => navigate('rung', { rid: n.id })
  },
  h(Dot, { t }),
  h('span', { className: cx('text-[10px] mono', TONE_TEXT[t]) }, `${n.id} ${n.status === 'stale' ? 'stale' : resultWord(n.result)}`))
}

function TreeSpec({ n, sel, hl }) {
  const t = tone(n)
  const on = hl === n.id
  const tests = (n.children || []).filter(c => c.status !== 'dismissed' && c.status !== 'proposed')
  const sub = [n.text, n.carried_by].filter(Boolean).join(' · ') + (tests.length ? '' : n.status === 'draft' ? '' : ' · no tests yet')
  return h('div', { className: cx('pl-3 ml-0.5 border-l border-line flex flex-col gap-1 mt-0.5', on && 'bg-needs/5 p-1 rounded') },
    h('div', { className: cx('flex items-start gap-1.5 cursor-pointer', sel === n.id && 'bg-needs/10 rounded'), 'aria-current': sel === n.id ? 'page' : undefined, 'data-rung': n.id, 'data-tone': t, 'data-label': rungLabel(n), onClick: () => navigate('rung', { rid: n.id }) },
      h('span', { className: cx('w-1.5 h-1.5 mt-1 rounded-full shrink-0', TONE_BG[t]), title: labelText(rungLabel(n)) }),
      h('div', 'flex flex-col min-w-0',
        h('span', { className: cx('whitespace-nowrap text-[11px]', on ? 'font-semibold text-needs' : t === 'dim' ? 'text-dim' : 'text-fg') }, n.id),
        h('span', 'sr-only', labelText(rungLabel(n))),
        h('span', { className: cx('text-[10px] truncate', t === 'dim' ? 'text-dim' : 'text-muted'), title: typeof sub === 'string' ? sub : undefined }, sub))),
    ...tests.map(c => h(TreeTest, { key: c.id, n: c, sel })))
}

function TreeReq({ n, sel, hl }) {
  const t = tone(n)
  const specs = (n.children || []).filter(c => c.status !== 'dismissed' && c.status !== 'proposed')
  return h('div', 'flex flex-col gap-1',
    h('div', { className: cx('flex items-start gap-1.5 cursor-pointer', sel === n.id && 'bg-needs/10 rounded'), 'aria-current': sel === n.id ? 'page' : undefined, 'data-rung': n.id, 'data-tone': t, 'data-label': rungLabel(n), onClick: () => navigate('rung', { rid: n.id }) },
      h('span', { className: cx('w-1.5 h-1.5 mt-1 rounded-full shrink-0', TONE_BG[t]), title: labelText(rungLabel(n)) }),
      h('div', 'flex flex-col min-w-0',
        h('span', { className: cx('whitespace-nowrap font-medium', t === 'dim' ? 'text-dim' : 'text-fg') }, n.id),
        h('span', 'sr-only', labelText(rungLabel(n))),
        h('span', { className: cx('text-[11px]', t === 'dim' ? 'text-dim' : 'text-muted') }, n.text))),
    ...specs.map(c => h(TreeSpec, { key: c.id, n: c, sel, hl })))
}

function TreeNeed({ n, sel, hl }) {
  const t = tone(n)
  const reqs = (n.children || []).filter(c => c.status !== 'dismissed' && c.status !== 'proposed')
  return h('div', 'flex flex-col gap-1.5 text-xs',
    h('div', { className: cx('flex items-start gap-2 cursor-pointer', sel === n.id && 'bg-needs/10 rounded'), 'aria-current': sel === n.id ? 'page' : undefined, 'data-rung': n.id, onClick: () => navigate('rung', { rid: n.id }) },
      h('span', { className: cx('w-2 h-2 mt-1 rounded-full shrink-0', TONE_BG[t]), title: labelText(rungLabel(n)) }),
      h('div', 'flex flex-col min-w-0',
        h('span', 'whitespace-nowrap font-semibold text-fg', n.id),
        h('span', 'sr-only', labelText(rungLabel(n))),
        h('span', 'text-[11px] text-muted leading-tight', n.text))),
    reqs.length ? h('div', 'pl-4 ml-1 border-l border-line flex flex-col gap-3 mt-1.5', ...reqs.map(c => h(TreeReq, { key: c.id, n: c, sel, hl }))) : null)
}

// Score parts (decisions Round 24, R11): each part is focusable and says what it measures on focus and hover,
// from the engine's own words. The visible text keeps its short form.
const PART_HELP_FALLBACK = {}
function ScoreParts({ parts, help, short, className }) {
  const hp = help || PART_HELP_FALLBACK
  const names = [['tags', 'tags'], ['load', 'load'], ['reliability', 'history'], ['cost', short ? 'cost pref' : 'cost preference']]
  return h('span', { className: cx('mono', className), 'data-testid': 'score-parts' },
    ...names.flatMap(([k, label], i) => [
      i ? h('span', { key: k + '-sep', 'aria-hidden': 'true' }, ' · ') : null,
      h('span', { key: k, tabIndex: 0, className: 'r-part rounded', 'data-part': k, title: hp[k] || '', 'aria-label': `${label} ${parts[k]}: ${hp[k] || ''}` }, `${label} ${parts[k]}`)]).filter(Boolean))
}

function WhyLine({ why }) {
  if (!why || !why.length) return null
  return h('span', { className: 'text-[10px] text-muted leading-tight', 'data-testid': 'why-fits' }, why.join(' · '))
}

function Allocation({ alloc }) {
  if (!alloc) return null
  const rows = alloc.suggestions || []
  const picked = alloc.pick && alloc.pick.profile
  const lead = picked || (rows[0] && rows[0].profile) || ''
  return h('div', 'flex flex-col gap-3 pt-3 border-t border-line',
    h('div', 'flex items-center justify-between pb-1',
      h('h3', { className: 'text-xs font-semibold tracking-wider uppercase text-muted', title: 'Settings', 'aria-label': `Allocation: ${alloc.spec}, Settings`, onClick: () => navigate('settings') }, `Allocation: ${alloc.spec}`),
      h('span', 'text-[11px] mono text-needs', lead)),
    alloc.human_only
      ? h('div', 'flex flex-col gap-2', h('div', 'text-[11px] text-muted', alloc.human_only_reason === 'marked' ? 'Human only' : 'Manual tests only: a person carries this'))
      : h('div', 'flex flex-col gap-2.5',
        ...rows.map((r, i) => i === 0
          ? h('div', { key: r.profile, className: 'flex flex-col gap-1 bg-btn p-2.5 rounded-[6px] border border-line', 'data-alloc': r.profile },
            h('div', 'flex items-center justify-between text-xs',
              h('span', 'font-semibold text-fg', r.profile),
              h('span', 'font-bold text-needs mono', String(r.score))),
            h('div', 'text-[10px] text-muted leading-tight', h(ScoreParts, { parts: r.parts, help: alloc.parts_help })),
            h(WhyLine, { why: r.why }),
            h('div', 'w-full h-1 bg-well rounded-full overflow-hidden mt-0.5',
              h('div', { className: 'h-full bg-needs rounded-full', style: { width: `${Math.min(100, r.score)}%` } })))
          : h('div', { key: r.profile, className: 'flex flex-col gap-1 bg-card p-2 rounded-[6px] border border-line2', 'data-alloc': r.profile },
            h('div', 'flex items-center justify-between text-xs',
              h('span', 'text-muted', r.profile),
              h('span', 'text-muted mono', String(r.score))),
            h('div', 'w-full h-1 bg-well rounded-full overflow-hidden mt-0.5',
              h('div', { className: 'h-full bg-dim rounded-full', style: { width: `${Math.min(100, r.score)}%` } }))))),
    h(ExcludedList, { excluded: alloc.excluded, testid: 'rail-excluded' }))
}

function Rail({ tree, alloc, sel, retired }) {
  const needs = (tree || []).filter(n => n.status !== 'dismissed')
  const head = needs[0]
  return h('aside', { className: 'w-[280px] min-w-[280px] max-w-[280px] h-full border-l border-line2 bg-card overflow-y-auto px-4 py-6 flex flex-col gap-6', 'data-testid': 'rail' },
    h('div', 'flex flex-col gap-3',
      h('div', 'flex items-center justify-between pb-1.5 border-b border-line',
        h('h3', 'text-xs font-semibold tracking-wider uppercase text-muted', 'Traceability Tree'),
        head ? h('span', { className: cx('text-[11px]', TONE_TEXT[tone(head)]) }, head.status) : null),
      needs.length
        ? h('nav', { className: 'flex flex-col gap-4', 'aria-label': 'Traceability tree' }, ...needs.map(n => h(TreeNeed, { key: n.id, n, sel, hl: alloc && alloc.spec })))
        : h('div', 'text-[11px] text-muted', 'No needs yet'),
      retired ? h('button', { type: 'button', className: 'self-start text-[11px] text-muted hover:text-fg', 'data-testid': 'retired-link', onClick: () => navigate('retired') }, `Retired ${retired}`) : null),
    h(Allocation, { alloc }))
}

// ------------------------------------------------------------------ page frame

// The main column and its rail side by side; on a narrow pane (r-frame's container query) the rail follows the
// main column and the whole frame scrolls (NAV-14).
function Frame({ main, rail, wide, quiet }) {
  return h('div', 'r-frame h-full w-full',
    h('div', 'r-frame-in flex flex-row h-full w-full overflow-hidden',
      h('section', { className: cx('r-main flex-1 h-full overflow-y-auto px-8 py-6 flex flex-col gap-6', !wide && 'max-w-[860px]'), 'data-testid': 'main' }, h(Notice), quiet ? null : h(LoadErrors), main),
      rail || null))
}

// A failed read of the project state or the settings, on every view, with the project (NAV-17): a view
// showing what it loaded before still says that the latest load failed. Reads the shared queries, never fetches.
function LoadErrors() {
  const a = useApi('/state', { enabled: false })
  const b = useApi('/settings', { enabled: false })
  const e = a.error || b.error
  if (!e) return null
  return h('div', { className: 'flex flex-wrap items-center gap-2', 'data-testid': 'load-error' },
    h(ErrorLine, { text: `${CUR_PROJECT ? CUR_PROJECT + ': ' : ''}${errText(e)}` }),
    h(Btn, { kind: 'small', testid: 'load-retry', onClick: () => { a.refetch(); b.refetch() } }, 'Retry'))
}

// A folder: the typed path, and Choose for the host's folder picker when this Hermes has one (never a button
// that does nothing). A failed pick says so under the field; cancel changes nothing.
function FolderInput({ value, onChange, onPicked, invalid, className, 'aria-label': named }) {
  const [err, setErr] = useState('')
  const choose = async () => {
    setErr('')
    try {
      const p = await pickFolder(value)
      if (p) onPicked(p)
    } catch (x) { setErr(errText(x)) }
  }
  return h('div', 'flex flex-col gap-1',
    h('div', 'flex items-center gap-2',
      h('input', { className: cx(className, 'font-mono flex-1 min-w-0'), type: 'text', name: 'folder', 'aria-label': named || 'Folder', 'aria-invalid': invalid ? 'true' : undefined,
        value, onChange: e => onChange(e.target.value), onBlur: e => onChange(e.target.value, true) }),
      canPickFolder() ? h(Btn, { kind: 'secondary', testid: 'choose-folder', onClick: choose, className: 'py-2 whitespace-nowrap' }, 'Choose folder') : null),
    err ? h('span', { className: 'text-[11px] text-fail', role: 'alert', 'data-testid': 'choose-error' }, err) : null)
}
FolderInput.labelled = true

// What the last action did (created, saved, raised), on the view it landed on.
function Notice() {
  const n = useValue($notice)
  // Always in the page, so screen readers announce the line when it appears.
  return h('div', { role: 'status', 'data-testid': 'notice', className: 'text-xs text-pass font-medium', style: n ? undefined : { position: 'absolute', width: 1, height: 1, overflow: 'hidden' } }, n || '')
}

// A destination that does not exist (a missing id, a failed load, an unknown view): what is missing, and a way on.
// What is missing, as a sentence: the engine's refusal (`no S-99.9 in csvtidy`) names the kind from the id.
const ID_KIND = { N: 'Need', R: 'Requirement', S: 'Specification', T: 'Test' }
function missingText(text) {
  const t = String(text || '')
  let m = t.match(/^no ([NRST])-(\S+) in (.+)$/)
  if (m) return `${ID_KIND[m[1]]} ${m[1]}-${m[2]} is not in ${m[3]}`
  m = t.match(/^no (\w+) (\S+) in (\w+) (\S+)$/)
  if (m) return `${m[1][0].toUpperCase() + m[1].slice(1)} ${m[2]} is not in ${m[3]} ${m[4]}`
  m = t.match(/^no execution #(\d+) of (\S+)$/)
  if (m) return `Execution ${m[2]} #${m[1]} does not exist`
  m = t.match(/^no (\w+) (\S+)$/)
  if (m) return `${m[1][0].toUpperCase() + m[1].slice(1)} ${m[2]} does not exist`
  return t ? t[0].toUpperCase() + t.slice(1) : 'Not found'
}

// A button that is also the view's Escape action (Back, Back to X, Cancel).
// An empty list or section: what is missing, and the one action that fills it (FST-04).
function Empty({ text, action, onClick, testid, actionTestid }) {
  return h('div', { className: 'bg-well border border-line2 rounded-[6px] p-2.5 flex flex-wrap items-center justify-between gap-2 text-xs', 'data-testid': 'empty-state' },
    h('span', { className: 'text-muted', 'data-testid': testid || undefined }, text),
    action && onClick ? h(Btn, { kind: 'small', testid: actionTestid, onClick }, action) : null)
}

function ExitBtn({ onClick, exit, children, ...rest }) {
  useExit(exit === false ? null : onClick)
  return h(Btn, { ...rest, onClick }, children)
}

// A missing id says so; anything else is a load that failed, and Retry may cure it.
function isNotFound(text) { return /^(no |not found|unknown |page not found)| is archived$/i.test(String(text || '')) }

function Missing({ project, text, name }) {
  // Back never falls back to the page that failed: a failed Home goes on to Needs you.
  const cur = ($nav.get() || {}).view
  const back = () => goBack(project && cur !== 'home' ? 'home' : 'projects')
  useExit(back, false, true)
  // The sentence and the way on, alone: no tiles or rail of a project the person did not ask for.
  const body = h(Card, { className: 'p-4 flex flex-col gap-3', testid: 'missing' },
    h('div', { role: 'alert' }, h('h1', { className: 'text-xl font-bold tracking-tight text-fg', 'data-page-title': '1', tabIndex: -1 }, (isNotFound(text) && name) || missingText(text))),
    h('div', 'flex items-center gap-2',
      h(Btn, { kind: 'primary', testid: 'missing-back', onClick: back }, 'Back'),
      isNotFound(text) ? null : h(Btn, { testid: 'missing-retry', onClick: () => refresh() }, 'Retry'),
      project ? h(Btn, { testid: 'missing-home', onClick: () => navigate('home', null, { replace: true }) }, 'Home') : null,
      h(Btn, { testid: 'missing-projects', onClick: () => navigate('projects', null, { replace: true }) }, 'Projects')))
  return h(Frame, { main: frag(project ? h('header', null, h(Header, { project, title: null })) : null, body), quiet: true })
}

function Loading() {
  return h('div', { className: 'p-8 text-xs text-muted', role: 'status' }, 'Loading')
}

function ErrorLine({ text }) {
  if (!text) return null
  return h('div', { className: 'text-xs text-fail', 'data-testid': 'error', role: 'alert' }, text)
}
