// Rung desktop pane: shared project page frame, the build flow (Need, Requirements, Specifications, Tests, Develop).

function useTick(ms) {
  const [, set] = useState(0)
  useEffect(() => {
    const t = setInterval(() => set(x => x + 1), ms || 1000)
    return () => clearInterval(t)
  }, [ms])
}

function useHome(project, focus) {
  return useApi(`/projects/${encodeURIComponent(project)}/home${focus ? `?focus=${encodeURIComponent(focus)}` : ''}`)
}

function Page({ project, focus, sel, children, noTiles }) {
  const q = useHome(project, focus || sel)
  const d = q.data
  const main = frag(
    h('header', 'flex flex-col gap-4', h(Header, { project }), noTiles ? null : h(Tiles, { tiles: d && d.tiles })),
    children)
  return h(Frame, { main, rail: h(Rail, { tree: d && d.tree, alloc: d && d.allocation, sel: sel || focus }) })
}

function Crumbs({ path, last, lastTone }) {
  const kids = []
  for (const p of path || []) {
    kids.push(h('span', { key: p.id, className: 'cursor-pointer hover:text-fg', onClick: e => { e.stopPropagation(); navigate('rung', { rid: p.id }) } }, p.id))
    kids.push(h('span', { key: p.id + '›' }, '›'))
  }
  kids.push(h('span', { key: 'last', className: lastTone || 'text-needs' }, last))
  return h('div', { className: 'text-[11px] mono text-muted font-medium flex items-center gap-1.5', 'data-testid': 'crumbs' }, ...kids)
}

function useRung(project, rid) {
  return useApi(rid ? `/projects/${encodeURIComponent(project)}/rungs/${encodeURIComponent(rid)}` : null, { enabled: !!rid })
}

function useFlow(project, need) {
  return useApi(need ? `/projects/${encodeURIComponent(project)}/needs/${encodeURIComponent(need)}/flow` : null, { enabled: !!need })
}

const P = project => `/projects/${encodeURIComponent(project)}`

function stripState(flow) {
  if (!flow) return { reached: 0 }
  const order = ['need', 'requirements', 'specifications', 'tests', 'develop']
  let reached = 0
  order.forEach((k, i) => { if (flow.steps[k].available) reached = i })
  return { reached, done: order.map(k => flow.steps[k].done) }
}

function BuildStrip({ need, flow, current }) {
  const st = stripState(flow)
  return h(Strip, { current, reached: need ? st.reached : 0, need, done: st.done })
}

function Seg({ options, value, onChange, testid, big }) {
  return h('div', { className: big ? 'inline-flex p-0.5 bg-well border border-line2 rounded-[6px] w-fit' : 'inline-flex p-0.5 rounded bg-well border border-line text-[11px]', 'data-testid': testid, role: 'radiogroup' },
    ...options.map(([v, label]) => {
      const on = v === value
      const cls = big
        ? (on ? 'px-3 py-1 rounded text-xs font-semibold bg-needs text-on-needs' : 'px-3 py-1 rounded text-xs font-medium text-muted')
        : (on ? 'px-2 py-0.5 rounded bg-btnh text-fg font-medium border border-line' : 'px-2 py-0.5 text-muted border border-transparent')
      return h('button', { key: v, type: 'button', role: 'radio', 'aria-checked': on ? 'true' : 'false', className: cls, onClick: e => { e.stopPropagation(); if (!on) onChange(v) } }, label)
    }))
}

// ------------------------------------------------------------------ step 1: Need

function NeedNew({ project }) {
  const [text, setText] = useState('')
  const [sugs, setSugs] = useState([])
  const [marks, setMarks] = useState({})
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const seq = useRef(0)
  useEffect(() => {
    const t = text.trim()
    if (t.length < 8) { setSugs([]); return }
    const my = ++seq.current
    const timer = setTimeout(async () => {
      setBusy(true)
      try {
        const r = await rest(`${P(project)}/needs/suggest`, { method: 'POST', body: { text: t } })
        if (my === seq.current) { setSugs(r.suggestions || []); setMarks({}) }
      } catch (e) {
        if (my === seq.current) setErr(errText(e))
      } finally {
        if (my === seq.current) setBusy(false)
      }
    }, 450)
    return () => clearTimeout(timer)
  }, [text])
  const create = async () => {
    const accepted = sugs.filter(s => marks[s] === 'accepted')
    const res = await post(`${P(project)}/needs`, { text: text.trim(), requirements: accepted })
    if (!res.ok) return setErr(res.error)
    navigate('build', { need: res.data.id, step: 'reqs' })
  }
  const body = h('div', 'flex flex-col gap-6',
    h(BuildStrip, { need: null, flow: null, current: 0 }),
    h('div', 'flex flex-col gap-2',
      h('label', 'text-xs font-semibold uppercase tracking-wider text-fg', 'Need'),
      h('textarea', {
        className: 'bg-card border border-line rounded-[6px] px-4 py-3 text-xs font-medium text-fg resize-none focus:border-needs outline-none',
        rows: 2, name: 'need', value: text, autoFocus: true, onChange: e => setText(e.target.value)
      })),
    sugs.length || busy ? h('section', { className: 'flex flex-col gap-2.5', 'data-testid': 'suggested' },
      h('div', 'flex items-center justify-between',
        h('h2', 'text-xs font-semibold uppercase tracking-wider text-fg', 'Suggested requirements'),
        busy ? h('span', 'text-[11px] text-needs', 'Drafting') : null),
      h('div', 'flex flex-col gap-2', ...sugs.map(s => h(SuggestRow, {
        key: s, text: s, mark: marks[s],
        onAccept: () => setMarks({ ...marks, [s]: 'accepted' }),
        onDismiss: () => setMarks({ ...marks, [s]: 'dismissed' })
      })))) : null,
    h(ErrorLine, { text: err }),
    h('div', 'flex items-center justify-between pt-2 border-t border-line',
      h('div', 'flex items-center gap-2',
        h(Btn, { kind: 'primaryLg', testid: 'create-need', disabled: !text.trim(), onClick: create }, 'Create need'),
        h(Btn, { kind: 'quiet', onClick: () => navigate('home') }, 'Cancel'))))
  return h(Page, { project }, body)
}

function SuggestRow({ text, mark, onAccept, onDismiss, well }) {
  const done = mark === 'dismissed'
  return h('div', {
    className: cx(well ? 'bg-well border border-line2' : 'bg-card border border-line', 'rounded-[6px] px-3.5 py-2.5 flex items-center justify-between', done && 'opacity-40 line-through'),
    'data-suggestion': text, 'data-mark': mark || 'open'
  },
  h('div', 'flex items-center gap-3',
    h('span', 'w-1.5 h-1.5 rounded-full bg-needs'),
    h('span', 'text-xs text-fg', text)),
  h('div', 'flex items-center gap-2',
    h(Btn, { kind: 'accept', disabled: !!mark, onClick: onAccept }, mark === 'accepted' ? 'Accepted' : 'Accept'),
    h(Btn, { kind: 'ghost', disabled: !!mark, onClick: onDismiss }, mark === 'dismissed' ? 'Dismissed' : 'Dismiss')))
}

// ------------------------------------------------------------------ build router

function Build({ project, need, step }) {
  const flowQ = useFlow(project, need)
  const flow = flowQ.data
  const idx = { need: 0, reqs: 1, specs: 2, tests: 3, develop: 4 }[step] ?? 1
  const key = ['need', 'requirements', 'specifications', 'tests', 'develop'][idx]
  if (!flow) return h(Page, { project }, h(Loading))
  if (!flow.steps[key].available) {
    // A locked step can not be reached by URL either: show the step that is open.
    const open = ['need', 'requirements', 'specifications', 'tests', 'develop'].filter(k => flow.steps[k].available).pop()
    return h(Page, { project }, h('div', 'flex flex-col gap-6',
      h(BuildStrip, { need, flow, current: idx }),
      h(Card, { className: 'p-4 text-xs text-muted', testid: 'locked-step' }, `The ${STEPS[idx]} step is locked`),
      h('div', null, h(Btn, { onClick: () => navigate('build', { need, step: STEP_VIEWS[['need', 'requirements', 'specifications', 'tests', 'develop'].indexOf(open)] }) }, 'Back'))))
  }
  const props = { project, need, flow }
  if (idx === 1) return h(StepReqs, props)
  if (idx === 2) return h(StepSpecs, props)
  if (idx === 3) return h(StepTests, props)
  if (idx === 4) return h(StepDevelop, props)
  return h(VIEWS.rung, { project, rid: need })
}

function NeedRow({ n }) {
  return h('div', { className: 'flex items-center justify-between bg-card border border-line rounded-[6px] px-4 py-3 cursor-pointer', onClick: () => navigate('rung', { rid: n.id }), 'data-testid': 'need-row' },
    h('div', 'flex items-center gap-3',
      h('span', 'font-mono text-xs font-semibold text-fg', n.id),
      h('span', 'text-line', '·'),
      h('span', 'text-xs font-medium text-fg', n.text)),
    h(Badge, { status: n.status }))
}

// ------------------------------------------------------------------ step 2: Requirements

function StepReqs({ project, need, flow }) {
  const q = useRung(project, need)
  const n = q.data
  const [err, setErr] = useState('')
  if (!n) return h(Page, { project }, h(Loading))
  const reqs = (n.children || []).filter(r => r.status !== 'dismissed' && r.status !== 'proposed')
  const st = flow.steps.requirements
  const approveAll = async () => {
    const r = await post(`${P(project)}/needs/${need}/approve-requirements`)
    if (!r.ok) return setErr(r.error)
    navigate('build', { need, step: 'specs' })
  }
  const body = h('div', 'flex flex-col gap-6',
    h(BuildStrip, { need, flow, current: 1 }),
    h(NeedRow, { n }),
    h('section', { className: 'flex flex-col gap-2.5', 'data-testid': 'requirements' },
      h('div', 'flex items-center justify-between',
        h('h2', 'text-xs font-semibold uppercase tracking-wider text-fg', 'Requirements'),
        h('span', 'text-[11px] text-muted', `${reqs.length} defined`)),
      h('div', 'flex flex-col gap-2',
        ...reqs.map(r => h('div', { key: r.id, className: 'bg-card border border-line rounded-[6px] px-3.5 py-2.5 flex items-center justify-between', 'data-req': r.id },
          h('div', 'flex items-center gap-3',
            h('span', 'font-mono text-xs font-medium text-muted', r.id),
            h('span', { className: 'text-xs text-fg', 'data-testid': 'req-text' }, r.text)),
          h('div', 'flex items-center gap-2.5',
            h(Badge, { status: r.status, small: true }),
            h(Btn, { kind: 'ghost', onClick: () => navigate('rung', { rid: r.id, ret: 'reqs', need }) }, r.status === 'stale' ? 'Review' : 'Edit')))))),
    (n.suggestions || []).length ? h('section', { className: 'flex flex-col gap-2.5', 'data-testid': 'suggested' },
      h('div', 'flex items-center justify-between', h('h2', 'text-xs font-semibold uppercase tracking-wider text-muted', 'Suggested')),
      ...n.suggestions.map(s => h(SuggestRow, {
        key: s.id, text: s.text,
        onAccept: async () => { const r = await post(`${P(project)}/suggestions/${s.id}`, { accept: true }); setErr(r.ok ? '' : r.error) },
        onDismiss: async () => { const r = await post(`${P(project)}/suggestions/${s.id}`, { accept: false }); setErr(r.ok ? '' : r.error) }
      }))) : null,
    h(ErrorLine, { text: err }),
    h('div', 'flex items-center justify-between pt-2 border-t border-line',
      h(Btn, { kind: 'outline', testid: 'new-requirement', onClick: () => navigate('req-new', { need, ret: 'reqs' }) }, 'New requirement'),
      h('div', 'flex items-center gap-2',
        h(Btn, { kind: 'primaryLg', testid: 'approve-all', disabled: !st.can_approve || st.done, title: st.blocked_by || '', onClick: approveAll }, 'Approve all'),
        h(Btn, { disabled: !st.done, title: st.blocked_by || '', onClick: () => navigate('build', { need, step: 'specs' }) }, 'Next'))))
  return h(Page, { project }, body)
}

// ------------------------------------------------------------------ step 3: Specifications

function draftBadge(spec) {
  if (!spec) return null
  if (spec.draft_state === 'drafting') return 'drafting'
  if (spec.status === 'approved') return 'approved'
  if (spec.status === 'stale') return 'stale'
  if (spec.draft_state === 'failed') return 'failed'
  return spec.text ? 'drafted' : null
}

function StepSpecs({ project, need, flow }) {
  const q = useRung(project, need)
  const n = q.data
  const [err, setErr] = useState('')
  if (!n) return h(Page, { project }, h(Loading))
  const reqs = (n.children || []).filter(r => r.status === 'approved' || r.status === 'stale')
  const st = flow.steps.specifications
  const setMode = async (r, mode) => {
    const res = await post(`${P(project)}/rungs/${r.id}/authoring`, { mode })
    setErr(res.ok ? '' : res.error)
  }
  const approve = async () => {
    const res = await post(`${P(project)}/needs/${need}/approve-drafted`)
    if (!res.ok) return setErr(res.error)
    navigate('build', { need, step: 'tests' })
  }
  const body = h('div', 'flex flex-col gap-5',
    h(BuildStrip, { need, flow, current: 2 }),
    h('div', { className: 'flex flex-col gap-3', 'data-testid': 'spec-step' },
      ...reqs.map(r => {
        const specs = (r.children || []).filter(s => s.status !== 'dismissed' && s.status !== 'proposed')
        const mode = r.authoring || (specs.length ? (specs[0].author_role === 'human' ? 'human' : 'ai') : null)
        return h('div', { key: r.id, className: 'bg-card border border-line rounded-[6px] p-3.5 flex flex-col gap-3', 'data-req': r.id },
          h('div', 'flex items-center justify-between',
            h('div', 'flex items-center gap-2',
              h('span', 'text-xs font-semibold mono text-fg', r.id),
              h('span', 'text-xs text-fg', r.text)),
            h(Seg, { options: [['ai', 'AI derives'], ['human', 'I write, AI supports']], value: mode, testid: 'authoring', onChange: v => setMode(r, v) })),
          specs.length && specs.some(s => s.text || s.draft_state === 'drafting')
            ? frag(...specs.map(s => h('div', { key: s.id, className: 'flex items-center justify-between pt-2 border-t border-line2', 'data-spec': s.id },
              h('div', 'flex items-center gap-2 text-xs',
                h('span', 'mono text-muted', s.text ? `${s.id} ${s.text}` : s.id),
                draftBadge(s) ? h(Badge, { status: draftBadge(s), small: true }) : null),
              s.draft_state === 'drafting' ? null : h(Btn, { kind: 'small', onClick: () => navigate('rung', { rid: s.id, ret: 'specs', need }) }, 'Open'))))
            : mode === 'human'
              ? h('div', 'flex items-center justify-end pt-2 border-t border-line2',
                h(Btn, { kind: 'small', testid: 'write', onClick: () => navigate('spec-edit', { req: r.id, ret: 'specs', need }) }, 'Write'))
              : mode === 'ai'
                ? h('div', 'flex items-center gap-2 pt-2 border-t border-line2 text-xs', h(Badge, { status: 'drafting', small: true }))
                : null)
      })),
    h(ErrorLine, { text: err }),
    h('div', 'flex items-center gap-2.5 pt-1',
      h(Btn, { kind: 'primaryLg', testid: 'approve-drafted', disabled: !st.can_approve || st.done, title: st.blocked_by || '', onClick: approve }, 'Approve drafted'),
      h(Btn, { disabled: !st.done, title: st.blocked_by || '', onClick: () => navigate('build', { need, step: 'tests' }) }, 'Next')))
  return h(Page, { project }, body)
}

// ------------------------------------------------------------------ step 4: Tests

function passRule(t) {
  if (t.type === 'manual') return ''
  const pr = t.pass_rule || { kind: 'exit_code', value: 0 }
  const rule = pr.kind === 'output_contains' ? `output contains ${pr.value}` : `exit code ${pr.value}`
  return `${rule} · timeout ${t.timeout || 120}s`
}

const TYPE_WORD = { command: 'Command test', manual: 'Manual test', ai_judged: 'AI judged test' }

function TestRow({ project, t, need, ret, onErr }) {
  const accepted = t.status === 'approved' || t.status === 'stale'
  return h('div', { className: 'bg-well border border-line2 rounded-[6px] p-3 flex items-center justify-between', 'data-test': t.id, 'data-status': t.status },
    h('div', 'flex flex-col gap-1',
      h('div', 'flex items-center gap-2',
        h('span', 'text-xs font-medium mono text-fg', t.id),
        h('span', { className: cx('text-xs text-fg', t.type !== 'manual' && 'font-mono'), 'data-testid': 'test-command' }, t.type === 'manual' ? t.text : (t.command || t.text)),
        h('span', 'px-1.5 py-0.5 rounded text-[10px] font-medium bg-btn text-muted border border-line', TYPE_WORD[t.type] || 'Command test')),
      t.type !== 'manual' ? h('div', { className: 'text-[11px] mono text-muted', 'data-testid': 'pass-rule' }, passRule(t)) : null,
      t.type === 'ai_judged' ? h('div', { className: 'text-[11px] text-dim', 'data-testid': 'no-gate' }, 'Cannot release a gate') : null),
    h('div', 'flex items-center gap-2',
      accepted
        ? h('span', { className: 'px-2.5 py-1 text-xs font-medium text-pass', 'data-testid': 'accepted' }, 'Accepted')
        : h(Btn, { kind: 'acceptSolid', testid: 'accept', onClick: async () => { const r = await post(`${P(project)}/rungs/${t.id}/approve`); onErr(r.ok ? '' : r.error) } }, 'Accept'),
      h(Btn, { kind: 'small', testid: 'edit', onClick: () => navigate('test-edit', { test: t.id, ret, need }) }, 'Edit')))
}

function StepTests({ project, need, flow }) {
  const q = useRung(project, need)
  const n = q.data
  const [err, setErr] = useState('')
  if (!n) return h(Page, { project }, h(Loading))
  const st = flow.steps.tests
  const specs = []
  for (const r of n.children || []) for (const s of r.children || []) if (s.status === 'approved' || s.status === 'stale') specs.push(s)
  const approve = async () => {
    const res = await post(`${P(project)}/needs/${need}/approve-tests`)
    if (!res.ok) return setErr(res.error)
    navigate('build', { need, step: 'develop' })
  }
  const body = h('div', 'flex flex-col gap-6',
    h(BuildStrip, { need, flow, current: 3 }),
    h('div', { className: 'flex flex-col gap-4', 'data-testid': 'test-step' },
      ...specs.map(s => h('div', { key: s.id, className: 'bg-card border border-line rounded-[6px] p-4 flex flex-col gap-3', 'data-spec': s.id },
        h('div', 'flex items-center justify-between pb-2 border-b border-line',
          h('div', 'flex items-center gap-2',
            h('span', 'text-xs font-semibold mono text-needs', s.id),
            h('span', 'text-xs font-medium text-fg', s.text)),
          h(Btn, { kind: 'small', testid: 'add-test', onClick: () => navigate('test-edit', { spec: s.id, ret: 'tests', need }) }, 'Add test')),
        ...(s.children || []).filter(t => t.status !== 'dismissed' && t.status !== 'proposed').map(t => h(TestRow, { key: t.id, project, t, need, ret: 'tests', onErr: setErr }))))),
    h(ErrorLine, { text: err }),
    h('div', 'flex items-center gap-3 pt-2',
      h(Btn, { kind: 'primaryLg', testid: 'approve-tests', className: 'px-4 py-2', disabled: !st.can_approve || st.done, title: st.blocked_by || '', onClick: approve }, 'Approve tests'),
      h(Btn, { disabled: !st.done, title: st.blocked_by || '', onClick: () => navigate('build', { need, step: 'develop' }) }, 'Next')))
  return h(Page, { project }, body)
}

// ------------------------------------------------------------------ step 5: Develop

function testCount(t) {
  const parts = []
  if (t.command) parts.push(`${t.command} command`)
  if (t.manual) parts.push(`${t.manual} manual`)
  if (t.ai_judged) parts.push(`${t.ai_judged} AI judged`)
  return parts.join(' · ') || 'no tests'
}

function DevelopRow({ project, spec, last, timeoutMin, onErr }) {
  const q = useApi(`${P(project)}/rungs/${spec.id}`)
  const r = q.data
  const [open, setOpen] = useState(false)
  if (!r) return h('div', 'px-4 py-3 text-xs text-muted', spec.id)
  const a = r.allocation
  const shown = a.pick ? a.suggestions.find(x => x.profile === a.pick.profile) || null : a.suggestions[0]
  const running = (r.runs || []).find(x => x.status === 'running' || x.status === 'queued')
  const lastRun = (r.runs || [])[0]
  const grid = 'grid grid-cols-[2.2fr_1fr_1.8fr_1.4fr_1fr] items-center px-4 py-3 text-xs'
  const prof = shown && (CTX_PROFILES[shown.profile] || null)
  return h('div', { className: cx(grid, !last && 'border-b border-line2', 'relative'), 'data-spec': spec.id },
    h('div', 'font-medium text-fg pr-2', `${spec.id} ${spec.text}`),
    h('div', 'text-muted mono text-[11px]', testCount(a.tests)),
    a.human_only
      ? h('div', 'font-medium text-fg', 'You')
      : h('div', { className: 'flex flex-col gap-0.5 pr-2 cursor-pointer', 'data-testid': 'carried-by', onClick: () => setOpen(!open) },
        shown
          ? frag(
            h('span', 'font-medium text-fg mono', `${shown.profile} ${shown.score}`),
            h('span', 'text-[10px] mono text-muted', `tags ${shown.parts.tags} · load ${shown.parts.load} · reliability ${shown.parts.reliability} · cost ${shown.parts.cost}`),
            a.pick ? h('span', { className: 'text-[10px] text-needs', 'data-testid': 'picked-by' }, a.pick.picked_by === 'you' ? 'picked by you' : `picked by ${a.pick.picked_by}`) : null)
          : h('span', 'text-fail', 'No eligible profile')),
    h('div', { className: 'text-muted text-[11px]', 'data-testid': 'budget' }, a.human_only || !shown ? '' : `${prof ? prof.max_runs : 1} attempts · ${timeoutMin} min`),
    h('div', 'text-right',
      a.human_only
        ? h(Btn, { kind: 'small', className: 'px-3', onClick: () => { const m = (r.children || []).find(t => t.type === 'manual'); if (m) navigate('rung', { rid: m.id, ret: 'develop', need: r.path[0] && r.path[0].id }) } }, 'Assign to me')
        : running
          ? h(Btn, { kind: 'small', className: 'px-3', onClick: () => navigate('run', { run: running.id }) }, 'Running')
          : lastRun && lastRun.status === 'passed'
            ? h(Btn, { kind: 'small', className: 'px-3', onClick: () => navigate('run', { run: lastRun.id }) }, 'Passed')
            : h(Btn, {
              kind: 'small', className: 'px-3', testid: 'send', disabled: !r.develop.available || !shown, title: r.develop.blocked_by || '',
              onClick: async () => {
                const res = await post(`${P(project)}/specs/${spec.id}/send`, {})
                if (!res.ok) return onErr(res.error)
                navigate('run', { run: res.data.id })
              }
            }, 'Send')),
    open ? h('div', { className: 'absolute z-10 bg-card border border-line rounded-[6px] p-2 flex flex-col gap-1 shadow-2xl', style: { top: '100%', left: '38%', width: '300px' }, 'data-testid': 'pick-menu' },
      ...a.suggestions.map(sg => h('div', {
        key: sg.profile, className: 'flex items-center justify-between px-2 py-1.5 rounded hover:bg-btnh cursor-pointer text-xs', 'data-pick': sg.profile,
        onClick: async () => { setOpen(false); const res = await post(`${P(project)}/specs/${spec.id}/pick`, { agent: sg.profile }); onErr(res.ok ? '' : res.error) }
      },
      h('span', 'mono text-fg', sg.profile),
      h('span', 'mono text-muted', `${sg.score} · tags ${sg.parts.tags} · load ${sg.parts.load} · rel ${sg.parts.reliability} · cost ${sg.parts.cost}`)))) : null)
}

let CTX_PROFILES = {}

function StepDevelop({ project, need, flow }) {
  const q = useRung(project, need)
  const st = useApi('/settings').data
  const n = q.data
  const [err, setErr] = useState('')
  if (!n || !st) return h(Page, { project }, h(Loading))
  CTX_PROFILES = Object.fromEntries(st.profiles.map(p => [p.name, p]))
  const specs = []
  for (const r of n.children || []) for (const s of r.children || []) if (s.status === 'approved' || s.status === 'stale') specs.push(s)
  const sendAll = async () => {
    for (const s of specs) {
      const res = await post(`${P(project)}/specs/${s.id}/send`, {})
      if (!res.ok && !/manual|already running|no accepted command/.test(res.error)) { setErr(res.error); return }
    }
    navigate('home')
  }
  const body = h('div', 'flex flex-col gap-6',
    h(BuildStrip, { need, flow, current: 4 }),
    h('div', { className: 'bg-card border border-line rounded-[6px] flex flex-col', 'data-testid': 'develop-table' },
      h('div', 'grid grid-cols-[2.2fr_1fr_1.8fr_1.4fr_1fr] items-center px-4 py-2.5 bg-well border-b border-line2 text-[11px] font-semibold tracking-wider text-muted uppercase',
        h('div', null, 'Specification'), h('div', null, 'Tests'), h('div', null, 'Carried by'), h('div', null, 'Budget'), h('div', 'text-right', 'Action')),
      h('div', 'flex flex-col', ...specs.map((s, i) => h(DevelopRow, { key: s.id, project, spec: s, last: i === specs.length - 1, timeoutMin: st.settings.run_timeout_min, onErr: setErr })))),
    h(ErrorLine, { text: err }),
    h('div', 'flex items-center gap-3',
      h(Btn, { kind: 'primaryLg', className: 'px-4 py-2', testid: 'send-all', onClick: sendAll }, 'Send all'),
      h(Btn, { className: 'px-4 py-2', onClick: () => navigate('build', { need, step: 'tests' }) }, 'Back')))
  return h(Page, { project }, body)
}
