// Rung desktop pane: home, project picker, new project, settings.

function useCurrent() {
  const st = useApi('/state')
  const s = st.data
  return { state: s, project: s && s.current, loading: st.isLoading, error: st.error }
}

function execLine(x) {
  const bits = [`#${x.n} ${x.status === 'pending' ? 'pending' : x.status}`]
  if (x.commit) bits.push(x.commit)
  if (x.carried_by || x.recorder) bits.push(x.carried_by || x.recorder)
  if (x.duration != null) bits.push(dur(x.duration))
  if (x.started_at) bits.push(clock(x.started_at))
  return bits.join(' · ')
}

function ExecList({ test, execs, limit, showTest }) {
  const rows = (execs || []).slice(0, limit || 3)
  if (!rows.length) return h('div', 'bg-well p-2.5 rounded-[6px] border border-line2 font-mono text-[11px] text-dim', 'No executions yet')
  return h('div', 'flex flex-col gap-1.5 bg-well p-2.5 rounded-[6px] border border-line2 font-mono text-[11px]',
    ...rows.map(x => {
      const dead = x.invalidated && x.status === 'pass'  // an upstream edit voids passes; earlier fails stay failed
      const t = dead ? 'dim' : x.status === 'pass' ? 'pass' : x.status === 'fail' ? 'fail' : x.status === 'pending' || x.status === 'error' ? 'needs' : 'dim'
      return h('div', {
        key: `${x.test || test}#${x.n}`,
        className: cx('flex items-center justify-between py-0.5 cursor-pointer', dead ? 'line-through text-dim' : 'text-fg'),
        'data-exec': `${x.test || test}#${x.n}`,
        onClick: () => navigate('exec', { test: x.test || test, n: x.n })
      },
      h('div', 'flex items-center gap-2', h(Dot, { t }), h('span', null, showTest ? `${x.test} ${execLine(x)}` : execLine(x))),
      dead
        ? h('span', 'text-[10px] no-underline text-dim italic', `invalidated by ${String(x.invalidated_by || 'an upstream edit').replace(/ edited$/, ' edit')}`)
        : h('span', { className: cx('text-[10px]', TONE_TEXT[t]) }, x.status === 'pass' ? 'pass' : x.status === 'fail' ? 'failed' : x.status))
    }))
}

function StaleCard({ project, item, ro }) {
  const r = useApi(`/projects/${encodeURIComponent(project)}/rungs/${item.id}`).data
  const tests = r && r.kind === 'specification' ? (r.children || []).filter(c => c.type === 'command' && c.status !== 'dismissed') : []
  const first = tests[0]
  const ex = useApi(first ? `/projects/${encodeURIComponent(project)}/tests/${first.id}/executions` : null, { enabled: !!first }).data
  const ch = item.change
  const path = (r && r.path) || []
  const [err, setErr] = useState('')
  return h(Card, { nested: true, className: 'r-ny p-4 flex flex-col gap-3.5', testid: 'needs-you-item', onClick: () => navigate('rung', { rid: item.id }) },
    h('div', 'flex flex-col gap-1.5',
      h('div', 'flex items-center justify-between',
        h('div', 'text-[11px] mono text-muted font-medium flex items-center gap-1.5',
          ...path.flatMap(p => [h('span', { key: p.id }, p.id), h('span', { key: p.id + '>' }, '›')]),
          h('span', 'whitespace-nowrap text-needs', item.id)),
        h(Badge, { status: 'stale' })),
      h('button', { type: 'button', className: 'text-left text-sm font-semibold text-fg hover:underline', onClick: e => { e.stopPropagation(); navigate('rung', { rid: item.id }) } }, `${item.id} · ${item.text}`),
      ch ? h('div', 'text-[12px] text-muted flex items-center gap-1.5',
        h('span', {
          className: 'cursor-pointer hover:text-fg',
          onClick: e => { e.stopPropagation(); navigate('change', { change: ch.id, rid: item.id }) }
        }, `${ch.rung} · ${ch.after} · edited ${ago(ch.at)}`)) : null),
    first ? h('div', 'flex flex-col gap-2 pt-2 border-t border-line',
      h('div', 'flex items-center justify-between text-[11px] text-muted',
        h('span', 'font-medium mono text-fg', `${first.id} · ${first.command || first.text}`),
        h('span', { className: TONE_TEXT[tone(first)] }, first.status === 'stale' ? 'stale' : resultWord(first.result))),
      h(ExecList, { test: first.id, execs: ex })) : null,
    ro ? null : h('div', 'flex items-center gap-2 pt-2 border-t border-line',
      h(Btn, { kind: 'primary', testid: 'approve', onClick: async () => { const res = await post(`/projects/${encodeURIComponent(project)}/rungs/${item.id}/approve`); setErr(res.ok ? '' : res.error) } }, 'Approve'),
      item.kind === 'specification' ? h(Btn, { onClick: () => navigate('rung', { rid: item.id }) }, 'Develop until green') : null,
      first ? h(Btn, { onClick: () => navigate('defect-new', { test: first.id }) }, 'Raise defect') : null,
      h(ErrorLine, { text: err })))
}

// Who proposed it and where, from data only: a missing part is left out, never filled with a placeholder.
function proposalSource(item) {
  const sc = item.source_chat
  return [item.proposer ? `by ${item.proposer}` : null, sc ? (/^run \d+$/.test(sc) ? `from ${sc}` : `from chat "${sc}"`) : null].filter(Boolean).join(' · ')
}

function ProposedCard({ project, item, ro }) {
  const [err, setErr] = useState('')
  const act = async which => {
    const res = await post(`/projects/${encodeURIComponent(project)}/rungs/${item.id}/${which}`)
    setErr(res.ok ? '' : res.error)
  }
  return h('div', {
    className: 'r-ny bg-card border border-line rounded-[6px] px-4 py-3 flex items-center justify-between',
    style: { borderLeft: '3px solid var(--r-needs)' },
    'data-testid': 'needs-you-item', 'data-proposed': item.id
  },
  h('div', 'flex flex-col gap-1',
    h('div', 'flex items-center gap-2 text-xs',
      h('span', 'px-1.5 py-0.5 rounded border border-needs text-needs text-[10px] font-semibold uppercase tracking-wider whitespace-nowrap shrink-0', 'Proposed'),
      h('span', 'whitespace-nowrap mono text-muted', item.id),
      h('span', { className: 'text-muted', 'data-testid': 'proposal-source' }, proposalSource(item))),
    h('span', 'text-sm text-fg', item.text),
    h('span', 'text-[11px] text-muted mono', `${item.parent} › ${item.id}`),
    h(ErrorLine, { text: err })),
  ro ? null : h('div', 'flex items-center gap-2',
    h(Btn, { kind: 'acceptSolid', testid: 'accept', onClick: () => act('approve') }, 'Accept'),
    h(Btn, { kind: 'ghostLine', testid: 'dismiss', onClick: () => act('dismiss') }, 'Dismiss')))
}

function ApprovalCard({ project, item, ro }) {
  const [err, setErr] = useState('')
  return h(Card, { className: 'r-ny px-4 py-3 flex items-center justify-between', testid: 'needs-you-item' },
    h('div', 'flex flex-col gap-1',
      h('div', 'flex items-center gap-2 text-xs',
        h(Badge, { status: 'pending' }),
        h('span', 'mono text-muted', `${item.id} #${item.n}`),
        h('span', 'text-muted', `recorded by ${item.recorder || 'you'}`)),
      h('span', 'text-sm text-fg', item.text),
      item.note ? h('span', 'text-[11px] text-muted', item.note) : null,
      h(ErrorLine, { text: err })),
    h('div', 'flex items-center gap-2',
      ro ? null : h(Btn, { kind: 'acceptSolid', testid: 'approve-result', onClick: async () => { const r = await post(`/projects/${encodeURIComponent(project)}/tests/${item.id}/executions/${item.n}/approve`); setErr(r.ok ? '' : r.error) } }, 'Approve result'),
      h(Btn, { kind: 'ghostLine', onClick: () => navigate('rung', { rid: item.id }) }, 'Open')))
}

function RunningRow({ run }) {
  const last = run.attempts[run.attempts.length - 1]
  const n = last ? last.n : 1
  const pct = Math.max(8, Math.min(100, Math.round(((n - 1) + 0.5) / run.max_attempts * 100)))
  const secs = run.started_at ? Date.now() / 1000 - run.started_at : 0
  return h(Card, { className: 'p-3 flex flex-col gap-2', testid: 'running-item', onClick: () => navigate('run', { run: run.id }) },
    h('div', 'flex items-center justify-between text-xs',
      h('span', 'text-fg mono', `${run.spec} · ${run.profile} · attempt ${n} of ${run.max_attempts} · running ${dur(secs)}`),
      h('span', 'text-[11px] text-needs font-medium', run.status === 'queued' ? 'queued' : 'in progress')),
    h('div', 'w-full h-1 bg-btn rounded-full overflow-hidden',
      h('div', { className: 'h-full bg-needs rounded-full', style: { width: `${pct}%` } })))
}

function Home({ project }) {
  const q = useApi(`/projects/${encodeURIComponent(project)}/home`, { live: true })
  const d = q.data
  // Home polls itself; the status bar chip follows the change ticker. Refetch the chip as soon as Home sees a
  // different Needs you count, so the two never show different numbers.
  const ny = d && d.tiles ? d.tiles.needs_you : null
  useEffect(() => { if (ny != null) queryClient.invalidateQueries({ queryKey: ['rung', '/state'] }) }, [ny])
  if (!d) return q.error ? h(Missing, { project, text: errText(q.error) }) : h(Frame, { main: h(Loading) })
  const items = d.needs_you || []
  const stale = items.filter(i => i.type === 'stale')
  const approvals = items.filter(i => i.type === 'approval')
  const proposed = items.filter(i => i.type === 'proposed')
  const errors = items.filter(i => i.type === 'error')
  const inputs = items.filter(i => i.type === 'needs_input')
  const ro = !!(d.tiles && d.tiles.archived)
  const head = h('header', 'flex flex-col gap-4', h(Header, { project, ro, extra: h(PasteBtn, { project, kind: 'head' }), back: cameFrom('projects') ? () => goBack('projects') : undefined }), ro ? h(ArchivedBar, { project }) : null,
    h(Tiles, { tiles: d.tiles }), ro ? null : h(FirstGreen, { project, need: ((d.tree || []).find(n => n.status !== 'dismissed') || {}).id }))
  const sel = d.allocation && d.allocation.spec
  if (!(d.needs || []).length) {
    return h(Frame, {
      main: frag(head,
        h('div', { className: 'flex-1 flex flex-col items-center justify-center py-20 gap-4', 'data-testid': 'empty-project' },
          h('div', 'w-12 h-12 rounded-[6px] bg-card border border-line flex items-center justify-center text-muted', '≡'),
          h('h2', 'text-base font-semibold text-fg', 'No needs yet'),
          ro ? null : h('button', { type: 'button', className: 'px-4 py-2 rounded-[6px] bg-needs text-on-needs font-medium text-xs', onClick: () => navigate('need-new') }, 'Write the first need'),
          d.retired ? h('button', { type: 'button', className: 'text-[11px] text-muted hover:text-fg', 'data-testid': 'retired-link', onClick: () => navigate('retired') }, `Retired ${d.retired}`) : null))
    })
  }
  const main = frag(
    head,
    h('section', { className: 'flex flex-col gap-2.5', 'data-testid': 'needs-you' },
      h(SectionTitle, { tone: items.length ? 'needs' : null, dot: items.length ? 'needs' : 'dim', right: items.length ? '' : 'Priority queue' }, 'Needs you'),
      items.length
        ? frag(...stale.map(i => h(StaleCard, { key: 's' + i.id, project, item: i, ro })),
          ...errors.map(i => h(ErrorCard, { key: 'e' + i.id + i.n, project, item: i, ro })),
          ...inputs.map(i => h(NeedsInputCard, { key: 'i' + i.run, project, item: i, ro })),
          ...approvals.map(i => h(ApprovalCard, { key: 'a' + i.id + i.n, project, item: i, ro })))
        : h('div', 'bg-card border border-line rounded-[6px] p-3 text-xs text-dim', 'Nothing needs you'),
      proposed.length ? h('div', 'flex flex-col gap-2 mt-3', ...proposed.map(i => h(ProposedCard, { key: 'p' + i.id, project, item: i, ro }))) : null),
    h('section', { className: 'flex flex-col gap-2', 'data-testid': 'running' },
      h(SectionTitle, { dot: (d.running || []).length || (d.claims || []).length || (d.running_tests || []).length ? 'needs' : 'dim' }, 'Running'),
      (d.running || []).length || (d.running_tests || []).length || (d.claims || []).length
        ? frag(...d.running.map(r => h(RunningRow, { key: r.id, run: r })),
          ...(d.claims || []).map(c => h(ClaimRow, { key: 'c' + c.id, c })),
          ...(d.running_tests || []).map(x => h(Card, { key: x.test + x.n, className: 'p-3 flex items-center justify-between text-xs', onClick: () => navigate('exec', { test: x.test, n: x.n }) },
            h('span', 'text-fg mono', `${x.test} · execution #${x.n} · running ${dur(Date.now() / 1000 - x.started_at)}`),
            h('span', 'text-[11px] text-needs font-medium', 'in progress'))))
        : h('div', 'bg-card border border-line rounded-[6px] p-3 text-xs text-dim', 'Nothing running')),
    (d.done || []).length ? h('section', { className: 'flex flex-col gap-2', 'data-testid': 'done' },
      h(SectionTitle, { dot: 'pass' }, 'Done'),
      ...d.done.map(s => h(Card, { key: s.id, className: 'p-3 flex items-center justify-between opacity-80 hover:opacity-100', onClick: () => navigate('rung', { rid: s.id }) },
        h('div', 'flex items-center gap-2.5', h(Dot, { t: 'pass' }),
          h('span', 'whitespace-nowrap text-xs font-medium text-fg', s.id), h('span', 'text-xs text-muted', s.text)),
        h('span', 'text-xs font-medium text-pass flex items-center gap-1',
          s.tests.length === 1 ? `${s.tests[0].id} pass` : 'Pass')))) : null,  // home.html names a lone test; home-notes.html says Pass
    (d.draft || []).length ? h('section', { className: 'flex flex-col gap-2', 'data-testid': 'draft' },
      h(SectionTitle, { dot: 'dim' }, 'Draft'),
      ...d.draft.map(r => h(Card, { key: r.id, className: 'p-3 flex items-center justify-between text-dim', onClick: () => navigate('rung', { rid: r.id }) },
        h('div', 'flex items-center gap-2.5', h(Dot, { t: 'dim' }),
          h('span', 'whitespace-nowrap text-xs font-medium', r.id), h('span', 'text-xs', r.text),
          (r.specs || []).length ? h('span', 'text-[11px] text-dim', '· ' + r.specs.join(', ')) : null),
        h('span', 'text-xs', 'draft')))) : null)
  return h(Frame, { main, rail: h(Rail, { tree: d.tree, alloc: d.allocation, sel, retired: d.retired }) })
}

// ------------------------------------------------------------------ project picker

function StatChip({ label, n, t, of }) {
  const zero = !n && of == null
  let cls = 'bg-btn text-muted border border-line'
  if (!zero) {
    if (t === 'needs') cls = 'bg-needs/10 text-needs border border-needs'
    if (t === 'running') cls = 'border border-needs text-needs'
    if (t === 'stale') cls = 'bg-stale/15 text-stale border border-stale/30'
  }
  if (of != null) cls = n > 0 || of === 0 ? 'text-pass border border-pass/30' : 'text-dim border border-line'
  if (of != null && n === 0 && of > 0) cls = 'text-dim border border-line'
  return h('span', { className: cx('inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium', cls), 'data-stat': label },
    of != null ? `${n} of ${of} ${label.toLowerCase()}` : `${label} ${n}`)
}

// What an item in Needs you asks of you, and where Open takes it.
const NEED_WORD = { stale: 'Stale', proposed: 'Proposed', approval: 'Pending approval', error: 'Could not run', needs_input: 'Needs input' }
// Same destinations as the dock's rows.
function openNyItem(item) {
  if (item.type === 'error') return navigate('exec', { test: item.id, n: item.n })
  if (item.type === 'needs_input') return navigate('run', { run: item.run })
  return navigate('rung', { rid: item.id })
}
const needCount = n => `${n} ${n === 1 ? 'needs' : 'need'} you`

// The front page (Rounds 12 and 16): what needs you across every open project, grouped by project, with the
// project list beside it. Rung opens here only when no project is current; the project name in a header opens it.
function Projects({ tab }) {
  const back = useState(() => canGoBack())[0]  // opened from a view (the project name): Back returns to it
  const stQ = useApi('/state')
  const ovQ = useApi('/overview', { live: true })
  const st = stQ.data
  const ov = ovQ.data
  const [qtext, setQ] = useState('')
  const [err, setErr] = useState('')
  const archived = tab === 'archived'
  const enter = async (name, then) => {
    const x = await post(`/projects/${encodeURIComponent(name)}/open`)
    if (!x.ok) return setErr(x.error)
    if (then) then(); else navigate('home')
  }
  const rows = ((st && st.projects) || []).filter(p => !qtext || p.name.toLowerCase().includes(qtext.toLowerCase()))
  rows.sort((a, b) => (b.stats.last_activity || 0) - (a.stats.last_activity || 0))
  const groups = (ov && ov.projects) || []
  const waiting = groups.filter(g => g.items.length)
  const idle = groups.filter(g => !g.items.length)
  const openBtn = (name) => h(Btn, { kind: 'small', className: 'shrink-0 whitespace-nowrap', testid: 'open-project', label: `Open project ${name}`, onClick: () => enter(name) }, 'Open project')
  const runLink = (g, x) => h(Btn, {
    kind: 'ghostLine', key: `${x.kind}${x.run || x.id}${x.n || ''}`, testid: 'ny-running',
    onClick: () => enter(g.name, () => (x.kind === 'run' ? navigate('run', { run: x.run }) : navigate('exec', { test: x.id, n: x.n })))
  }, x.kind === 'run' ? `${x.id} running · ${x.profile}` : `${x.id} #${x.n} running`)
  const group = g => h('section', { key: g.name, className: 'bg-card border border-line rounded-[6px] flex flex-col', 'data-testid': 'ny-group', 'data-project': g.name, 'aria-labelledby': `ny-${g.name}` },
    h('div', 'flex flex-wrap items-center justify-between gap-2 px-4 py-3 border-b border-line',
      h('div', 'flex flex-wrap items-center gap-2 min-w-0',
        h('h2', { id: `ny-${g.name}`, className: 'text-sm font-semibold text-fg' }, g.name),
        h('span', { className: 'px-2 py-0.5 rounded text-[11px] font-medium border border-needs text-needs', 'data-testid': 'ny-count' }, needCount(g.items.length)),
        ...g.running.map(x => runLink(g, x))),
      openBtn(g.name)),
    h('ul', 'flex flex-col',
      ...g.items.map((item, i) => h('li', { key: `${item.type}${item.id}${item.n || ''}`, className: cx('r-ny flex items-center justify-between gap-3 px-4 py-2.5', i && 'border-t border-line'), 'data-testid': 'ny-item', 'data-item': item.id },
        h('div', 'flex flex-col gap-0.5 min-w-0',
          h('div', 'flex items-center gap-2 text-[11px]',
            h('span', 'mono text-needs font-medium', item.n ? `${item.id} #${item.n}` : item.id),
            h('span', { className: 'text-muted', 'data-testid': 'ny-need' }, NEED_WORD[item.type] || item.type)),
          h('span', { className: 'text-xs text-fg truncate', title: item.text }, item.text)),
        h(Btn, { kind: 'small', className: 'shrink-0 whitespace-nowrap', testid: 'ny-open', label: `Open ${item.id}`, onClick: () => enter(g.name, () => openNyItem(item)) }, 'Open')))))
  const idleRow = (g, i) => h('div', { key: g.name, className: cx('flex flex-wrap items-center justify-between gap-2 px-4 py-2.5', i && 'border-t border-line'), 'data-testid': 'ny-idle', 'data-project': g.name },
    h('div', 'flex flex-wrap items-center gap-3 text-xs',
      h('span', 'font-semibold text-fg', g.name),
      h('span', { className: 'text-muted', 'data-stat': 'Stale' }, `${g.stats.stale} stale`),
      h('span', { className: 'text-muted', 'data-stat': 'Covered' }, `${g.stats.covered} of ${g.stats.requirements} covered`)),
    openBtn(g.name))
  const front = ovQ.error
    ? h('div', 'flex flex-col gap-2', h(ErrorLine, { text: errText(ovQ.error) }), h('div', null, h(Btn, { testid: 'retry', onClick: () => ovQ.refetch() }, 'Retry')))
    : !ov ? h(Loading)
      : frag(
        waiting.length ? h('div', { className: 'flex flex-col gap-4', 'data-testid': 'ny-groups' }, ...waiting.map(group))
          : h('div', { className: 'bg-card border border-line rounded-[6px] p-3 text-xs text-muted', 'data-testid': 'ny-empty' }, 'Nothing needs you'),
        idle.length ? h('section', { className: 'flex flex-col gap-2', 'aria-labelledby': 'ny-idle-title' },
          h('h2', { id: 'ny-idle-title', className: 'text-xs font-semibold uppercase tracking-wider text-muted' }, 'Nothing waiting'),
          h('div', { className: 'bg-card border border-line rounded-[6px] flex flex-col', 'data-testid': 'ny-idle-list' }, ...idle.map(idleRow))) : null)
  const side = h('aside', { className: 'r-side flex flex-col gap-3', 'data-testid': 'project-side', 'aria-labelledby': 'rung-projects-title' },
    h('h2', { id: 'rung-projects-title', className: 'text-xs font-semibold uppercase tracking-wider text-muted' }, 'Projects'),
    h('div', 'flex items-center bg-card border border-line rounded-[6px] px-3 py-1.5 gap-2',
      h('span', { className: 'text-muted text-xs', 'aria-hidden': 'true' }, '⌕'),
      h('input', { className: 'bg-transparent text-xs text-fg outline-none w-full placeholder:text-muted', placeholder: 'Search projects', type: 'text', name: 'search', value: qtext, onChange: e => setQ(e.target.value) })),
    archived || (st && st.archived) ? h(Seg, { options: [['active', 'Active'], ['archived', `Archived ${(st && st.archived) || 0}`]], value: archived ? 'archived' : 'active', testid: 'project-filter', onChange: v => navigate('projects', v === 'archived' ? { tab: 'archived' } : null, { replace: true }) }) : null,
    h(ErrorLine, { text: err }),  // a failed /state load shows once, in the frame (LoadErrors)
    archived ? null : h('div', { className: 'flex flex-col gap-2', 'data-testid': 'project-list' },
      st && !rows.length ? h('div', 'bg-card border border-line rounded-[6px] p-3 text-xs text-muted flex items-center justify-between gap-2',
        h('span', { 'data-testid': 'empty' }, qtext ? 'No matching projects' : 'No projects'),
        qtext ? h(Btn, { kind: 'small', testid: 'clear-search', onClick: () => setQ('') }, 'Clear search') : h(Btn, { kind: 'small', onClick: () => navigate('project-new') }, 'New project')) : null,
      ...rows.map(p => h(Card, {
        key: p.name, className: 'p-3 flex flex-col gap-2', testid: 'project-row',
        onClick: () => enter(p.name)
      },
      h('div', 'flex items-center justify-between gap-2',
        h('div', 'flex flex-col gap-0.5 min-w-0',
          h('div', { className: 'text-sm font-semibold text-fg', 'data-testid': 'project-row-name' }, p.name),
          h('div', { className: 'text-xs mono text-muted truncate', title: p.folder }, shortPath(p.folder))),
        st && st.current === p.name ? h('span', { className: 'text-[10px] font-medium text-needs border border-needs rounded px-1.5 py-0.5 whitespace-nowrap', 'data-testid': 'last-opened' }, 'Last opened') : null),
      h('div', 'flex flex-wrap items-center gap-1.5',
        h(StatChip, { label: 'Needs you', n: p.stats.needs_you, t: 'needs' }),
        h(StatChip, { label: 'Running', n: p.stats.running, t: 'running' }),
        h(StatChip, { label: 'Stale', n: p.stats.stale, t: 'stale' }),
        h(StatChip, { label: 'Covered', n: p.stats.covered, of: p.stats.requirements }),
        h('span', { className: 'text-xs text-muted', 'data-stat': 'Last activity' }, ago(p.stats.last_activity)))))))
  const main = frag(
    h('header', 'flex flex-wrap items-center justify-between gap-3',
      h('div', 'flex items-baseline gap-3',
        h('h1', { className: 'text-xl font-bold tracking-tight text-fg', 'data-page-title': '1', tabIndex: -1 }, archived ? 'Archived projects' : 'Needs you'),
        !archived && ov ? h('span', { className: 'text-xl font-bold mono text-needs', 'data-testid': 'ny-total' }, String(ov.total)) : null),
      h('div', 'flex flex-wrap items-center gap-2',
        back ? h(ExitBtn, { kind: 'head', testid: 'page-back', onClick: () => goBack('home') }, 'Back') : null,
        !archived && st && (st.projects || []).length ? h(PasteBtn, { project: st.current, projects: st.projects.map(p => p.name) }) : null,
        h(Btn, { onClick: () => navigate('settings') }, 'Settings'),
        h(Btn, { kind: 'primary', onClick: () => navigate('project-new') }, 'New project'))),
    h('div', 'r-cols flex flex-wrap items-start gap-6',
      h('div', { className: 'r-col-main flex flex-col gap-4', 'data-testid': 'needs-you-front' },
        archived ? h(ArchivedList, { qtext, onClear: () => setQ('') }) : front),
      side))
  return h('div', 'relative h-full w-full', h(Frame, { main, wide: true }))
}

// ------------------------------------------------------------------ new project

function NewProject() {
  const stQ = useApi('/state')
  const st = stQ.data
  const profiles = ((st && st.profiles) || []).map(p => p.name)
  const [name, setName] = useState('')
  const [folder, setFolder] = useState('')
  const [cmd, setCmd] = useState('')
  const [picked, setPicked] = useState([])
  const [err, setErr] = useState('')
  const [errs, setErrs] = useState({})
  const touched = useRef({})
  const hasProjects = st && st.projects && st.projects.length
  // With no project yet, the way out is the start screen (its choices stay reachable after it was dismissed).
  const backToStart = !!st && !hasProjects
  // Cancel is the explicit discard; Back (the way back to the start screen) asks first when text is typed.
  const exit = hasProjects ? () => goBack('projects', null, { force: true }) : () => navigate('start', null, { replace: true })
  useDirty(name.trim() || folder.trim() || cmd.trim())
  useExit(hasProjects ? () => goBack('projects') : exit, true)
  const fill = async path => {
    // Name, test command and profiles follow the folder until the person edits them.
    if (!path.trim()) return
    try {
      const d = await rest('/projects/defaults', { method: 'POST', body: { folder: path.trim() } })
      if (!touched.current.name) setName(d.name || '')
      if (!touched.current.cmd) setCmd(d.test_command || '')
      if (!touched.current.profiles) setPicked(d.profiles || [])
    } catch (_) { /* the field error shows on create */ }
  }
  const create = async () => {
    const res = await post('/projects', { name: name.trim(), folder: folder.trim(), test_command: cmd.trim(), profiles: picked })
    if (res.ok) { finish('home'); return notify(`Created ${res.data && res.data.name ? res.data.name : name.trim()}`) }
    setErrs(res.fields || (res.field ? { [res.field]: res.error } : {}))
    setErr(res.field ? '' : res.error)
    if (res.field) focusInvalid()
  }
  const fe = k => errs[k] ? h('span', { className: 'text-[11px] text-fail', id: 'fe-' + k, role: 'alert', 'data-testid': 'field-error', 'data-field': k }, errs[k]) : null
  const bad = k => (errs[k] ? 'true' : undefined)
  const inp = 'w-full px-3 py-2 bg-well border border-line rounded-[6px] text-xs text-fg outline-none focus:border-needs'
  const main = h('div', { className: 'flex-1 h-full overflow-y-auto flex p-4', 'data-testid': 'new-project' },
    h('div', 'm-auto w-full max-w-[640px] bg-card border border-line rounded-[6px] p-6 flex flex-col gap-6',
      h('h1', { className: 'text-xl font-bold tracking-tight text-fg', 'data-page-title': '1', tabIndex: -1 }, 'New project'),
      h(LoadErrors),
      h('div', 'flex flex-col gap-4',
        h('div', 'flex flex-col gap-1.5',
          h('label', 'text-xs font-medium text-muted', 'Name'),
          h('input', { className: inp, type: 'text', name: 'name', 'aria-invalid': bad('name'), value: name, onChange: e => { touched.current.name = true; setName(e.target.value) } }), fe('name')),
        h('div', 'flex flex-col gap-1.5',
          h('label', 'text-xs font-medium text-muted', 'Folder'),
          h(FolderInput, { className: inp, value: folder, invalid: !!errs.folder,
            onChange: (v, done) => { setFolder(v); if (done) fill(v) }, onPicked: p => { setFolder(p); fill(p) } }), fe('folder')),
        h('div', 'flex flex-col gap-1.5',
          h('label', 'text-xs font-medium text-muted', 'Test command'),
          h('input', { className: cx(inp, 'font-mono'), type: 'text', name: 'test_command', 'aria-invalid': bad('test_command'), value: cmd, onChange: e => { touched.current.cmd = true; setCmd(e.target.value) } }), fe('test_command')),
        h('div', 'flex flex-col gap-2',
          h('label', 'text-xs font-medium text-muted', 'Profiles'),
          h('div', 'flex flex-col gap-2 pt-1',
            ...profiles.map(p => h('label', { key: p, className: 'flex items-center gap-2.5 text-xs text-fg cursor-pointer' },
              h('input', {
                type: 'checkbox', className: 'rounded accent-needs', name: 'profile', value: p, checked: picked.includes(p),
                onChange: e => { touched.current.profiles = true; setPicked(e.target.checked ? [...picked, p] : picked.filter(x => x !== p)) }
              }),
              h('span', null, p)))), fe('profiles'))),
      h(ErrorLine, { text: err }),  // a failed /state load shows once, in the frame (LoadErrors)
      h('div', 'flex items-center justify-end gap-2 pt-4 border-t border-line',
        hasProjects ? h(Btn, { onClick: exit }, 'Cancel')
          : backToStart ? h(Btn, { testid: 'back-to-start', onClick: exit }, 'Back') : null,
        h(Btn, { kind: 'primary', testid: 'create-project', onClick: create }, 'Create project'))))
  return h('div', 'flex flex-row h-full w-full overflow-hidden', main)
}

// ------------------------------------------------------------------ settings

const COLOUR_ROWS = [['needs_you', 'Needs you', 'needs'], ['pass', 'Pass', 'pass'], ['fail', 'Fail', 'fail'], ['stale', 'Stale', 'stale'], ['draft', 'Draft', 'dim']]
const FIXED = [['theme', 'From theme'], ['#e5a94b', 'Amber'], ['#4cc38a', 'Green'], ['#e5534b', 'Red'], ['#a78bfa', 'Violet'], ['#6b9eff', 'Blue'], ['#8d8a9a', 'Grey']]

function Toggle({ on, onChange, testid, label }) {
  return h('div', {
    role: 'switch', 'aria-checked': on ? 'true' : 'false', 'data-testid': testid, 'aria-label': label, tabIndex: 0,
    onKeyDown: activate(() => onChange(!on)),
    className: cx('inline-flex items-center w-8 h-4 rounded-full p-0.5 cursor-pointer', on ? 'bg-needs justify-end' : 'bg-line justify-start'),
    onClick: () => onChange(!on)
  }, h('div', { className: cx('w-3 h-3 rounded-full', on ? 'bg-card' : 'bg-muted') }))
}

function SettingsExclusions({ project }) {
  const q = useApi(project ? `/projects/${encodeURIComponent(project)}/exclusions` : null)
  const d = q.data
  if (!d) return null
  const rows = Object.entries(d.profiles || {})
  return h('section', { className: 'flex flex-col gap-3', 'data-testid': 'settings-exclusions' },
    h('div', 'text-[11px] font-semibold tracking-wider text-muted uppercase', `Excluded in ${d.project}`),
    h('div', 'bg-card border border-line rounded-[6px] divide-y divide-line',
      ...rows.map(([name, list]) => h('div', { key: name, className: 'flex items-start justify-between gap-4 px-4 py-2.5 text-xs', 'data-profile': name },
        h('span', 'mono text-fg font-medium shrink-0', name),
        list.length
          ? h('div', 'flex flex-col gap-1 items-end min-w-0',
            ...list.map(x => h('div', { key: x.spec, className: 'flex items-center gap-2 min-w-0', 'data-excluded-spec': x.spec },
              h('span', 'mono text-fg shrink-0', x.spec),
              h('span', { className: 'text-muted truncate', title: x.reason, 'data-reason': x.reason }, x.reason))))
          : h('span', 'text-dim', 'none')))))
}

function Settings({ project }) {
  const [bad, setBad] = useState(null)  // the row (a profile name, or null for a setting) and field a save refused
  const inv = (row, field) => !!bad && bad.field === field && bad.row === row
  const mark = (cls, row, field) => ({ className: cx(cls, inv(row, field) && 'border-fail'), 'aria-invalid': inv(row, field) || undefined })
  const q = useApi('/settings')
  const onb = (useApi('/state').data || {}).onboarding
  const [draft, setDraft] = useState(null)
  const [touched, setTouched] = useState(false)
  useDirty(touched)
  useExit(() => navigate('home', null, { force: true, replace: true }), true)
  const [adding, setAdding] = useState(null)
  const [label, setLabel] = useState('')
  const [err, setErr] = useState('')
  useEffect(() => {
    if (q.data && !draft) setDraft(JSON.parse(JSON.stringify(q.data)))
  }, [q.data])
  if (q.error && !draft) return h(Missing, { project, text: errText(q.error) })
  if (!draft) return h(Frame, { main: h(Loading) })
  const setProf = (i, patch) => { setTouched(true); setDraft({ ...draft, profiles: draft.profiles.map((p, j) => (j === i ? { ...p, ...patch } : p)) }) }
  const setSet = (k, v) => { setTouched(true); setDraft({ ...draft, settings: { ...draft.settings, [k]: v } }) }
  const colours = draft.settings.colours || {}
  const save = async () => {
    const s = draft.settings
    // What the field shows, as a number when it is one; anything else goes as typed and the route
    // refuses it on that field, so nothing is saved that the form did not show.
    const num = (v, unit) => {
      const t = String(v == null ? '' : v).trim().replace(unit || /$^/, '').trim()
      return /^\d+$/.test(t) ? parseInt(t, 10) : t
    }
    const timeout = num(s.test_timeout, /\s*s$/i)
    const kb = num(s.output_limit_label != null ? s.output_limit_label : Math.round(s.output_limit / 1000), /\s*kb$/i)
    const res = await post('/settings', {
      settings: { test_timeout: timeout, output_limit: s.output_limit_label == null ? s.output_limit : typeof kb === 'number' ? kb * 1000 : kb, colours: s.colours },
      profiles: draft.profiles.map(p => ({ ...p, cost: num(p.cost), max_runs: num(p.max_runs), at_once: num(p.at_once) }))
    })
    if (!res.ok) {
      const m = /^([^:]+): /.exec(res.error || '')
      setBad({ row: m && draft.profiles.some(p => p.name === m[1]) ? m[1] : null, field: res.field || null })
      return setErr(res.error)
    }
    setBad(null)
    $colours.set(res.data.settings.colours)
    setDraft(JSON.parse(JSON.stringify(res.data)))
    setErr('')
    setTouched(false)
    navigate('home', null, { force: true, replace: true })
    notify('Settings saved')
  }
  const cancel = () => { setDraft(JSON.parse(JSON.stringify(q.data))); setTouched(false); setErr(''); navigate('home', null, { force: true, replace: true }) }
  const numInp = 'w-16 bg-well border border-line rounded px-2 py-1 text-xs text-fg mono outline-none'
  const main = frag(
    h('div', 'flex items-center gap-2 text-xs',
      h('span', 'text-muted uppercase font-semibold tracking-wider text-[11px]', 'Project'),
      h('span', 'text-muted', '/'),
      project ? h('button', { type: 'button', className: 'text-fg font-medium mono', 'data-testid': 'project-name', title: 'Needs you', 'aria-label': `${project}, Needs you`, onClick: () => navigate('projects') }, project) : h('span', 'text-muted', 'none')),
    h('header', 'flex items-center justify-between pb-1', h('h1', { className: 'text-xl font-bold tracking-tight text-fg', 'data-page-title': '1', tabIndex: -1 }, 'Settings')),
    h('section', 'flex flex-col gap-3',
      h('div', 'text-[11px] font-semibold tracking-wider text-muted uppercase', 'Profiles'),
      h('div', 'bg-card border border-line rounded-[6px] overflow-hidden',
        h('table', 'w-full text-left border-collapse',
          h('thead', 'border-b border-line text-[11px] uppercase tracking-wider text-muted font-semibold bg-well/50',
            h('tr', null,
              h('th', 'px-3 py-2.5 font-semibold whitespace-nowrap', 'Profile'),
              h('th', 'px-3 py-2.5 font-semibold whitespace-nowrap', 'Tags'),
              h('th', 'px-3 py-2.5 font-semibold whitespace-nowrap w-24', 'Cost'),
              h('th', 'px-3 py-2.5 font-semibold whitespace-nowrap min-w-40', 'Tools'),
              h('th', 'px-3 py-2.5 font-semibold whitespace-nowrap w-24', 'Max runs'),
              h('th', 'px-3 py-2.5 font-semibold whitespace-nowrap w-24', 'At once'),
              h('th', 'px-3 py-2.5 font-semibold whitespace-nowrap w-24 text-right', 'Enabled'))),
          h('tbody', 'text-xs divide-y divide-line',
            ...draft.profiles.map((p, i) => h('tr', { key: p.name, 'data-profile': p.name },
              h('td', 'px-3 py-2.5 font-medium text-fg mono whitespace-nowrap', p.name),
              h('td', 'px-3 py-2.5',
                h('div', 'flex items-center gap-1.5 flex-wrap',
                  ...p.labels.map(l => h('span', { key: l, className: 'inline-flex items-center gap-1 px-2 py-0.5 rounded bg-btn border border-line text-fg text-[11px]', 'data-label': l },
                    l, h('span', { className: 'text-muted cursor-pointer', 'aria-label': `Remove ${l}`, 'data-remove': l, onClick: () => setProf(i, { labels: p.labels.filter(x => x !== l) }) }, '×'))),
                  adding === p.name
                    ? h('input', {
                      autoFocus: true, className: 'w-20 bg-well border border-line rounded px-1.5 py-0.5 text-[11px] text-fg outline-none', value: label, 'data-testid': 'label-input',
                      onChange: e => setLabel(e.target.value),
                      onBlur: () => { setAdding(null); setLabel('') },
                      onKeyDown: e => {
                        if (e.key === 'Enter') {
                          const v = label.trim()
                          if (v && !p.labels.includes(v)) setProf(i, { labels: [...p.labels, v] })
                          setAdding(null); setLabel('')
                        }
                        if (e.key === 'Escape') { e.preventDefault(); setAdding(null); setLabel('') }
                      }
                    })
                    : h('button', { type: 'button', className: 'px-1.5 py-0.5 rounded bg-btn border border-line text-muted text-[11px]', 'aria-label': `Add a label to ${p.name}`, 'data-add-label': p.name, onClick: () => setAdding(p.name) }, '+'))),
              h('td', 'px-3 py-2.5', h('input', { ...mark(numInp, p.name, 'cost'), type: 'number', name: 'cost', 'aria-label': `${p.name} cost`, value: p.cost, onChange: e => setProf(i, { cost: e.target.value }) })),
              h('td', 'px-3 py-2.5', h(ChipList, {
                items: p.tools || [], testid: 'tools', attr: 'data-tool', addLabel: `Add a tool to ${p.name}`,
                onRemove: t => setProf(i, { tools: (p.tools || []).filter(x => x !== t) }),
                onAdd: t => setProf(i, { tools: [...(p.tools || []), t] })
              })),
              h('td', 'px-3 py-2.5', h('input', { ...mark(numInp, p.name, 'max_runs'), type: 'number', name: 'max_runs', 'aria-label': `${p.name} max runs`, value: p.max_runs, onChange: e => setProf(i, { max_runs: e.target.value }) })),
              h('td', 'px-3 py-2.5', h('input', { ...mark(numInp, p.name, 'at_once'), type: 'number', min: 1, max: 10, name: 'at_once', 'aria-label': `${p.name} at once`, value: p.at_once, onChange: e => setProf(i, { at_once: e.target.value }) })),
              h('td', 'px-3 py-2.5 text-right', h(Toggle, { on: p.enabled, testid: 'enabled', label: `${p.name} enabled`, onChange: v => setProf(i, { enabled: v }) })))))))),
    project ? h(SettingsExclusions, { project }) : null,
    h('section', 'flex flex-col gap-3',
      h('div', 'text-[11px] font-semibold tracking-wider text-muted uppercase', 'Status colours'),
      h('div', 'bg-card border border-line rounded-[6px] divide-y divide-line',
        ...COLOUR_ROWS.map(([k, word, t]) => h('div', { key: k, className: 'flex items-center justify-between px-4 py-2.5' },
          h('div', 'flex items-center gap-2.5',
            h('span', { className: cx('w-2.5 h-2.5 rounded-full', TONE_BG[t]) }),
            h('span', 'text-xs text-fg font-medium', word)),
          h('select', {
            className: 'bg-well border border-line text-xs text-fg rounded px-2.5 py-1 outline-none cursor-pointer',
            value: colours[k] || 'theme', 'data-colour': k, 'aria-label': `${word} colour`,
            onChange: e => setSet('colours', { ...colours, [k]: e.target.value })
          }, ...FIXED.map(([v, l]) => h('option', { key: v, value: v }, l))))))),
    h('section', 'flex flex-col gap-3',
      h('div', 'text-[11px] font-semibold tracking-wider text-muted uppercase', 'Tests'),
      h('div', 'bg-card border border-line rounded-[6px] divide-y divide-line',
        h('div', 'flex items-center justify-between px-4 py-3',
          h('span', 'text-xs text-fg font-medium', 'Default timeout'),
          h('input', { ...mark('w-32 bg-well border border-line rounded px-2.5 py-1 text-xs text-fg mono outline-none text-right', null, 'test_timeout'), type: 'text', name: 'test_timeout', value: typeof draft.settings.test_timeout === 'number' ? `${draft.settings.test_timeout}s` : draft.settings.test_timeout, onChange: e => setSet('test_timeout', e.target.value) })),
        h('div', 'flex items-center justify-between px-4 py-3',
          h('span', 'text-xs text-fg font-medium', 'Output limit'),
          h('input', { ...mark('w-32 bg-well border border-line rounded px-2.5 py-1 text-xs text-fg mono outline-none text-right', null, 'output_limit'), type: 'text', name: 'output_limit', value: draft.settings.output_limit_label != null ? draft.settings.output_limit_label : `${Math.round(draft.settings.output_limit / 1000)} KB`, onChange: e => setSet('output_limit_label', e.target.value) })))),
    h('section', { className: 'flex flex-col gap-3', 'data-testid': 'settings-project' },
      h('div', 'text-[11px] font-semibold tracking-wider text-muted uppercase', 'Project'),
      h('div', 'bg-card border border-line rounded-[6px] divide-y divide-line',
        h('div', 'flex items-center justify-between px-4 py-3',
          h('span', 'text-xs text-fg font-medium', 'First green'),
          h(Toggle, { on: !(onb && onb.checklist_hidden), testid: 'show-first-green', label: 'Show First green', onChange: v => post('/onboarding', { checklist_hidden: !v }) })),
        project ? h('div', 'flex items-center justify-between px-4 py-3',
          h('span', 'text-xs text-fg font-medium mono', project),
          h(Btn, { kind: 'small', testid: 'open-project-settings', onClick: () => navigate('project-settings') }, 'Project settings')) : null)),
    h(ErrorLine, { text: err }),
    h('div', 'sticky bottom-0 bg-page flex items-center justify-end gap-3 pt-2 pb-6',
      h('button', { type: 'button', className: 'px-4 py-1.5 rounded-[6px] border border-line text-xs font-semibold text-muted', onClick: cancel }, 'Cancel'),
      h('button', { type: 'button', className: 'px-4 py-1.5 rounded-[6px] bg-needs text-on-needs font-semibold text-xs', onClick: save }, 'Save')))
  return h(Frame, { main, wide: true })
}
