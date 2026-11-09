// ------------------------------------------------------------------ system controls (decisions Round 24)
// Architecture baseline (SYS-02): components and contracts, each a draft a person approves; a contract shows the
// work it affects. Dependencies (SYS-03): a specification requires others, shown both ways; a start waits.

Object.assign(BADGE, {
  draft_version: ['Draft', 'bg-btn text-fg border border-line'],
  approved_version: ['Approved', 'bg-pass/10 text-pass border border-pass/30'],
  local: ['Local', 'bg-btn text-fg border border-line'],
  integrated: ['Integrated', 'bg-btn text-fg border border-line']
})

// Project settings: how develop runs work (SYS-05). Saved at once; no typed text to lose.
function RunModeSection({ project, proj, onErr }) {
  const mode = (proj && proj.run_mode) || 'shared'
  const set = async m => { const x = await post(`${P(project)}/run-mode`, { mode: m }); onErr(x.ok ? '' : x.error) }
  return h('section', { className: 'bg-card border border-line rounded-[6px] p-5 flex flex-col gap-3', 'data-testid': 'run-mode' },
    h(SectionTitle, null, 'Runs'),
    h('div', { className: 'flex gap-4', role: 'radiogroup', 'aria-label': 'Runs' },
      ...[['shared', 'Project folder'], ['isolated', 'Isolated']].map(([k, label]) => h('label', { key: k, className: 'flex items-center gap-1.5 text-xs text-fg min-h-[24px]' },
        h('input', { type: 'radio', name: 'run_mode', value: k, checked: mode === k, onChange: () => set(k) }), label))))
}

const listOf = v => String(v || '').split(',').map(x => x.trim()).filter(Boolean)

function ArchItem({ project, it, ro, affected, onErr }) {
  const v = it.draft || it.current
  const approve = async () => {
    const x = await post(`${P(project)}/architecture/approve`, { kind: it.kind, name: it.name })
    if (!x.ok) return onErr(x.error)
    onErr('')
  }
  const isC = it.kind === 'contract'
  return h('div', { 'data-testid': 'arch-' + it.kind, 'data-name': it.name }, h(Card, { nested: true, className: 'p-3 flex flex-col gap-2' },
    h('div', 'flex items-center justify-between gap-3',
      h('span', 'flex items-center gap-2 min-w-0',
        h('span', 'text-xs font-semibold text-fg', it.name),
        h('span', 'text-[11px] mono text-muted whitespace-nowrap', `v${v.version}`),
        isC ? h('span', 'text-[11px] text-muted whitespace-nowrap', `${v.kind} · ${v.producer} to ${(v.consumers || []).join(', ')}`) : null),
      h('span', 'flex items-center gap-2 shrink-0',
        h(Badge, { status: it.draft ? 'draft_version' : 'approved_version', small: true }),
        it.draft && !ro ? h(Btn, { kind: 'accept', testid: 'approve-arch', onClick: approve }, 'Approve') : null)),
    isC ? frag((v.artifacts || []).length ? h('span', { className: 'text-xs text-muted mono', 'data-testid': 'artifacts' }, v.artifacts.join(', ')) : null,
      v.text ? h(Well, { className: 'text-xs text-fg whitespace-pre-wrap' }, v.text) : null)
      : h('div', 'text-xs text-muted flex flex-col gap-0.5',
        v.responsibility ? h('span', null, v.responsibility) : null,
        (v.paths || []).length ? h('span', 'mono', v.paths.join(', ')) : null),
    isC && affected ? h('div', { className: 'flex flex-col gap-1 text-xs', 'data-testid': 'affected' },
      h('span', 'text-[11px] font-semibold uppercase tracking-wider text-muted', 'Affected work'),
      affected.specifications.length || affected.milestones.length
        ? h('div', 'flex flex-wrap gap-1.5',
          ...affected.specifications.map(s => h('button', { type: 'button', key: s, className: 'mono text-[11px] px-2 min-h-[24px] rounded border border-line bg-btn text-fg', 'data-affected': s, onClick: () => navigate('rung', { rid: s }) }, s)),
          ...affected.milestones.map(m => h('button', { type: 'button', key: m, className: 'mono text-[11px] px-2 min-h-[24px] rounded border border-line bg-btn text-fg', 'data-affected': m, onClick: () => navigate('milestone', { mid: m }) }, m)))
        : h('span', 'text-dim', 'None')) : null,
    isC && it.checks ? h(ContractChecks, { project, it, ro, onErr }) : null,
    isC && !ro ? h(ContractRevise, { project, it, onErr }) : null))
}

// Contract checks (SYS-06): proposed, approved by a person, run against the real artifacts.
const CC_WORD = { satisfied: 'Passed', failed: 'Failed', out_of_date: 'Out of date', missing: 'Not run', could_not_verify: 'Could not verify' }
const CC_BADGE = { satisfied: 'verified', failed: 'failed', out_of_date: 'out_of_date', missing: 'not_run', could_not_verify: 'could_not_verify' }
function ContractChecks({ project, it, ro, onErr }) {
  const cc = it.checks
  const [cmd, setCmd] = useState('')
  useDirty(!!cmd.trim())
  const base = { contract: it.name }
  const run = async () => { const x = await post(`${P(project)}/contract-checks/run`, base); onErr(x.ok ? '' : x.error) }
  const add = async () => {
    const x = await post(`${P(project)}/contract-checks`, { ...base, command: cmd })
    if (!x.ok) return onErr(x.error)
    onErr(''); setCmd('')
  }
  const approved = cc.checks.filter(c => c.status === 'approved').length
  return h('div', { className: 'flex flex-col gap-1.5 text-xs', 'data-testid': 'contract-checks', 'data-state': cc.state },
    h('div', 'flex items-center justify-between gap-2',
      h('span', 'text-[11px] font-semibold uppercase tracking-wider text-muted', 'Contract checks'),
      !ro && approved ? h(Btn, { kind: 'small', testid: 'run-contract-checks', onClick: run }, 'Run checks') : null),
    ...cc.checks.map(c => h('div', { key: c.check, className: 'flex items-center gap-2 min-w-0', 'data-check': c.check, 'data-state': c.state },
      h('span', 'mono text-[11px] text-fg whitespace-nowrap', c.check),
      h('span', { className: 'mono text-[11px] text-muted truncate min-w-0', title: c.command }, c.command),
      c.status === 'draft' ? h(Badge, { status: 'draft_version', small: true }) : h(Badge, { status: CC_BADGE[c.state], label: CC_WORD[c.state], small: true }),
      c.why ? h('span', { className: 'text-[11px] text-muted', 'data-testid': 'check-why' }, c.why) : null,
      c.contract_version ? h('span', 'text-[11px] mono text-dim whitespace-nowrap', `v${c.contract_version} · ${c.basis}`) : null,
      c.status === 'draft' && !ro ? h(Btn, { kind: 'accept', testid: 'approve-contract-check', onClick: async () => {
        const x = await post(`${P(project)}/contract-checks/approve`, { ...base, check: c.check }); onErr(x.ok ? '' : x.error)
      } }, 'Approve') : null)),
    ro ? null : h('div', 'flex items-center gap-2',
      h('input', { className: cx(INPUT, 'mono'), name: 'contract_check', 'aria-label': `${it.name} check command`, value: cmd, onChange: e => setCmd(e.target.value) }),
      h(Btn, { kind: 'small', testid: 'add-contract-check', disabled: !cmd.trim(), onClick: add }, 'Add check')))
}

function ContractRevise({ project, it, onErr }) {
  const base = (it.draft || it.current || {}).text || ''
  const [text, setText] = useState(null)
  const dirty = text !== null && text !== base
  useDirty(dirty)
  if (text === null) return h('div', null, h(Btn, { kind: 'small', testid: 'revise-contract', onClick: () => setText(base) }, 'New version'))
  return h('div', 'flex flex-col gap-2',
    h('textarea', { className: INPUT, rows: 3, name: 'contract_text', 'aria-label': `${it.name} text`, value: text, onChange: e => setText(e.target.value) }),
    h('div', 'flex items-center justify-end gap-2',
      h(ExitBtn, { testid: 'cancel-revise', onClick: () => setText(null) }, 'Cancel'),
      h(Btn, { kind: 'small', testid: 'save-contract', disabled: !dirty, onClick: async () => {
        const x = await post(`${P(project)}/architecture`, { kind: 'contract', name: it.name, text })
        if (!x.ok) return onErr(x.error)
        onErr(''); setText(null)
      } }, 'Save draft')))
}

function Architecture({ project }) {
  const q = useApi(`${P(project)}/architecture`, { live: true })
  const stQ = useHome(project)
  const ro = !!(stQ.data && stQ.data.tiles && stQ.data.tiles.archived)
  const empty = { kind: 'component', name: '', responsibility: '', paths: '', contract_kind: 'api', producer: '', consumers: [], artifacts: '', text: '' }
  const [f, setF] = useState(empty)
  const [err, setErr] = useState('')
  useDirty(!!(f.name.trim() || f.responsibility.trim() || f.paths.trim() || f.artifacts.trim() || f.text.trim()))
  useExit(() => goBack('home'))
  if (q.error) return h(Missing, { project, text: errText(q.error) })
  const a = q.data
  const comps = a ? a.components.filter(c => c.current).map(c => c.name) : []
  const set = k => e => { const v = e.target.value; setF(cur => ({ ...cur, [k]: v })) }
  const save = async () => {
    const body = f.kind === 'component'
      ? { kind: 'component', name: f.name, responsibility: f.responsibility, paths: listOf(f.paths) }
      : { kind: 'contract', name: f.name, contract_kind: f.contract_kind, producer: f.producer, consumers: f.consumers, artifacts: listOf(f.artifacts), text: f.text }
    const x = await post(`${P(project)}/architecture`, body)
    if (!x.ok) return setErr(x.error)
    setErr(''); setF({ ...empty, kind: f.kind })
  }
  const onErr = setErr
  return h(Page, { project, title: 'Architecture', back: () => goBack('home') },
    h(ErrorLine, { text: err }),
    !a ? h(Loading) : frag(
      h('section', { className: 'flex flex-col gap-2', 'data-testid': 'components' },
        h(SectionTitle, null, 'Components'),
        a.components.length ? frag(...a.components.map(c => h(ArchItem, { key: c.name, project, it: c, ro, onErr })))
          : h(Empty, { text: 'No components' })),
      h('section', { className: 'flex flex-col gap-2', 'data-testid': 'contracts' },
        h(SectionTitle, null, 'Contracts'),
        a.contracts.length ? frag(...a.contracts.map(c => h(ArchItem, { key: c.name, project, it: c, ro, affected: c.affected, onErr })))
          : h(Empty, { text: 'No contracts' })),
      ro ? null : h(Card, { className: 'p-4 flex flex-col gap-3', testid: 'arch-form' },
        h(SectionTitle, null, 'Add'),
        h('div', { className: 'flex gap-2', role: 'radiogroup', 'aria-label': 'Kind' },
          ...['component', 'contract'].map(k => h('label', { key: k, className: 'flex items-center gap-1.5 text-xs text-fg min-h-[24px]' },
            h('input', { type: 'radio', name: 'arch_kind', value: k, checked: f.kind === k, onChange: () => setF({ ...f, kind: k }) }), capital(k)))),
        h(Field, { label: 'Name', name: 'arch_name' }, h('input', { className: INPUT, name: 'arch_name', value: f.name, onChange: set('name') })),
        f.kind === 'component' ? frag(
          h(Field, { label: 'Responsibility', optional: true, name: 'responsibility' }, h('input', { className: INPUT, name: 'responsibility', value: f.responsibility, onChange: set('responsibility') })),
          h(Field, { label: 'Paths', optional: true, name: 'paths' }, h('input', { className: cx(INPUT, 'mono'), name: 'paths', value: f.paths, onChange: set('paths') })))
          : frag(
            h(Field, { label: 'Kind', name: 'contract_kind' }, h('select', { className: INPUT, name: 'contract_kind', value: f.contract_kind, onChange: set('contract_kind') },
              ...['api', 'event', 'file', 'schema', 'cli', 'other'].map(k => h('option', { key: k, value: k }, k)))),
            h(Field, { label: 'Producer', name: 'producer' }, h('select', { className: INPUT, name: 'producer', value: f.producer, onChange: set('producer') },
              h('option', { value: '' }, ''), ...comps.map(c => h('option', { key: c, value: c }, c)))),
            h(Field, { label: 'Consumers', name: 'consumers' }, h('div', { className: 'flex flex-wrap gap-3', role: 'group', 'aria-label': 'Consumers' },
              ...comps.map(c => h('label', { key: c, className: 'flex items-center gap-1.5 text-xs text-fg min-h-[24px]' },
                h('input', { type: 'checkbox', name: 'consumers', value: c, checked: f.consumers.includes(c), onChange: () => setF(cur => ({ ...cur, consumers: cur.consumers.includes(c) ? cur.consumers.filter(x => x !== c) : [...cur.consumers, c] })) }), c)))),
            h(Field, { label: 'Artifacts', optional: true, name: 'artifacts' }, h('input', { className: cx(INPUT, 'mono'), name: 'artifacts', value: f.artifacts, onChange: set('artifacts') })),
            h(Field, { label: 'Contract', optional: true, name: 'text' }, h('textarea', { className: INPUT, rows: 3, name: 'text', value: f.text, onChange: set('text') }))),
        h('div', 'flex justify-end', h(Btn, { kind: 'primary', testid: 'save-arch', disabled: !f.name.trim(), onClick: save }, 'Save draft')))))
}

// On a specification: the components it touches and its dependencies, both ways.
function SpecSystem({ project, r, onErr }) {
  const aq = useApi(`${P(project)}/architecture`)
  const [req, setReq] = useState('')
  const comps = aq.data ? aq.data.components.filter(c => c.current).map(c => c.name) : []
  const d = r.dependencies || { requires: [], required_by: [] }
  const base = `${P(project)}/rungs/${r.id}`
  const [mine, toggle] = useSavedSet(r.components, async next => {
    const x = await post(`${base}/components`, { components: next })
    onErr(x.ok ? '' : x.error)
    return x.ok
  })
  const add = async () => {
    const x = await post(`${base}/dependencies`, { requires: req.trim() })
    if (!x.ok) return onErr(x.error)
    onErr(''); setReq('')
  }
  const chip = (id, s) => h('button', { type: 'button', key: id, className: 'inline-flex items-center gap-1.5 text-[11px] px-2 min-h-[24px] rounded border border-line bg-btn text-fg', 'data-dep': id, onClick: () => navigate('rung', { rid: id }) },
    h('span', 'mono', id), s ? h(Badge, { status: s, small: true }) : null)
  return h('section', { className: 'bg-card border border-line rounded-[6px] p-4 flex flex-col gap-3', 'data-testid': 'spec-system' },
    h('div', 'flex items-center justify-between pb-1.5 border-b border-line', h('h3', 'text-xs font-semibold uppercase tracking-wider text-muted', 'System')),
    r.waits_for ? h('div', { className: 'flex items-center gap-2 text-xs', 'data-testid': 'waits-for' }, h(Dot, { t: 'needs' }), h('span', 'text-fg', r.waits_for)) : null,
    h('div', { className: 'flex flex-wrap items-center gap-2 text-xs', 'data-testid': 'spec-components' },
      h('span', 'text-muted w-24 shrink-0', 'Components'),
      comps.length ? frag(...comps.map(c => h('label', { key: c, className: 'flex items-center gap-1.5 min-h-[24px] text-fg' },
        h('input', { type: 'checkbox', name: 'component', value: c, checked: mine.includes(c), onChange: () => toggle(c) }), c)))
        : h('span', 'text-dim', 'None')),
    h('div', { className: 'flex flex-wrap items-center gap-2 text-xs', 'data-testid': 'requires' },
      h('span', 'text-muted w-24 shrink-0', 'Requires'),
      d.requires.length ? frag(...d.requires.map(x => h('span', { key: x.id, className: 'inline-flex items-center gap-1' }, chip(x.id, x.verification),
        h('button', { type: 'button', className: 'text-[11px] text-muted hover:text-fg min-h-[24px] min-w-[24px]', 'aria-label': `Remove ${x.id}`, 'data-remove': x.id, onClick: async () => { const y = await post(`${base}/dependencies/remove`, { requires: x.id }); onErr(y.ok ? '' : y.error) } }, '×'))))
        : h('span', 'text-dim', 'None'),
      h('input', { className: cx(INPUT, 'mono w-28'), name: 'requires', 'aria-label': 'Requires specification', value: req, onChange: e => setReq(e.target.value) }),
      h(Btn, { kind: 'small', testid: 'add-dependency', disabled: !req.trim(), onClick: add }, 'Add')),
    h('div', { className: 'flex flex-wrap items-center gap-2 text-xs', 'data-testid': 'required-by' },
      h('span', 'text-muted w-24 shrink-0', 'Required by'),
      d.required_by.length ? frag(...d.required_by.map(id => chip(id))) : h('span', 'text-dim', 'None')))
}

// A checkbox set saved on each click. The next set is built from the last one sent, not from the server copy,
// so a second click before the refetch keeps the first choice.
function useSavedSet(server, save) {
  const sent = useRef(null)
  const key = (server || []).join('\u0000')
  const [, bump] = useState(0)
  if (sent.current && sent.current.join('\u0000') === key) sent.current = null
  const cur = sent.current || server || []
  const toggle = async c => {
    const next = cur.includes(c) ? cur.filter(y => y !== c) : [...cur, c]
    sent.current = next
    bump(n => n + 1)
    const ok = await save(next)
    if (!ok && sent.current === next) { sent.current = null; bump(n => n + 1) }
  }
  return [cur, toggle]
}

// On a milestone: the components it touches (SYS-02).
function MilestoneComponents({ project, m, ro, onErr }) {
  const aq = useApi(`${P(project)}/architecture`)
  const comps = aq.data ? aq.data.components.filter(c => c.current).map(c => c.name) : []
  const [mine, toggle] = useSavedSet(m.components, async next => {
    const x = await post(`${P(project)}/milestones/${m.id}/components`, { components: next })
    onErr(x.ok ? '' : x.error)
    return x.ok
  })
  if (!comps.length && !mine.length) return null
  return h('div', { className: 'flex flex-wrap items-center gap-3 text-xs', 'data-testid': 'milestone-components' },
    h('span', 'text-muted', 'Components'),
    ...comps.map(c => h('label', { key: c, className: 'flex items-center gap-1.5 min-h-[24px] text-fg' },
      h('input', { type: 'checkbox', name: 'component', value: c, checked: mine.includes(c), disabled: ro, onChange: () => toggle(c) }), c)))
}

// The plan (SYS-04): every specification in scope with its state now; Start ready work starts the Ready ones.
Object.assign(BADGE, {
  ready: BADGE.ready || ['Ready', 'bg-btn text-fg border border-line'],
  blocked: ['Blocked', 'text-needs border border-needs'],
  running: BADGE.running || ['Running', 'text-needs border border-needs'],
  not_ready: BADGE.not_ready || ['Not ready', 'bg-btn text-dim border border-line'],
  waiting: ['Waiting for capacity', 'bg-btn text-fg border border-line']
})
const PLAN_WORD = { ready: 'Ready', blocked: 'Blocked', running: 'Running', verified: 'Verified', not_ready: 'Not ready', waiting: 'Waiting for capacity' }

function Plan({ project }) {
  const q = useApi(`${P(project)}/plan`, { live: true })
  const stQ = useHome(project)
  const ro = !!(stQ.data && stQ.data.tiles && stQ.data.tiles.archived)
  const [err, setErr] = useState('')
  const [note, setNote] = useState('')
  const [budget, setBudget] = useState(null)
  const [mins, setMins] = useState(null)
  useExit(() => goBack('home'))
  if (q.error) return h(Missing, { project, text: errText(q.error) })
  const pl = q.data
  const b = pl ? pl.budget : null
  const ready = pl ? pl.items.filter(i => i.state === 'ready').length : 0
  const start = async () => {
    const x = await post(`${P(project)}/plan/start`, {})
    if (!x.ok) return setErr(x.error)
    setErr('')
    setNote([x.data.started.length ? `Started ${x.data.started.map(s => s.spec).join(', ')}` : 'Nothing started', x.data.stopped].filter(Boolean).join('. '))
  }
  const saveBudget = async () => {
    const num = (cur, saved) => { const v = String(cur == null ? (saved == null ? '' : saved) : cur).trim(); return v ? Number(v) : null }
    const x = await post(`${P(project)}/plan/budget`, { attempts: num(budget, b.attempts), minutes: num(mins, b.minutes) })
    if (!x.ok) return setErr(x.error)
    setErr(''); setBudget(null); setMins(null)
  }
  return h(Page, { project, title: 'Plan', back: () => goBack('home') },
    h(ErrorLine, { text: err }),
    note ? h('div', { className: 'text-xs text-fg', 'data-testid': 'plan-note', role: 'status' }, note) : null,
    !pl ? h(Loading) : frag(
      h('section', { className: 'flex flex-col gap-2', 'data-testid': 'plan' },
        h(SectionTitle, { right: ro ? null : h(Btn, { kind: 'primary', testid: 'start-ready', disabled: !ready || b.exhausted, onClick: start }, 'Start ready work') }, 'Specifications'),
        pl.items.length ? frag(...pl.items.map(i => h('div', { key: i.spec, 'data-testid': 'plan-item', 'data-spec': i.spec, 'data-state': i.state }, h(Card, { nested: true, className: 'p-3 flex items-center justify-between gap-3', onClick: () => navigate('rung', { rid: i.spec }) },
          h('span', 'flex items-center gap-2 min-w-0',
            h('span', 'mono text-xs text-fg whitespace-nowrap', i.spec),
            h('span', { className: 'text-xs text-muted truncate min-w-0', title: i.text }, i.text)),
          h('span', 'flex items-center gap-2 shrink-0',
            i.state === 'blocked' ? h('span', { className: 'text-[11px] text-muted', 'data-testid': 'blocked-by' }, `by ${i.blocked_by.join(', ')}`) : null,
            i.state === 'ready' && i.reason ? h('span', { className: 'text-[11px] text-muted', 'data-testid': 'plan-reason' }, i.reason) : null,
            h(Badge, { status: i.state, label: PLAN_WORD[i.state], small: true }))))))
          : h(Empty, { text: 'No approved specifications' })),
      h('section', { className: 'bg-card border border-line rounded-[6px] p-4 flex flex-col gap-2', 'data-testid': 'plan-budget' },
        h(SectionTitle, null, 'Budget'),
        h('div', { className: 'flex items-center gap-3 text-xs', 'data-testid': 'budget-line' },
          h('span', 'text-fg', b.attempts == null ? 'No attempt budget' : `${b.used} of ${b.attempts} attempts used`),
          h('span', 'text-fg', b.minutes == null ? 'No time budget' : `${b.minutes_used} of ${b.minutes} minutes used`),
          b.exhausted ? h('span', { className: 'text-needs font-medium', 'data-testid': 'budget-exhausted' }, capital(b.stopped || 'Budget used')) : null,
          h('span', 'text-muted', `Model usage ${pl.model_usage}`)),
        ro ? null : h('div', 'flex items-center gap-2',
          h('input', { className: cx(INPUT, 'w-24 mono'), name: 'budget', inputMode: 'numeric', 'aria-label': 'Attempts budget', value: budget == null ? (b.attempts == null ? '' : String(b.attempts)) : budget, onChange: e => setBudget(e.target.value) }),
          h('input', { className: cx(INPUT, 'w-24 mono'), name: 'budget_minutes', inputMode: 'numeric', 'aria-label': 'Minutes budget', value: mins == null ? (b.minutes == null ? '' : String(b.minutes)) : mins, onChange: e => setMins(e.target.value) }),
          h(Btn, { kind: 'small', testid: 'save-budget', disabled: budget == null && mins == null, onClick: saveBudget }, 'Save')))))
}

Object.assign(VIEWS, { architecture: Architecture, plan: Plan })
