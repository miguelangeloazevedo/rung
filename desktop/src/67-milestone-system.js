// ------------------------------------------------------------------ milestone system controls (decisions Round 24)
// Journeys (SYS-07), regression baseline (SYS-08), quality obligations (SYS-09), environment (SYS-10), change
// impact (SYS-11) on a milestone; the system report (SYS-12). Every verdict comes from the engine.

Object.assign(BADGE, {
  obligation_unmet: ['Obligation not met', 'bg-fail/10 text-fail border border-fail/30'],
  quality_unmet: ['Not met', 'bg-fail/10 text-fail border border-fail/30'],
  in_scope: ['In scope', 'bg-btn text-fg border border-line'],
  out_of_scope_j: ['Out of scope', 'bg-btn text-dim border border-line'],
  accepted: ['Accepted', 'bg-pass/10 text-pass border border-pass/30'],
  not_accepted: ['Not accepted', 'text-needs border border-needs']
})

const QUALITY = ['security', 'performance', 'resilience', 'accessibility', 'other']
const B_TONE = { failed: 'fail', contract_failed: 'fail', regression_failed: 'fail', migration_failed: 'fail', quality_unmet: 'fail', out_of_date: 'stale', contract_out_of_date: 'stale' }

const sysPost = (project, m, field, value) => post(`${P(project)}/milestones/${m.id}/system`, { field, value })

function Journeys({ project, m, ro, onErr }) {
  const empty = { name: '', in_scope: true, reason: '', check: '' }
  const [f, setF] = useState(empty)
  useDirty(!!(f.name.trim() || f.reason.trim()))
  const js = m.journeys || []
  const save = async list => { const x = await sysPost(project, m, 'journeys', list); onErr(x.ok ? '' : x.error); return x.ok }
  const add = async () => {
    const j = { name: f.name.trim(), in_scope: f.in_scope, reason: f.reason.trim(), check: f.check || null }
    if (await save([...js, j])) setF(empty)
  }
  const setCheck = (name, check) => save(js.map(j => j.name === name ? { ...j, check: check || null } : j))
  const cmdChecks = m.checks.map(c => c.check)
  return h(Section, { title: 'Journeys', testid: 'milestone-journeys' },
    h('div', 'flex flex-col gap-1.5',
      js.length ? frag(...js.map(j => h('div', { key: j.name, className: 'flex items-center gap-2 text-xs min-w-0', 'data-journey': j.name, 'data-scope': j.in_scope ? 'in' : 'out' },
        h('span', 'text-fg', j.name),
        h(Badge, { status: j.in_scope ? 'in_scope' : 'out_of_scope_j', small: true }),
        j.in_scope ? (ro ? h('span', 'mono text-[11px] text-muted', j.check || 'No check')
          : h('select', { className: cx(INPUT, 'w-28'), name: 'journey_check', 'aria-label': `${j.name} check`, value: j.check || '', onChange: e => setCheck(j.name, e.target.value) },
            h('option', { value: '' }, 'No check'), ...cmdChecks.map(c => h('option', { key: c, value: c }, c))))
          : h('span', { className: 'text-[11px] text-muted', 'data-testid': 'journey-reason' }, j.reason))))
        : h('span', 'text-xs text-dim', 'None'),
      ro ? null : h('div', 'flex flex-wrap items-center gap-2 pt-1',
        h('input', { className: cx(INPUT, 'w-48'), name: 'journey_name', 'aria-label': 'Journey', value: f.name, onChange: e => setF({ ...f, name: e.target.value }) }),
        h('label', 'flex items-center gap-1.5 text-xs text-fg min-h-[24px]',
          h('input', { type: 'checkbox', name: 'journey_in_scope', checked: f.in_scope, onChange: () => setF({ ...f, in_scope: !f.in_scope }) }), 'In scope'),
        f.in_scope ? null : h('input', { className: cx(INPUT, 'w-48'), name: 'journey_reason', 'aria-label': 'Reason', value: f.reason, onChange: e => setF({ ...f, reason: e.target.value }) }),
        h(Btn, { kind: 'small', testid: 'add-journey', disabled: !f.name.trim(), onClick: add }, 'Add journey'))))
}

function Obligations({ project, m, ro, onErr }) {
  const empty = { category: 'performance', command: '', measure: '', threshold: '', unit: '', direction: 'max', workload: '', environment: '' }
  const [f, setF] = useState(empty)
  useDirty(!!(f.command.trim() || f.measure.trim() || f.threshold.trim() || f.workload.trim()))
  const set = k => e => { const v = e.target.value; setF(cur => ({ ...cur, [k]: v })) }
  const qs = m.checks.filter(c => c.quality)
  const add = async () => {
    const x = await post(`${P(project)}/milestones/${m.id}/checks`, { type: 'command', command: f.command, quality: {
      category: f.category, measure: f.measure, threshold: f.threshold === '' ? null : Number(f.threshold), unit: f.unit,
      direction: f.direction, workload: f.workload, environment: f.environment } })
    if (!x.ok) return onErr(x.error)
    onErr(''); setF(empty)
  }
  return h(Section, { title: 'Quality obligations', testid: 'milestone-quality' },
    h('div', 'flex flex-col gap-1.5',
      qs.length ? frag(...qs.map(c => h('div', { key: c.check, className: 'flex flex-wrap items-center gap-2 text-xs', 'data-obligation': c.check, 'data-state': c.state },
        h('span', 'mono text-fg', c.check), h('span', 'text-fg', c.quality.category),
        c.quality.review ? h('span', 'text-muted', 'Review') : h('span', 'mono text-[11px] text-muted', `${c.quality.direction === 'min' ? '>=' : '<='} ${c.quality.threshold} ${c.quality.unit || ''}`),
        c.quality.workload ? h('span', 'text-[11px] text-muted', c.quality.workload) : null,
        c.measured_text ? h('span', { className: 'text-[11px] mono text-fg', 'data-testid': 'measured' }, c.measured_text) : null,
        h(Badge, { status: c.state, small: true }))))
        : h('span', 'text-xs text-dim', 'None'),
      ro || m.status !== 'draft' ? null : h('div', { className: 'flex flex-wrap items-center gap-2 pt-1', 'data-testid': 'obligation-form' },
        h('select', { className: cx(INPUT, 'w-28'), name: 'q_category', 'aria-label': 'Category', value: f.category, onChange: set('category') }, ...QUALITY.map(k => h('option', { key: k, value: k }, k))),
        h('input', { className: cx(INPUT, 'mono w-48'), name: 'q_command', 'aria-label': 'Command', value: f.command, onChange: set('command') }),
        h('input', { className: cx(INPUT, 'mono w-28'), name: 'q_measure', 'aria-label': 'Measure', value: f.measure, onChange: set('measure') }),
        h('select', { className: cx(INPUT, 'w-24'), name: 'q_direction', 'aria-label': 'Direction', value: f.direction, onChange: set('direction') }, h('option', { value: 'max' }, 'at most'), h('option', { value: 'min' }, 'at least')),
        h('input', { className: cx(INPUT, 'mono w-24'), name: 'q_threshold', inputMode: 'numeric', 'aria-label': 'Threshold', value: f.threshold, onChange: set('threshold') }),
        h('input', { className: cx(INPUT, 'w-24'), name: 'q_unit', 'aria-label': 'Unit', value: f.unit, onChange: set('unit') }),
        h('input', { className: cx(INPUT, 'w-48'), name: 'q_workload', 'aria-label': 'Workload', value: f.workload, onChange: set('workload') }),
        h('input', { className: cx(INPUT, 'w-48'), name: 'q_environment', 'aria-label': 'Environment', value: f.environment, onChange: set('environment') }),
        h(Btn, { kind: 'small', testid: 'add-obligation', disabled: !f.command.trim(), onClick: add }, 'Add obligation'))))
}

function Environment({ project, m, ro, onErr }) {
  const env = m.environment || { probes: [], migration: '' }
  const [pr, setPr] = useState({ command: '', contains: '' })
  const [mig, setMig] = useState(null)
  useDirty(!!(pr.command.trim() || pr.contains.trim() || (mig !== null && mig !== env.migration)))
  const rec = m.env_run || {}
  const save = async v => { const x = await sysPost(project, m, 'environment', v); onErr(x.ok ? '' : x.error); return x.ok }
  const addProbe = async () => { if (await save({ ...env, probes: [...env.probes, pr] })) setPr({ command: '', contains: '' }) }
  return h(Section, { title: 'Environment', testid: 'milestone-environment' },
    h('div', 'flex flex-col gap-1.5 text-xs',
      ...env.probes.map(p => {
        const got = (rec.probes || []).find(x => x.command === p.command)
        return h('div', { key: p.command, className: 'flex flex-wrap items-center gap-2', 'data-probe': p.command, 'data-ok': got ? String(got.ok) : '' },
          h('span', 'mono text-fg', p.command), h('span', 'text-muted', 'contains'), h('span', 'mono text-fg', p.contains),
          got ? h('span', { className: cx('mono text-[11px]', got.ok ? 'text-muted' : 'text-fail'), 'data-testid': 'probe-output' }, got.output || '(empty)') : h('span', 'text-dim', 'Not run'))
      }),
      env.migration ? h('div', { className: 'flex items-center gap-2', 'data-testid': 'migration' }, h('span', 'text-muted', 'Migration'), h('span', 'mono text-fg', env.migration),
        rec.migration ? h('span', { className: cx('mono text-[11px]', rec.migration.ok ? 'text-muted' : 'text-fail') }, `exit ${rec.migration.exit_code}`) : null) : null,
      !env.probes.length && !env.migration ? h('span', 'text-dim', 'None') : null,
      ro ? null : h('div', 'flex flex-wrap items-center gap-2 pt-1',
        h('input', { className: cx(INPUT, 'mono w-48'), name: 'probe_command', 'aria-label': 'Probe command', value: pr.command, onChange: e => setPr({ ...pr, command: e.target.value }) }),
        h('input', { className: cx(INPUT, 'mono w-28'), name: 'probe_contains', 'aria-label': 'Must contain', value: pr.contains, onChange: e => setPr({ ...pr, contains: e.target.value }) }),
        h(Btn, { kind: 'small', testid: 'add-probe', disabled: !pr.command.trim() || !pr.contains, onClick: addProbe }, 'Add probe'),
        h('input', { className: cx(INPUT, 'mono w-48'), name: 'migration', 'aria-label': 'Migration command', value: mig == null ? env.migration : mig, onChange: e => setMig(e.target.value) }),
        h(Btn, { kind: 'small', testid: 'save-migration', disabled: mig == null || mig === env.migration, onClick: async () => { if (await save({ ...env, migration: mig })) setMig(null) } }, 'Save migration'))))
}

function Baseline({ project, m, ro, onErr }) {
  const lq = useApi(`${P(project)}/milestones`)
  const base = m.baseline || { milestones: [], command: '' }
  const earlier = (lq.data || []).filter(x => x.id !== m.id && Number(x.id.split('-')[1]) < Number(m.id.split('-')[1]))
  const [cmd, setCmd] = useState(null)
  useDirty(cmd !== null && cmd !== base.command)
  const save = async v => { const x = await sysPost(project, m, 'baseline', v); onErr(x.ok ? '' : x.error); return x.ok }
  const toggle = id => save({ ...base, milestones: base.milestones.includes(id) ? base.milestones.filter(x => x !== id) : [...base.milestones, id] })
  if (!earlier.length && !base.milestones.length && !base.command) return null
  return h(Section, { title: 'Regression baseline', testid: 'milestone-baseline' },
    h('div', 'flex flex-wrap items-center gap-3 text-xs',
      ...earlier.map(x => h('label', { key: x.id, className: 'flex items-center gap-1.5 min-h-[24px] text-fg' },
        h('input', { type: 'checkbox', name: 'baseline', value: x.id, checked: base.milestones.includes(x.id), disabled: ro, onChange: () => toggle(x.id) }), h('span', 'mono', x.id), h('span', 'text-muted', x.title))),
      ro ? (base.command ? h('span', 'mono text-fg', base.command) : null) : frag(
        h('input', { className: cx(INPUT, 'mono w-48'), name: 'baseline_command', 'aria-label': 'Baseline command', value: cmd == null ? base.command : cmd, onChange: e => setCmd(e.target.value) }),
        h(Btn, { kind: 'small', testid: 'save-baseline', disabled: cmd == null || cmd === base.command, onClick: async () => { if (await save({ ...base, command: cmd })) setCmd(null) } }, 'Save'))))
}

function Impact({ project, m, ro, onErr }) {
  const all = async () => { const x = await post(`${P(project)}/check-everything`, {}); onErr(x.ok ? '' : x.error) }
  return h('div', { className: 'flex flex-wrap items-center justify-between gap-2 text-xs', 'data-testid': 'judged-on' },
    h('span', 'text-muted', m.judged_on || ''),
    ro ? null : h(Btn, { kind: 'small', testid: 'check-everything', onClick: all }, 'Check everything'))
}

function MilestoneSystem(props) {
  return frag(h(Impact, props), h(Journeys, props), h(Obligations, props), h(Environment, props), h(Baseline, props))
}

// The system report (SYS-12): every milestone, Accepted only when all are verified now.
function SystemReport({ project }) {
  const q = useApi(`${P(project)}/system-report`, { live: true })
  useExit(() => goBack('milestones'))
  if (q.error) return h(Missing, { project, text: errText(q.error) })
  const r = q.data
  return h(Page, { project, title: 'System report', back: () => goBack('milestones') },
    !r ? h(Loading) : h(Card, { className: 'p-4 flex flex-col gap-3', testid: 'system-report' },
      h('div', 'flex items-center justify-between gap-3',
        h('span', 'text-[11px] mono text-muted', `code ${r.basis}`),
        h('span', { 'data-testid': 'report-verdict', 'data-accepted': String(r.accepted) }, h(Badge, { status: r.accepted ? 'accepted' : 'not_accepted' }))),
      r.open.length ? h('div', { className: 'flex flex-col gap-1', 'data-testid': 'report-open' },
        ...r.open.map((x, i) => h('div', { key: i, className: 'flex items-center gap-2 text-xs' }, h(Dot, { t: 'needs' }), h('span', 'text-fg', x)))) : null,
      h(Well, { className: 'text-xs mono text-fg whitespace-pre-wrap', testid: 'report-markdown' }, r.markdown)))
}

Object.assign(VIEWS, { 'system-report': SystemReport })
