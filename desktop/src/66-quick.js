// ------------------------------------------------------------------ quick task (decisions Round 24, B11)
// One card over the ordinary ladder: the outcome, one to five checks and the profile. Save writes the same rungs as
// the full flow, as drafts; Approve names the versions shown; Build and verify starts the ordinary run.

const QUICK_MAX = 5
const blankCheck = () => ({ type: 'command', command: '', steps: '' })

function QuickNew({ project }) {
  const setQ = useApi('/settings')
  const [outcome, setOutcome] = useState('')
  const [checks, setChecks] = useState([blankCheck()])
  const [profile, setProfile] = useState('')
  const [err, setErr] = useState('')
  const [fieldErr, setFieldErr] = useState({})
  const dirty = !!(outcome.trim() || checks.some(c => (c.command || '').trim() || (c.steps || '').trim()))
  useDirty(dirty)
  const cancel = () => goBack('home', {}, { force: true })
  useExit(cancel, true)
  const profiles = ((setQ.data && setQ.data.profiles) || []).map(p => p.name)
  const setCheck = (i, k) => e => { const v = e.target.value; setChecks(cur => cur.map((c, j) => j === i ? { ...c, [k]: v } : c)) }
  const save = async () => {
    const body = {
      outcome,
      agent: profile || null,
      checks: checks.map(c => c.type === 'manual' ? { type: 'manual', steps: c.steps.split('\n').filter(s => s.trim()) } : { type: 'command', command: c.command })
    }
    const res = await post(`${P(project)}/quick`, body)
    if (!res.ok) { setFieldErr(res.field ? { [res.field]: res.error } : {}); return setErr(res.field ? '' : res.error) }
    finish('quick', { need: res.data.need })
  }
  return h(Page, { project, title: 'Quick task' },
    h(Card, { className: 'p-4 flex flex-col gap-4', testid: 'quick-form' },
      h(Field, { label: 'What should work?', error: fieldErr.outcome, name: 'outcome' },
        h('textarea', { className: INPUT, rows: 2, name: 'outcome', value: outcome, onChange: e => setOutcome(e.target.value) })),
      h(Field, { label: 'How will we check it?', error: fieldErr.checks, name: 'checks' },
        h('div', { className: 'flex flex-col gap-2', 'data-testid': 'quick-checks' },
          ...checks.map((c, i) => h('div', { key: i, className: 'flex flex-col gap-1.5 border border-line rounded-[6px] p-2', 'data-testid': 'quick-check' },
            h('div', 'flex items-center gap-2',
              h('select', { className: INPUT + ' w-auto', name: `check-type-${i}`, 'aria-label': `Check ${i + 1} type`, value: c.type, onChange: setCheck(i, 'type') },
                h('option', { value: 'command' }, 'Command'), h('option', { value: 'manual' }, 'Manual steps')),
              checks.length > 1 ? h(Btn, { kind: 'ghost', testid: 'quick-remove-check', label: `Remove check ${i + 1}`, onClick: () => setChecks(cur => cur.filter((_, j) => j !== i)) }, 'Remove') : null),
            c.type === 'manual'
              ? h('textarea', { className: INPUT, rows: 2, name: `check-steps-${i}`, 'aria-label': `Check ${i + 1} steps`, value: c.steps, onChange: setCheck(i, 'steps') })
              : h('input', { className: INPUT + ' mono', name: `check-command-${i}`, 'aria-label': `Check ${i + 1} command`, value: c.command, onChange: setCheck(i, 'command') }))),
          checks.length < QUICK_MAX ? h('div', null, h(Btn, { kind: 'small', testid: 'quick-add-check', onClick: () => setChecks(cur => [...cur, blankCheck()]) }, 'Add check')) : null)),
      h(Field, { label: 'Profile', name: 'profile', optional: true },
        h('select', { className: INPUT, name: 'profile', value: profile, onChange: e => setProfile(e.target.value) },
          h('option', { value: '' }, 'Suggested'), ...profiles.map(n => h('option', { key: n, value: n }, n)))),
      h(ErrorLine, { text: err }),
      h('div', 'flex items-center justify-end gap-2',
        h(ExitBtn, { testid: 'cancel', onClick: cancel }, 'Cancel'),
        h(Btn, { kind: 'primary', testid: 'save', onClick: save }, 'Save'))))
}

const QUICK_KIND = { need: 'Need', requirement: 'Requirement', specification: 'Behaviour', test: 'Check' }

function QuickCheck({ project, c, ro, onEdit }) {
  const last = c.last
  const res = last ? (last.status === 'pending' ? 'pending' : last.status) : 'not_run'
  return h('div', { className: 'flex items-center justify-between gap-3 py-1.5', 'data-testid': 'quick-check-row' },
    h('div', 'flex items-center gap-2 min-w-0',
      h('span', 'whitespace-nowrap text-xs font-medium text-fg mono', c.id),
      h('span', 'whitespace-nowrap text-[11px] text-muted', c.type === 'manual' ? 'manual' : 'command'),
      h('span', { className: 'text-xs text-fg truncate min-w-0 mono', title: c.type === 'manual' ? c.steps.join('; ') : c.command, tabIndex: 0 }, c.type === 'manual' ? c.steps.join('; ') : c.command)),
    h('div', 'flex items-center gap-2',
      h(Badge, { status: c.status === 'approved' ? res : c.status, small: true }),
      c.type === 'manual' && c.status === 'approved' && !ro ? h(Btn, { kind: 'small', testid: 'quick-record', onClick: () => navigate('rung', { rid: c.id }) }, last && last.status === 'pending' ? 'Review result' : 'Record result') : null,
      ro ? null : h(Btn, { kind: 'ghost', testid: 'quick-edit-check', label: `Edit ${c.id}`, onClick: () => onEdit(c) }, 'Edit')))
}

function QuickEdit({ project, c, onClose }) {
  const [val, setVal] = useState(c.type === 'manual' ? c.steps.join('\n') : c.command)
  const [err, setErr] = useState('')
  const save = async () => {
    const fields = c.type === 'manual' ? { steps: val.split('\n').filter(s => s.trim()) } : { command: val }
    const res = await post(`${P(project)}/tests/${c.id}`, { ...fields, version: c.version })
    if (!res.ok) return setErr(res.error)
    onClose()
  }
  return h('div', { className: 'flex flex-col gap-2 border border-line rounded-[6px] p-2', 'data-testid': 'quick-edit', 'data-layer': '1' },
    c.type === 'manual'
      ? h('textarea', { className: INPUT, rows: 2, name: 'edit-steps', 'aria-label': `${c.id} steps`, value: val, onChange: e => setVal(e.target.value) })
      : h('input', { className: INPUT + ' mono', name: 'edit-command', 'aria-label': `${c.id} command`, value: val, onChange: e => setVal(e.target.value) }),
    h(ErrorLine, { text: err }),
    h('div', 'flex items-center justify-end gap-2',
      h(Btn, { kind: 'quiet', testid: 'quick-edit-cancel', onClick: onClose }, 'Cancel'),
      h(Btn, { kind: 'small', testid: 'quick-edit-save', onClick: save }, 'Save check')))
}

function Quick({ project, need }) {
  const q = useApi(`${P(project)}/quick/${need}`, { live: true })
  const stQ = useHome(project)
  const ro = !!(stQ.data && stQ.data.tiles && stQ.data.tiles.archived)
  const [err, setErr] = useState('')
  const [editing, setEditing] = useState(null)
  useExit(() => goBack('home'))
  if (q.error) return h(Missing, { project, text: errText(q.error) })
  const d = q.data
  if (!d) return h(Page, { project, title: 'Quick task', back: () => goBack('home') }, h(Loading))
  const v = d.verification || {}
  const run = d.run
  const running = run && (run.status === 'queued' || run.status === 'running')
  const approve = async () => {
    const versions = {}
    d.rungs.forEach(r => { versions[r.id] = r.version })
    const res = await post(`${P(project)}/quick/${need}/approve`, { versions })
    if (!res.ok) { setErr(res.error); q.refetch(); return }
    setErr('')
  }
  const build = async () => {
    const res = await post(`${P(project)}/quick/${need}/build`, {})
    if (!res.ok) return setErr(res.error)
    setErr('')
  }
  const blocker = (v.blockers || [])[0]
  return h(Page, { project, title: 'Quick task', back: () => goBack('home') },
    h(Card, { className: 'p-4 flex flex-col gap-3', testid: 'quick-card' },
      h('div', 'flex items-start justify-between gap-3',
        h('div', 'flex flex-col gap-1 min-w-0',
          h('span', 'text-[11px] text-muted', 'What should work'),
          h('span', { className: 'text-sm text-fg font-medium', 'data-testid': 'quick-outcome' }, d.outcome)),
        h(Badge, { status: d.approved ? (v.verification || 'unverified') : 'draft', testid: 'quick-state' })),
      blocker && d.approved ? h('div', { className: 'text-xs text-muted', 'data-testid': 'quick-blocker' }, blocker.text) : null,
      h('div', 'flex flex-col', h('span', 'text-[11px] text-muted', 'How we check it'),
        ...d.checks.map(c => editing === c.id
          ? h(QuickEdit, { key: c.id, project, c, onClose: () => setEditing(null) })
          : h(QuickCheck, { key: c.id, project, c, ro, onEdit: x => setEditing(x.id) }))),
      h('div', 'flex flex-col gap-1', h('span', 'text-[11px] text-muted', 'Written'),
        h('ul', { className: 'flex flex-col gap-0.5', 'data-testid': 'quick-rungs' },
          ...d.rungs.map(r => h('li', { key: r.id, className: 'flex items-center gap-2 text-xs min-w-0' },
            h('span', 'whitespace-nowrap mono text-fg', `${r.id} v${r.version}`),
            h('span', 'whitespace-nowrap text-[11px] text-muted', QUICK_KIND[r.kind]),
            h('span', { className: 'text-muted truncate min-w-0', title: r.text, tabIndex: 0 }, r.text),
            h(Badge, { status: r.status, small: true }))))),
      run ? h('div', { className: 'flex items-center gap-2 text-xs', 'data-testid': 'quick-run' },
        h('span', 'text-muted', `Run ${run.id} · ${run.profile}`), h(Badge, { status: run.status, small: true }),
        h(Btn, { kind: 'ghost', testid: 'quick-open-run', onClick: () => navigate('run', { run: run.id }) }, 'Open run')) : null,
      h(ErrorLine, { text: err }),
      h('div', 'flex flex-wrap items-center justify-end gap-2',
        h(Btn, { kind: 'quiet', testid: 'quick-ladder', onClick: () => navigate('rung', { rid: d.need }) }, 'Show full ladder'),
        ro ? null : d.approved
          ? h(Btn, { kind: 'primary', testid: 'quick-build', disabled: running || !d.can_build, title: d.build_blocked_by || undefined, onClick: build }, 'Build and verify')
          : h(Btn, { kind: 'primary', testid: 'quick-approve', onClick: approve }, 'Approve'))))
}

Object.assign(VIEWS, {
  'quick-new': QuickNew,
  quick: Quick
})
