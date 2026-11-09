// ------------------------------------------------------------------ integration milestones (decisions Round 23)
// A milestone is a declared journey over approved specifications with its own cross-component checks. Its state
// comes from the engine (one verdict for pane, CLI and report); the pane only shows it and offers the next step.

Object.assign(BADGE, {
  not_ready: ['Not ready for integration', 'bg-btn text-fg border border-line'],
  ready: ['Ready for integration', 'bg-btn text-fg border border-line'],
  verifying: ['Verifying', 'text-needs border border-needs'],
  integration_failed: ['Integration failed', 'bg-fail/10 text-fail border border-fail/30'],
  satisfied: ['Passed', 'bg-pass/10 text-pass border border-pass/30'],
  missing: ['Not run', 'bg-btn text-dim border border-line']
})

const M_TONE = { verified: 'pass', integration_failed: 'fail', out_of_date: 'stale', verifying: 'needs', awaiting_manual: 'needs', could_not_verify: 'needs' }

function specsOf(tree) {
  const out = []
  const walk = ns => (ns || []).forEach(n => { if (n.kind === 'specification' && n.status === 'approved') out.push(n); walk(n.children) })
  walk(tree)
  return out
}

function MilestoneRow({ m }) {
  const ok = m.scope.filter(s => s.ok).length
  return h(Card, { key: m.id, className: 'p-3 flex items-center justify-between gap-3', testid: 'milestone-row', onClick: () => navigate('milestone', { mid: m.id }) },
    h('div', 'flex items-center gap-2.5 min-w-0', h(Dot, { t: M_TONE[m.state] || 'muted' }),
      h('span', 'whitespace-nowrap text-xs font-medium text-fg mono', m.id),
      h('span', { className: 'text-xs text-fg truncate min-w-0', title: m.title }, m.title),
      h('span', 'whitespace-nowrap text-[11px] text-muted mono', `${ok} of ${m.scope.length}`)),
    h(Badge, { status: m.state, small: true }))
}

function Milestones({ project }) {
  const q = useApi(`${P(project)}/milestones`, { live: true })
  const stQ = useHome(project)
  const ro = !!(stQ.data && stQ.data.tiles && stQ.data.tiles.archived)
  useExit(() => goBack('home'))
  if (q.error) return h(Missing, { project, text: errText(q.error) })
  const rows = q.data
  return h(Page, { project, title: 'Milestones', back: () => goBack('home') },
    h('section', { className: 'flex flex-col gap-2', 'data-testid': 'milestones' },
      h(SectionTitle, { right: h('span', 'flex items-center gap-2', h(Btn, { kind: 'small', testid: 'open-plan', onClick: () => navigate('plan') }, 'Plan'),
        h(Btn, { kind: 'small', testid: 'open-report', onClick: () => navigate('system-report') }, 'System report'),
        h(Btn, { kind: 'small', testid: 'open-architecture', onClick: () => navigate('architecture') }, 'Architecture'),
        ro ? null : h(Btn, { kind: 'small', testid: 'milestone-new', onClick: () => navigate('milestone-new') }, 'New milestone')) }, 'Integration milestones'),
      !rows ? h(Loading) : rows.length ? frag(...rows.map(m => h(MilestoneRow, { key: m.id, m })))
        : h(Empty, { text: 'No milestones', action: ro ? null : 'New milestone', onClick: () => navigate('milestone-new'), testid: 'no-milestones' })))
}

function MilestoneNew({ project }) {
  const tq = useApi(`${P(project)}/tree`)
  const [f, setF] = useState({ title: '', journey: '', architecture: '', command: '' })
  const [scope, setScope] = useState([])
  const [err, setErr] = useState('')
  const [fieldErr, setFieldErr] = useState({})
  const set = k => e => { const v = e.target.value; setF(cur => ({ ...cur, [k]: v })) }
  const dirty = !!(f.title.trim() || f.journey.trim() || f.architecture.trim() || f.command.trim() || scope.length)
  useDirty(dirty)
  const cancel = () => goBack('milestones', {}, { force: true })
  useExit(cancel, true)
  if (tq.error) return h(Missing, { project, text: errText(tq.error) })
  const specs = specsOf(tq.data)
  const toggle = id => setScope(cur => cur.includes(id) ? cur.filter(x => x !== id) : [...cur, id])
  const save = async () => {
    if (!f.command.trim()) return setFieldErr({ command: 'A milestone needs a command check' })
    const res = await post(`${P(project)}/milestones`, { title: f.title, journey: f.journey, architecture: f.architecture, scope })
    if (!res.ok) { setFieldErr(res.field ? { [res.field]: res.error } : {}); return setErr(res.field ? '' : res.error) }
    const mid = res.data.id
    // Created either way; a check the engine refused leaves the draft without it, where Add check offers it again.
    await post(`${P(project)}/milestones/${mid}/checks`, { type: 'command', command: f.command, text: f.journey }, { quiet: true })
    finish('milestone', { mid })
  }
  return h(Page, { project, title: 'New milestone' },
    h(Card, { className: 'p-4 flex flex-col gap-4', testid: 'milestone-form' },
      h(Field, { label: 'Outcome', error: fieldErr.title, name: 'title' }, h('input', { className: INPUT, name: 'title', value: f.title, onChange: set('title') })),
      h(Field, { label: 'User journey', error: fieldErr.journey, name: 'journey' }, h('textarea', { className: INPUT, rows: 3, name: 'journey', value: f.journey, onChange: set('journey') })),
      h(Field, { label: 'Architecture and constraints', optional: true, name: 'architecture' }, h('textarea', { className: INPUT, rows: 2, name: 'architecture', value: f.architecture, onChange: set('architecture') })),
      h(Field, { label: 'Included specifications', error: fieldErr.scope, name: 'scope' },
        !tq.data ? h(Loading) : specs.length
          ? h('div', { className: 'flex flex-col gap-1', role: 'group', 'aria-label': 'Included specifications' },
            ...specs.map(s => h('label', { key: s.id, className: 'flex items-center gap-2 text-xs text-fg min-h-[24px]' },
              h('input', { type: 'checkbox', name: 'scope', value: s.id, checked: scope.includes(s.id), onChange: () => toggle(s.id) }),
              h('span', 'mono whitespace-nowrap', s.id), h('span', { className: 'text-muted truncate min-w-0', title: s.text }, s.text),
              h(Badge, { status: s.verification || 'unverified', small: true }))))
          : h(Empty, { text: 'No approved specifications' })),
      h(Field, { label: 'Integration check command', error: fieldErr.command, name: 'command' },
        h('input', { className: INPUT + ' mono', name: 'command', value: f.command, onChange: set('command') })),
      h(ErrorLine, { text: err }),
      h('div', 'flex items-center justify-end gap-2',
        h(ExitBtn, { testid: 'cancel', onClick: cancel }, 'Cancel'),
        h(Btn, { kind: 'primary', testid: 'save', onClick: save }, 'Create'))))
}

function NextStep({ project, m, ro }) {
  const na = m.next_action
  if (!na || ro) return null
  const base = `${P(project)}/milestones/${m.id}`
  if (na.kind === 'approve_milestone') return h(Btn, { kind: 'primary', testid: 'next-action', onClick: () => post(`${base}/approve`) }, 'Approve')
  if (na.kind === 'run_checks' || na.kind === 'repair_check_setup') return h(Btn, { kind: 'primary', testid: 'next-action', onClick: () => post(`${base}/run`) }, 'Run checks')
  if (na.kind === 'repair') return h(Btn, { testid: 'next-action', onClick: () => post(`${base}/run`) }, 'Run checks again')
  if (na.kind === 'verify_scope' && na.rung) return h(Btn, { kind: 'primary', testid: 'next-action', onClick: () => navigate('rung', { rid: na.rung }) }, `Open ${na.rung}`)
  if (na.kind === 'review_check_files' && na.check) return h(Btn, { kind: 'primary', testid: 'next-action', onClick: () => post(`${base}/checks/${na.check}/accept-files`) }, 'Accept changed files')
  return null
}

function MilestoneView({ project, mid }) {
  const q = useApi(`${P(project)}/milestones/${encodeURIComponent(mid)}`, { live: true })
  const stQ = useHome(project)
  const ro = !!(stQ.data && stQ.data.tiles && stQ.data.tiles.archived)
  const [exported, setExported] = useState(null)
  const [err, setErr] = useState('')
  const [cmd, setCmd] = useState('')
  useDirty(!!cmd.trim())
  useExit(() => goBack('milestones'))
  if (q.error) return h(Missing, { project, text: errText(q.error) })
  const m = q.data
  if (!m) return h(Page, { project, title: mid }, h(Loading))
  const base = `${P(project)}/milestones/${m.id}`
  const exp = async () => {
    const x = await post(`${base}/export`)
    if (!x.ok) return setErr(x.error)
    setErr(''); setExported(x.data.path)
  }
  const addCheck = async () => {
    const x = await post(`${base}/checks`, { type: 'command', command: cmd })
    if (!x.ok) return setErr(x.error)
    setErr(''); setCmd('')
  }
  const record = (cid, result) => post(`${base}/checks/${cid}/record`, { result })
  return h(Page, { project, title: m.id, back: () => goBack('milestones') },
    h(Card, { className: 'p-4 flex flex-col gap-4', testid: 'milestone' },
      h('div', 'flex flex-wrap items-start justify-between gap-3',
        h('div', 'flex flex-col gap-1 min-w-0',
          h('h2', { className: 'text-sm font-semibold text-fg', 'data-testid': 'milestone-title' }, m.title),
          h('span', 'text-[11px] mono text-muted', [`version ${m.version}`, m.approved_by && `approved by ${m.approved_by}`, `code ${m.basis}`].filter(Boolean).join(' · '))),
        h('div', 'flex items-center gap-2',
          h('span', { 'data-testid': 'milestone-state', 'data-state': m.state }, h(Badge, { status: m.state })),
          h(NextStep, { project, m, ro }),
          h(Btn, { testid: 'export', onClick: exp }, 'Export'))),
      exported ? h(Well, { className: 'flex items-center justify-between text-xs', testid: 'export-path' },
        h('span', 'text-muted', 'Exported'), h('span', 'mono text-fg', shortPath(exported))) : null,
      h(ErrorLine, { text: err }),
      m.blockers.length ? h('div', { className: 'flex flex-col gap-1', 'data-testid': 'milestone-blockers' },
        ...m.blockers.map((b, i) => h('div', { key: i, className: 'flex items-center gap-2 text-xs', 'data-code': b.code },
          h(Dot, { t: B_TONE[b.code] || 'needs' }), h('span', 'text-fg', b.text)))) : null,
      h(MilestoneComponents, { project, m, ro, onErr: setErr }),
      h(Section, { title: 'Journey', testid: 'milestone-journey' }, h(Well, { className: 'text-xs text-fg' }, m.journey)),
      m.architecture ? h(Section, { title: 'Architecture and constraints', testid: 'milestone-architecture' }, h(Well, { className: 'text-xs text-muted' }, m.architecture)) : null,
      h(Section, { title: 'Included work', testid: 'milestone-scope', right: h('span', 'text-[11px] mono text-muted', `${m.scope.filter(s => s.ok).length} of ${m.scope.length} verified`) },
        h('div', 'flex flex-col gap-1.5',
          ...m.scope.map(s => h(Card, { key: s.id, nested: true, className: 'p-2.5 flex items-center justify-between gap-3', onClick: () => navigate('rung', { rid: s.id }) },
            h('span', 'flex items-center gap-2 min-w-0', h('span', 'mono text-xs text-fg whitespace-nowrap', s.id), h('span', { className: 'text-xs text-muted truncate min-w-0', title: s.text || '' }, s.text || '')),
            h(Badge, { status: s.verification, small: true }))))),
      h(Section, { title: 'Checks', testid: 'milestone-checks' },
        h('div', 'flex flex-col gap-1.5',
          ...m.checks.map(c => h(Well, { key: c.check, className: 'flex flex-col gap-1.5', testid: 'check-' + c.check },
            h('div', 'flex items-center justify-between gap-3 text-xs',
              h('span', 'flex items-center gap-2 min-w-0',
                h('span', 'mono text-fg whitespace-nowrap', c.check),
                h('span', { className: 'mono text-muted truncate min-w-0', title: c.command || c.steps.join('; ') }, c.command || c.steps.join('; ')),
                c.required ? null : h('span', 'text-[11px] text-dim', 'optional')),
              h('span', 'flex items-center gap-1.5 shrink-0',
                c.type === 'manual' && m.status === 'approved' && !ro ? frag(
                  h(Btn, { kind: 'small', testid: 'record-pass', onClick: () => record(c.check, 'pass') }, 'Pass'),
                  h(Btn, { kind: 'small', testid: 'record-fail', onClick: () => record(c.check, 'fail') }, 'Fail')) : null,
                h(Badge, { status: c.state, small: true }))),
            ...(c.runs || []).slice(0, 3).map(r => h('div', { key: r.n, className: 'flex items-center justify-between text-[11px] mono text-muted pl-3 border-l border-line', 'data-run': r.n },
              h('span', null, [`#${r.n}`, r.carried_by, `code ${r.basis}`, r.current_scope ? null : 'earlier version', r.reason].filter(Boolean).join(' · ')),
              h(Badge, { status: r.status, small: true })))))),
        m.status === 'draft' && !ro ? h('div', 'flex items-center gap-2 pt-1',
          h('input', { className: INPUT + ' mono', name: 'check-command', 'aria-label': 'Check command', value: cmd, onChange: e => setCmd(e.target.value) }),
          h(Btn, { kind: 'small', testid: 'add-check', onClick: addCheck, disabled: !cmd.trim() }, 'Add check')) : null),
      h(MilestoneSystem, { project, m, ro, onErr: setErr })))
}

Object.assign(VIEWS, {
  milestones: Milestones,
  milestone: MilestoneView,
  'milestone-new': MilestoneNew
})
