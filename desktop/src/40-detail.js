// Rung desktop pane: rung detail views (need, requirement, specification, test), editors, change view.

function backTo(ret, need, fallback) {
  if (ret && need) return () => navigate('build', { need, step: ret })
  return fallback || (() => navigate('home'))
}

function pathCrumbs(r, lastTone) {
  return h(Crumbs, { path: r.path, last: r.id, lastTone: lastTone || 'text-needs' })
}

function Label({ children, upper }) {
  return h('span', upper === false ? 'text-[11px] font-semibold text-muted' : 'text-[11px] font-semibold uppercase tracking-wider text-muted', children)
}

function Section({ title, children, testid, right }) {
  return h('div', { className: 'flex flex-col gap-2 pt-3 border-t border-line', 'data-testid': testid },
    right ? h('div', 'flex items-center justify-between pb-1', h(Label, null, title), right) : h(Label, null, title),
    children)
}

function Well({ children, className, testid }) {
  return h('div', { className: cx('bg-well p-2.5 rounded-[6px] border border-line2', className), 'data-testid': testid }, children)
}

function editedAgo(change) {
  return change ? `edited ${ago(change.at)}` : ''
}

function RungView(props) {
  const { project, rid } = props
  const q = useRung(project, rid)
  const r = q.data
  const needId = r && (r.kind === 'need' ? r.id : r.path && r.path[0] && r.path[0].id)
  useEffect(() => { noteNeed(project, needId) }, [project, needId])
  if (q.error) return h(Missing, { project, text: errText(q.error) })
  if (!r) return h(Page, { project, sel: rid }, h(Loading))
  const p = { ...props, r }
  if (r.kind === 'need') return h(NeedView, p)
  if (r.kind === 'requirement') return h(ReqEditor, p)
  if (r.kind === 'specification') return h(SpecView, p)
  return h(TestView, p)
}

// ------------------------------------------------------------------ need

function NeedView({ project, r, flow }) {
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState(r.text)
  const [err, setErr] = useState('')
  const [conflict, setConflict] = useState(null)
  const [retiring, setRetiring] = useState(false)
  const [base, setBase] = useState(null)
  const ro = !!r.read_only
  useDirty(editing && text !== r.text)
  // Escape closes the inline edit (asking first when text is typed), else leaves the need like Back.
  useExit(() => { if (editing) { setEditing(false); setText(r.text) } else goBack('home') })
  const reqs = (r.children || []).filter(x => x.status !== 'dismissed' && x.status !== 'proposed')
  const reqTone = x => x.status === 'stale' ? 'text-stale' : x.status === 'draft' ? 'text-dim' : x.coverage === 'failing' ? 'text-fail' : x.coverage === 'covered' ? 'text-pass' : 'text-fg'
  const reqBadge = x => x.status === 'stale' ? 'stale' : x.status === 'draft' ? 'draft' : x.coverage === 'covered' ? 'covered' : x.coverage === 'failing' ? 'failing' : x.status === 'proposed' ? 'proposed' : 'open'
  const save = async approve => {
    const res = await post(`${P(project)}/rungs/${r.id}/edit`, { text, approve, version: base == null ? r.version : base })
    if (!res.ok) { setConflict(res.code === 'conflict' ? res : null); return setErr(res.code === 'conflict' ? '' : res.error) }
    setEditing(false); setErr(''); setConflict(null); setBase(null)
  }
  const head = h('div', 'flex flex-col gap-1.5',
    h('div', 'flex items-center justify-between',
      h('div', 'text-[11px] mono text-needs font-medium', h('span', null, r.id)),
      h(Badge, { status: r.status })),
    editing
      ? h('div', 'flex flex-col gap-2',
        h('input', { className: 'w-full bg-well border border-line2 rounded-[6px] px-3 py-2 text-sm font-semibold text-fg focus:outline-none focus:border-needs', value: text, name: 'need-text', autoFocus: true, onChange: e => setText(e.target.value), onKeyDown: e => { if (e.key === 'Escape') { e.preventDefault(); const close = () => { setEditing(false); setText(r.text) }; if (text !== r.text) $leave.set({ go: close }); else close() } } }),
        h('div', 'flex items-center gap-2',
          h(Btn, { kind: 'primary', testid: 'save-need', onClick: () => save(true) }, 'Save and approve'),
          h(Btn, { onClick: () => { setEditing(false); setText(r.text) } }, 'Cancel')))
      : ro ? h('h2', { className: 'text-base font-semibold text-fg', 'data-testid': 'need-title' }, r.text)
        : h('h2', { className: 'text-base font-semibold text-fg cursor-pointer', 'data-testid': 'need-title', title: 'Edit', 'aria-label': `Edit ${r.id}: ${r.text}`, onClick: () => { setBase(r.version); setText(r.text); setEditing(true) } }, r.text),
    h(Conflict, { res: conflict, path: `${P(project)}/rungs/${r.id}` }),
    !editing ? h('div', 'flex items-center gap-2 pt-1',
      r.status === 'draft' && !ro ? h(Btn, { kind: 'primary', testid: 'approve', onClick: async () => { const x = await post(`${P(project)}/rungs/${r.id}/approve`); setErr(x.ok ? '' : x.error) } }, 'Approve') : null,
      h(Btn, { kind: 'small', testid: 'open-readout', onClick: () => navigate('readout', { need: r.id }) }, 'Read-out'),
      ro ? null : h(Btn, { kind: 'quiet', testid: 'retire', onClick: () => setRetiring(true) }, 'Retire')) : null)
  const body = h(Card, { className: 'p-4 flex flex-col gap-4', testid: 'need' },
    r.retired ? h(RetiredBar, { project, r }) : null,
    head,
    r.change && r.change.rung === r.id ? h('div', 'flex items-center justify-between px-3 py-2 rounded-[6px] bg-well border border-line2 text-xs',
      h('div', 'flex items-center gap-2 text-muted', h(Dot, { t: 'stale' }), h('span', null, `${r.id} · ${editedAgo(r.change)}`)),
      h('button', { type: 'button', className: 'text-[11px] font-medium text-needs inline-flex items-center min-h-[24px] min-w-[24px] hover:underline', 'data-testid': 'view-change', onClick: () => navigate('change', { change: r.change.id, rid: r.id }) }, 'View change')) : null,
    h('div', 'flex flex-col gap-2 pt-3 border-t border-line',
      h('div', 'flex items-center justify-between pb-1',
        h('span', 'text-xs font-semibold uppercase tracking-wider text-muted', 'Requirements'),
        ro ? null : h('button', { type: 'button', className: 'px-2.5 py-1 rounded text-xs font-medium text-needs border border-needs', 'data-testid': 'new-requirement', onClick: () => navigate('req-new', { need: r.id }) }, 'New requirement')),
      reqs.length ? null : h(Empty, { text: 'No requirements', action: ro ? null : 'New requirement', onClick: () => navigate('req-new', { need: r.id }) }),
      ...reqs.map(x => h('div', { key: x.id, className: 'flex items-center justify-between bg-well p-2.5 rounded-[6px] border border-line2 cursor-pointer', 'data-req': x.id, onClick: () => navigate('rung', { rid: x.id }) },
        h('div', 'flex items-center gap-2.5',
          h('span', { className: cx('text-xs font-medium mono', reqTone(x)) }, x.id),
          h('span', { className: cx('text-xs', x.status === 'draft' ? 'text-muted' : 'text-fg') }, x.text)),
        h(Badge, { status: reqBadge(x), small: true })))),
    h(SuggestPanel, { project, need: r.id, ro: ro || !!r.retired }),
    (r.suggestions || []).length ? h('div', { className: 'flex flex-col gap-2 pt-3 border-t border-line', 'data-testid': 'suggested' },
      h('span', 'text-xs font-semibold uppercase tracking-wider text-muted', 'Suggested'),
      ...r.suggestions.map(s => h('div', { key: s.id, className: 'flex items-center justify-between bg-well p-2.5 rounded-[6px] border border-line2', 'data-suggestion': s.text },
        h('div', 'flex items-center gap-2', h('span', 'w-1.5 h-1.5 rounded-full bg-stale'), h('span', 'text-xs text-fg', s.text)),
        h('div', 'flex items-center gap-2',
          h('button', { type: 'button', className: 'px-2 py-1 rounded text-xs font-medium bg-needs text-on-needs', onClick: async () => { const x = await post(`${P(project)}/suggestions/${s.id}`, { accept: true }); setErr(x.ok ? '' : x.error) } }, 'Accept'),
          h('button', { type: 'button', className: 'px-2 py-1 rounded text-xs font-medium bg-btn border border-line text-muted', onClick: async () => { const x = await post(`${P(project)}/suggestions/${s.id}`, { accept: false }); setErr(x.ok ? '' : x.error) } }, 'Dismiss'))))) : null,
    h(ErrorLine, { text: err }))
  return h(Page, { project, sel: r.id, back: () => goBack('home'), backExit: false }, flow ? h(BuildStrip, { need: r.id, flow, current: 0 }) : null, body, retiring ? h(RetireDialog, { project, need: r.id, onClose: () => setRetiring(false) }) : null)
}

// ------------------------------------------------------------------ requirement editor (also New requirement)

function ReqEditor({ project, r, need, ret }) {
  const isNew = !r
  const pre = usePrefill(isNew ? 'req-new' : '')
  const [text, setText] = useState(r ? r.text : (pre.text || ''))
  const [detail, setDetail] = useState(r ? r.detail : (pre.detail || ''))
  const [err, setErr] = useState('')
  const [sugs, setSugs] = useState(null)
  const [marks, setMarks] = useState({})
  const [conflict, setConflict] = useState(null)
  const shown = useRef(r ? { text: r.text, detail: r.detail } : null)
  const clean = !!shown.current && text === shown.current.text && detail === shown.current.detail
  const base = useBase(r && r.version, clean)
  const needId = r ? r.parent : need
  // Follow a newer version (a revert, another edit) while nothing is typed; typed text stays and meets the conflict check.
  useEffect(() => {
    if (!r || !shown.current) return
    if (text === shown.current.text && detail === shown.current.detail) { setText(r.text); setDetail(r.detail) }
    shown.current = { text: r.text, detail: r.detail }
  }, [r && r.version, r && r.text])
  useEffect(() => {
    if (isNew) return
    let live = true
    rest(`${P(project)}/rungs/${r.id}/suggest-edits`, { method: 'POST', body: {} }).then(x => { if (live) setSugs(x.suggestions || []) }).catch(() => { if (live) setSugs([]) })
    return () => { live = false }
  }, [r && r.id])
  const dest = ret ? ['build', { need: needId, step: ret }] : ['rung', { rid: needId }]
  const done = () => goBack(dest[0], dest[1], { force: true })
  const saved = (id, approved) => finish(dest[0], dest[1], `${isNew ? 'Added' : approved ? 'Approved' : 'Saved'} ${id}`)
  useDirty(isNew ? (text.trim() || detail.trim()) : !clean)
  useExit(done, true)
  const save = async approve => {
    let res
    if (isNew) {
      res = await post(`${P(project)}/needs/${needId}/requirements`, { text, detail })
      if (res.ok && approve) res = await post(`${P(project)}/rungs/${res.data.id}/approve`)
    } else {
      res = await post(`${P(project)}/rungs/${r.id}/edit`, { text, detail, approve, version: base })
    }
    if (!res.ok) { setConflict(res.code === 'conflict' ? res : null); return setErr(res.code === 'conflict' ? '' : res.error) }
    saved((res.data && res.data.id) || (r && r.id) || 'requirement', approve)
  }
  const specs = r ? (r.children || []).filter(s => s.status !== 'dismissed' && s.status !== 'proposed') : []
  const crumbPath = r ? r.path : [{ id: needId }]
  const body = h(Card, { className: 'p-5 flex flex-col gap-5', testid: 'req-editor' },
    h('div', 'flex flex-col gap-2',
      h('div', 'flex items-center justify-between',
        h(Crumbs, { path: crumbPath, last: r ? r.id : 'New requirement', lastTone: 'text-fg' }),
        h(Badge, { status: r ? r.status : 'draft' })),
      h('div', 'flex flex-col gap-1.5',
        h('label', 'text-[11px] font-semibold uppercase tracking-wider text-muted', 'Requirement'),
        h('input', { className: 'w-full bg-well border border-line2 rounded-[6px] px-3 py-2 text-sm font-semibold text-fg focus:outline-none focus:border-needs', type: 'text', name: 'req-text', value: text, autoFocus: isNew, onChange: e => setText(e.target.value) }))),
    r && r.change && r.change.rung === r.id ? h('div', 'flex items-center justify-between px-3 py-2 rounded-[6px] bg-well border border-line2 text-xs',
      h('div', 'flex items-center gap-2 text-muted', h(Dot, { t: 'stale' }), h('span', null, `${r.id} · ${editedAgo(r.change)}`)),
      h('button', { type: 'button', className: 'text-[11px] font-medium text-needs inline-flex items-center min-h-[24px] min-w-[24px] hover:underline', 'data-testid': 'view-change', onClick: () => navigate('change', { change: r.change.id, rid: r.id }) }, 'View change')) : null,
    h('div', 'flex flex-col gap-2',
      h('label', 'text-[11px] font-semibold uppercase tracking-wider text-muted', 'Acceptance'),
      h('textarea', { className: 'w-full bg-well border border-line2 rounded-[6px] p-3 text-xs text-fg focus:outline-none focus:border-needs font-mono leading-relaxed', rows: 3, name: 'req-detail', value: detail, onChange: e => setDetail(e.target.value) })),
    sugs && sugs.length ? h('div', { className: 'flex flex-col gap-2.5 pt-2 border-t border-line', 'data-testid': 'suggested-edits' },
      h('div', 'text-[11px] font-semibold uppercase tracking-wider text-muted', 'Suggested edits'),
      h('div', 'flex flex-col gap-2', ...sugs.map(s => h('div', { key: s.id, className: cx('flex items-center justify-between bg-well p-2.5 rounded-[6px] border border-line2', marks[s.id] === 'dismissed' && 'opacity-40 line-through'), 'data-suggestion': s.text },
        h('span', 'text-xs text-fg', s.text),
        h('div', 'flex items-center gap-2',
          h('button', { type: 'button', className: 'px-2.5 py-1 rounded bg-btn border border-line text-fg text-[11px] font-medium', disabled: !!marks[s.id], onClick: async () => { const x = await post(`${P(project)}/suggestions/${s.id}`, { accept: true }); if (!x.ok) return setErr(x.error); setMarks({ ...marks, [s.id]: 'accepted' }); setDetail(d => (d ? d + '\n' : '') + s.text) } }, marks[s.id] === 'accepted' ? 'Accepted' : 'Accept'),
          h('button', { type: 'button', className: 'px-2.5 py-1 rounded bg-btn border border-line text-muted text-[11px] font-medium', disabled: !!marks[s.id], onClick: async () => { const x = await post(`${P(project)}/suggestions/${s.id}`, { accept: false }); if (!x.ok) return setErr(x.error); setMarks({ ...marks, [s.id]: 'dismissed' }) } }, 'Dismiss')))))) : null,
    isNew ? h(DraftBar, { project, kind: 'requirement', parent: needId, fields: { text, detail }, apply: v => { if (v.text != null) setText(v.text); if (v.detail != null) setDetail(v.detail) } }) : null,
    specs.length ? h('div', 'flex flex-col gap-2 pt-2 border-t border-line',
      h('div', 'text-[11px] font-semibold uppercase tracking-wider text-muted', 'Specifications'),
      ...specs.map(s => h('div', { key: s.id, className: 'flex items-center justify-between bg-well p-2.5 rounded-[6px] border border-line2 cursor-pointer', onClick: () => navigate('rung', { rid: s.id }) },
        h('div', 'flex items-center gap-2',
          h('span', 'text-xs font-semibold mono text-fg', `${s.id}:`),
          h('span', 'text-xs text-muted', s.text)),
        h(Badge, { status: (s.children || []).length ? s.status : 'draft', label: (s.children || []).length ? undefined : 'No tests', small: true })))) : null,
    h(ErrorLine, { text: err }),
    h(Conflict, { res: conflict, path: r ? `${P(project)}/rungs/${r.id}` : null }),
    h('div', 'flex items-center gap-2.5 pt-3 border-t border-line',
      h('button', { type: 'button', className: 'px-3.5 py-1.5 rounded-[6px] bg-needs text-on-needs font-semibold text-xs', 'data-testid': 'approve', onClick: () => save(true) }, 'Approve'),
      h('button', { type: 'button', className: 'px-3.5 py-1.5 rounded-[6px] bg-btn border border-line text-fg text-xs font-medium', 'data-testid': 'save-draft', onClick: () => save(false) }, 'Save draft'),
      h('button', { type: 'button', className: 'px-3 py-1.5 rounded-[6px] text-muted text-xs font-medium', 'data-testid': 'cancel-edit', onClick: done }, 'Cancel')))
  return h(Page, { project, sel: r ? r.id : needId }, body)
}

function ReqNew({ project, need, ret }) {
  return h(ReqEditor, { project, r: null, need, ret })
}

// ------------------------------------------------------------------ change view

function ChangeView({ project, change, rid }) {
  const q = useApi(`${P(project)}/changes`)
  const tq = useRung(project, rid)
  const target = tq.data
  const [err, setErr] = useState('')
  const ch = (q.data || []).find(c => String(c.id) === String(change))
  if (q.error || tq.error) return h(Missing, { project, text: errText(q.error || tq.error) })
  if (q.data && !ch) return h(Missing, { project, text: `no change ${change} in ${project}` })
  if (!ch || !target) return h(Page, { project, sel: rid }, h(Loading))
  const stale = ch.stale || []
  const firstStale = stale.find(x => !x.startsWith('T-')) || stale[0]
  const words = (a, b) => {
    // Highlight the words that are new in After.
    const old = new Set(String(a || '').split(/\s+/))
    return String(b || '').split(/(\s+)/).map((w, i) => /\s+/.test(w) || old.has(w) ? w : h('span', { key: i, className: 'text-pass font-semibold' }, w))
  }
  const kindWord = KIND_WORD[target.kind] || 'Rung'
  const body = h('div', 'flex flex-col gap-6',
    h(Card, { className: 'p-4 flex flex-col gap-4', testid: 'change' },
      h('div', 'flex items-center justify-between',
        h('div', 'flex flex-col gap-1',
          h(Crumbs, { path: target.path, last: target.id, lastTone: 'text-fg' }),
          h('div', 'flex items-center gap-2.5',
            h('h2', 'text-sm font-semibold text-fg', `Change to ${ch.rung}`),
            h('span', 'inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-btn text-muted border border-line2', editedAgo(ch)))),
        h('div', 'flex items-center gap-2',
          firstStale ? h('button', { type: 'button', className: 'px-3 py-1.5 rounded-[6px] bg-needs text-on-needs font-semibold text-xs', 'data-testid': 'review-first', onClick: () => navigate('rung', { rid: firstStale }) }, `Review ${firstStale}`) : null,
          h('button', { type: 'button', className: 'px-3 py-1.5 rounded-[6px] bg-btn border border-line text-fg text-xs font-medium', 'data-testid': 'revert', onClick: async () => { const x = await post(`${P(project)}/changes/${ch.id}/revert`); if (!x.ok) return setErr(x.error); finish('rung', { rid: ch.rung }, `Reverted ${ch.rung}`) } }, 'Revert change'))),
      h('div', 'grid grid-cols-2 gap-3 pt-3 border-t border-line',
        h('div', { className: 'bg-well border border-line2 rounded-[6px] p-3 flex flex-col gap-3', 'data-testid': 'before' },
          h('div', 'flex items-center justify-between pb-1.5 border-b border-line2', h('span', 'text-xs font-semibold text-fail uppercase tracking-wider', 'Before')),
          h('div', 'flex flex-col gap-2.5 text-xs',
            h('div', 'flex flex-col gap-1', h('span', 'text-[11px] font-medium text-muted', kindWord), h('div', 'text-fg', ch.before)),
            ch.before_detail || ch.after_detail ? h('div', 'flex flex-col gap-1', h('span', 'text-[11px] font-medium text-muted', 'Acceptance criteria'), h('div', 'text-muted', ch.before_detail)) : null)),
        h('div', { className: 'bg-well border border-line2 rounded-[6px] p-3 flex flex-col gap-3', 'data-testid': 'after' },
          h('div', 'flex items-center justify-between pb-1.5 border-b border-line2', h('span', 'text-xs font-semibold text-pass uppercase tracking-wider', 'After')),
          h('div', 'flex flex-col gap-2.5 text-xs',
            h('div', 'flex flex-col gap-1', h('span', 'text-[11px] font-medium text-muted', kindWord), h('div', 'text-fg', ...words(ch.before, ch.after))),
            ch.before_detail || ch.after_detail ? h('div', 'flex flex-col gap-1', h('span', 'text-[11px] font-medium text-muted', 'Acceptance criteria'), h('div', 'text-fg', ...words(ch.before_detail, ch.after_detail))) : null)))),
    h(ErrorLine, { text: err }),
    stale.length ? h('section', { className: 'flex flex-col gap-2.5', 'data-testid': 'now-stale' },
      h('div', 'flex items-center justify-between',
        h('h2', 'text-xs font-semibold uppercase tracking-wider text-stale flex items-center gap-1.5', h('span', 'w-1.5 h-1.5 rounded-full bg-stale'), 'Now stale')),
      h('div', 'flex flex-col gap-2', ...stale.map(id => h(StaleRow, { key: id, project, rid: id })))) : null)
  return h(Page, { project, sel: rid, back: () => goBack('rung', { rid }) }, body)
}

function StaleRow({ project, rid }) {
  const r = useRung(project, rid).data
  if (!r) return h(Card, { className: 'p-3 text-xs text-muted' }, rid)
  const isTest = r.kind === 'test'
  const last = isTest ? (r.executions || []).find(x => x.invalidated) : null
  const still = r.status === 'stale'
  return h('div', { className: 'bg-card border border-line rounded-[6px] p-3 flex items-center justify-between cursor-pointer', 'data-stale': rid, onClick: () => navigate('rung', { rid }) },
    h('div', 'flex items-center gap-2.5',
      h(Dot, { t: still ? 'stale' : 'pass' }),
      h('span', { className: cx('text-xs text-fg', isTest ? 'font-mono' : 'font-medium') }, `${r.id} ${isTest ? (r.command || r.text) : r.text}`),
      last ? h('span', 'line-through text-dim text-xs font-mono', `#${last.n} ${last.status}${last.commit ? ' · ' + last.commit : ''}`) : null),
    h(Badge, { status: still ? 'stale' : 'approved' }))
}

// ------------------------------------------------------------------ specification

function ScoreCard({ s, first }) {
  if (first) {
    return h('div', { className: 'flex flex-col gap-1.5 bg-btn p-3 rounded-[6px] border border-line', 'data-score': s.profile },
      h('div', 'flex items-center justify-between text-xs',
        h('span', 'font-semibold text-fg', s.profile),
        h('span', 'font-bold text-needs mono', String(s.score))),
      h('div', 'text-[11px] mono text-muted leading-tight', `tags ${s.parts.tags} · load ${s.parts.load} · reliability ${s.parts.reliability} · cost ${s.parts.cost}`),
      h('div', 'w-full h-1 bg-well rounded-full overflow-hidden mt-1', h('div', { className: 'h-full bg-needs rounded-full', style: { width: `${s.score}%` } })))
  }
  return h('div', { className: 'flex flex-col gap-1.5 bg-well p-2.5 rounded-[6px] border border-line2', 'data-score': s.profile },
    h('div', 'flex items-center justify-between text-xs',
      h('span', 'text-muted', s.profile),
      h('span', 'text-muted mono', String(s.score))),
    h('div', 'w-full h-1 bg-card rounded-full overflow-hidden', h('div', { className: 'h-full bg-dim rounded-full', style: { width: `${s.score}%` } })))
}

function TestLine({ t }) {
  const res = t.result || 'not_run'
  const tn = res === 'pass' ? 'pass' : res === 'fail' ? 'fail' : res === 'stale' ? 'stale' : res === 'pending' ? 'needs' : 'dim'
  return h('div', { className: 'flex items-center justify-between p-2.5 rounded-[6px] bg-well border border-line2 cursor-pointer', 'data-test': t.id, onClick: () => navigate('rung', { rid: t.id }) },
    h('div', 'flex items-center gap-2.5',
      h(Dot, { t: tn }),
      h('span', { className: cx('text-xs', t.type === 'manual' ? 'text-muted' : 'mono text-fg') }, t.type === 'manual' ? t.text : (t.command || t.text))),
    h(Badge, { status: res === 'not_run' ? 'not_run' : res }))
}

function SpecView({ project, r, ret, need }) {
  const [err, setErr] = useState('')
  const [picking, setPicking] = useState(false)
  const tests = (r.children || []).filter(t => t.status !== 'dismissed' && t.status !== 'proposed')
  const proposedTests = (r.children || []).filter(t => t.status === 'draft')
  const a = r.allocation || { suggestions: [] }
  const shown = a.pick ? [a.suggestions.find(x => x.profile === a.pick.profile), ...a.suggestions.filter(x => x.profile !== a.pick.profile)].filter(Boolean) : a.suggestions
  const needId = r.path[0] && r.path[0].id
  const act = async (path, body, go) => {
    const x = await post(path, body)
    if (!x.ok) return setErr(x.error)
    setErr('')
    if (go) go(x.data)
  }
  const runTests = () => act(`${P(project)}/specs/${r.id}/run-tests`, {}, d => { const s = d.started && d.started[0]; if (s) navigate('exec', { test: s.test, n: s.n }) })
  const develop = () => act(`${P(project)}/specs/${r.id}/send`, {}, d => navigate('run', { run: d.id }))
  const headline = h('div', 'flex items-center justify-between',
    pathCrumbs(r, r.status === 'approved' && r.released ? 'text-fg' : 'text-needs'),
    r.draft_state === 'failed' ? h(Badge, { status: 'draft_failed' }) : r.draft_state === 'drafting' ? h(Badge, { status: 'drafting' })
      : r.released ? h(Badge, { status: 'released' }) : tests.length || r.status === 'stale' ? h(Badge, { status: r.status }) : h('span', 'inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-btn text-muted border border-line', 'No tests'))
  // Unapproved AI draft (spec-s31)
  if (r.status === 'draft') {
    const lines = String(r.detail || '').split('\n').map(x => x.replace(/^[-*]\s*/, '').trim()).filter(Boolean)
    const body = h(Card, { className: 'p-4 flex flex-col gap-4', testid: 'spec' },
      h('div', 'flex flex-col gap-2', headline, h('h2', 'text-base font-semibold text-fg', r.draft_state === 'drafting' ? 'Drafting' : r.text),
        r.draft_state === 'failed' ? h('p', { className: 'text-xs text-needs', 'data-testid': 'draft-error' }, r.draft_error || 'Draft failed') : null),
      h('div', 'flex flex-col gap-1.5 pt-2 border-t border-line',
        h('span', 'text-[11px] font-semibold uppercase tracking-wider text-muted', 'Authoring'),
        h(Seg, { big: true, options: [['ai', 'AI derives'], ['human', 'I write, AI supports']], value: r.authoring || (r.author_role === 'human' ? 'human' : 'ai'), testid: 'authoring', onChange: v => (v === 'human' ? navigate('spec-edit', { spec: r.id, ret, need }) : act(`${P(project)}/rungs/${r.parent}/authoring`, { mode: 'ai' })) })),
      lines.length ? h('div', 'flex flex-col gap-2 pt-2 border-t border-line',
        h('span', 'text-[11px] font-semibold text-muted', `Draft by ${r.drafted_by || 'drafting'}`),
        h('div', 'bg-well p-3 rounded-[6px] border border-line2 flex flex-col gap-1.5 text-xs text-fg',
          ...lines.map((l, i) => h('div', { key: i, className: 'flex items-center gap-2' }, h('span', 'w-1.5 h-1.5 rounded-full bg-dim'), h('span', null, l))))) : null,
      proposedTests.length ? h('div', 'flex flex-col gap-2 pt-2 border-t border-line',
        h('span', 'text-[11px] font-semibold uppercase tracking-wider text-muted', 'Proposed tests'),
        ...proposedTests.map(t => h('div', { key: t.id, className: 'bg-well p-2.5 rounded-[6px] border border-line2 flex items-center justify-between', 'data-test': t.id },
          h('div', 'flex items-center gap-2 mono text-xs text-fg', h('span', 'w-1.5 h-1.5 rounded-full bg-dim'), h('span', 'font-medium', t.id), h('span', 'text-muted', t.command || t.text)),
          h('div', 'flex items-center gap-2',
            h(Btn, { kind: 'small', onClick: () => act(`${P(project)}/rungs/${t.id}/approve`) }, 'Accept'),
            h(Btn, { kind: 'small', onClick: () => navigate('test-edit', { test: t.id }) }, 'Edit'))))) : null,
      h(ErrorLine, { text: err }),
      h('div', 'flex items-center gap-2 pt-3 border-t border-line',
        h(Btn, { kind: 'primary', testid: 'approve', disabled: r.draft_state === 'drafting', onClick: () => act(`${P(project)}/rungs/${r.id}/approve`, {}, () => backTo(ret, need, () => navigate('rung', { rid: r.id }))()) }, 'Approve'),
        r.ai_derived ? h(Btn, { testid: 'regenerate', disabled: r.draft_state === 'drafting', onClick: () => act(`${P(project)}/rungs/${r.id}/regenerate`) }, 'Regenerate') : null))
    return h(Page, { project, sel: r.id, back: () => goBack('rung', { rid: r.parent }) }, body)
  }
  // Released (spec-s11)
  if (r.released && r.status === 'approved') {
    const lastRun = (r.runs || [])[0]
    const execs = []
    for (const t of tests) for (const x of (t.executions || [])) execs.push({ ...x, test: t.id })
    const body = h('section', 'flex flex-col gap-4',
      h(Card, { className: 'p-4 flex flex-col gap-4', testid: 'spec' },
        h('div', 'flex flex-col gap-1.5', headline,
          h('div', 'text-sm font-semibold text-fg', r.text),
          h('div', 'text-[12px] text-muted flex items-center gap-3 mt-1',
            h('span', null, `Carried by ${r.carried_by || 'you'}`), h('span', null, '·'), h('span', null, `Approved ${dayClock(r.approved_at)}`))),
        h('div', 'flex flex-col gap-2 pt-3 border-t border-line',
          h('div', 'text-xs font-semibold uppercase tracking-wider text-muted', 'Tests'),
          tests.length ? null : h(Empty, { text: 'No tests', action: 'Add test', onClick: () => navigate('test-edit', { spec: r.id }) }),
          ...tests.map(t => h('div', { key: t.id, className: 'bg-well p-2.5 rounded-[6px] border border-line2 flex items-center justify-between text-[11px] cursor-pointer', 'data-test': t.id, onClick: () => navigate('rung', { rid: t.id }) },
            h('span', 'mono text-fg', `${t.id} · ${t.type === 'manual' ? t.text : (t.command || t.text)}`),
            h('span', { className: cx('font-medium', TONE_TEXT[t.result === 'pass' ? 'pass' : t.result === 'fail' ? 'fail' : 'dim']) }, capital(resultWord(t.result)))))),
        h('div', 'flex flex-col gap-2 pt-3 border-t border-line',
          h('div', 'text-xs font-semibold uppercase tracking-wider text-muted', 'Latest run'),
          h(SpecExecs, { tests, run: lastRun })),
        h(ErrorLine, { text: err }),
        h('div', 'flex items-center gap-2 pt-3 border-t border-line',
          h(Btn, { kind: 'primary', testid: 'run-tests', onClick: runTests }, 'Run tests'),
          h(Btn, { testid: 'reopen', onClick: () => navigate('spec-edit', { spec: r.id }) }, 'Reopen'),
          r.ai_derived ? h(Btn, { testid: 'fresh-draft', onClick: () => act(`${P(project)}/rungs/${r.id}/regenerate`) }, 'Fresh draft') : null)),
      h(ClaimsSection, { project, r, onErr: setErr }),
      h(CarrierSection, { project, r, onErr: setErr }))
    return h(Page, { project, sel: r.id, back: () => goBack('rung', { rid: r.parent }) }, body)
  }
  // Approved or stale, not released (spec-s21)
  const ch = r.change
  const body = h('div', 'flex flex-col gap-5',
    h('article', { className: 'bg-card border border-line rounded-[6px] p-5 flex flex-col gap-5', 'data-testid': 'spec' },
      h('div', 'flex flex-col gap-2.5', headline,
        h('h2', 'text-base font-semibold text-fg tracking-tight', r.text),
        ch && r.status === 'stale' ? h('div', 'flex items-center justify-between px-3 py-2 rounded-[6px] bg-well border border-line2 text-xs',
          h('div', 'flex items-center gap-2 text-muted', h('span', 'w-1.5 h-1.5 rounded-full bg-stale'), h('span', null, `${ch.rung} · ${ch.after} · ${editedAgo(ch)}`)),
          h('button', { type: 'button', className: 'text-[11px] font-medium text-needs inline-flex items-center min-h-[24px] min-w-[24px] hover:underline', 'data-testid': 'view-change', onClick: () => navigate('change', { change: ch.id, rid: ch.rung }) }, 'View change')) : null),
      h(ErrorLine, { text: err }),
      h('div', 'flex items-center gap-2 pt-1 border-t border-line',
        h('button', { type: 'button', className: cx('px-3.5 py-1.5 rounded-[6px] bg-needs text-on-needs font-semibold text-xs mt-3', r.status !== 'stale' && 'opacity-40 cursor-not-allowed'), 'data-testid': 'approve', 'data-locked': r.status !== 'stale' ? '1' : undefined, onClick: () => r.status === 'stale' && act(`${P(project)}/rungs/${r.id}/approve`) }, 'Approve'),
        h('button', { type: 'button', className: 'px-3.5 py-1.5 rounded-[6px] bg-btn border border-line text-fg text-xs font-medium mt-3', 'data-testid': 'run-tests', onClick: runTests }, 'Run tests'),
        a.human_only ? null : h('button', { type: 'button', className: cx('px-3.5 py-1.5 rounded-[6px] bg-btn border border-line text-fg text-xs font-medium mt-3', !r.develop.available && 'opacity-40 cursor-not-allowed'), 'data-testid': 'develop', 'data-locked': r.develop.available ? undefined : '1', title: r.develop.blocked_by || '', onClick: () => r.develop.available && develop() }, 'Develop until green'),
        h('button', { type: 'button', className: 'px-3.5 py-1.5 rounded-[6px] bg-btn border border-line text-fg text-xs font-medium mt-3', 'data-testid': 'edit-spec', onClick: () => navigate('spec-edit', { spec: r.id }) }, 'Edit specification'),
        (r.status === 'approved' || r.status === 'stale') && r.ai_derived ? h('button', { type: 'button', className: 'px-3.5 py-1.5 rounded-[6px] bg-btn border border-line text-fg text-xs font-medium mt-3', 'data-testid': 'fresh-draft', onClick: () => act(`${P(project)}/rungs/${r.id}/regenerate`) }, 'Fresh draft') : null)),
    h('section', { className: 'bg-card border border-line rounded-[6px] p-4 flex flex-col gap-3', 'data-testid': 'spec-tests' },
      h('div', 'flex items-center justify-between pb-1.5 border-b border-line', h('h3', 'text-xs font-semibold uppercase tracking-wider text-muted', 'Tests')),
      h('div', 'flex flex-col gap-2', tests.length ? null : h(Empty, { text: 'No tests', action: 'Add test', onClick: () => navigate('test-edit', { spec: r.id }) }), ...tests.map(t => h(TestLine, { key: t.id, t })))),
    h(ClaimsSection, { project, r, onErr: setErr }),
    a.human_only ? h('section', { className: 'bg-card border border-line rounded-[6px] p-4 flex flex-col gap-3', 'data-testid': 'carried-by' },
      h('div', 'flex items-center justify-between pb-1.5 border-b border-line',
        h('h3', 'text-xs font-semibold uppercase tracking-wider text-muted', 'Carried by'),
        h('span', 'text-[11px] text-fg font-medium', 'You')),
      h(ExcludedList, { excluded: a.excluded })) : h('section', { className: 'bg-card border border-line rounded-[6px] p-4 flex flex-col gap-3', 'data-testid': 'carried-by' },
      h('div', 'flex items-center justify-between pb-1.5 border-b border-line',
        h('h3', 'text-xs font-semibold uppercase tracking-wider text-muted', 'Carried by'),
        h('button', { type: 'button', className: 'text-[11px] text-needs font-medium inline-flex items-center min-h-[24px] min-w-[24px] hover:underline', 'data-testid': 'change-pick', onClick: () => setPicking(!picking) }, 'Change')),
      h('div', 'flex flex-col gap-3',
        ...(picking
          ? a.suggestions.map(s => h('div', { key: s.profile, className: 'cursor-pointer', 'data-pick': s.profile, onClick: async () => { setPicking(false); await act(`${P(project)}/specs/${r.id}/pick`, { agent: s.profile }) } }, h(ScoreCard, { s, first: a.pick ? a.pick.profile === s.profile : false })))
          : shown.map((s, i) => h(ScoreCard, { key: s.profile, s, first: i === 0 }))),
        a.pick ? h('div', { className: 'text-[11px] text-muted', 'data-testid': 'picked-by' }, `picked by ${a.pick.picked_by === 'you' ? 'you' : a.pick.picked_by}`) : null,
        !a.suggestions.length ? h('div', 'text-xs text-fail', 'No eligible profile') : null,
        h(ExcludedList, { excluded: a.excluded }))),
    h(CarrierSection, { project, r, onErr: setErr }))
  return h(Page, { project, sel: r.id, back: () => goBack('rung', { rid: r.parent }) }, body)
}

function dayClock(ts) {
  if (!ts) return ''
  const d = new Date(ts * 1000)
  const today = new Date()
  const same = d.toDateString() === today.toDateString()
  return `${same ? 'today' : d.toISOString().slice(0, 10)} ${clock(ts)}`
}

// The latest run: the last attempt of the latest develop run that ran tests, every test in it; with no
// develop run, the newest execution of each command test.
function SpecExecs({ tests, run }) {
  const att = run && (run.attempts || []).filter(a => (a.executions || []).length).slice(-1)[0]
  const rows = att
    ? att.executions
    : tests.filter(t => t.type !== 'manual').map(t => { const x = (t.executions || [])[0]; return x ? { ...x, test: t.id } : null }).filter(Boolean)
  return h(ExecList, { execs: rows, limit: Math.max(1, rows.length), showTest: true })
}

// ------------------------------------------------------------------ specification editor (I write, AI supports)

function SpecEdit({ project, req, spec, ret, need }) {
  const sq = useRung(project, spec)
  const rq = useRung(project, req || (sq.data && sq.data.parent))
  const s = sq.data
  const r = rq.data
  const pre = usePrefill(spec ? '' : 'spec-edit')
  const [text, setText] = useState(pre.text != null ? pre.text : null)
  const [detail, setDetail] = useState(pre.detail != null ? pre.detail : null)
  const base = useBase(s && s.version, text == null && detail == null)
  const [sug, setSug] = useState(null)
  const [mark, setMark] = useState('')
  const [err, setErr] = useState('')
  const [conflict, setConflict] = useState(null)
  const reqId = req || (s && s.parent)
  useEffect(() => {
    if (!reqId) return
    let live = true
    rest(`${P(project)}/rungs/${reqId}/support`).then(x => { if (live) setSug(x.suggestion || '') }).catch(() => { if (live) setSug('') })
    return () => { live = false }
  }, [reqId])
  const t = text != null ? text : (s ? s.text : '')
  const d = detail != null ? detail : (s ? s.detail : '')
  useDirty((text != null && text !== (s ? s.text : '')) || (detail != null && detail !== (s ? s.detail : '')))
  const dest = () => (ret ? ['build', { need: need || (r && r.parent), step: ret }] : ['rung', { rid: s ? s.id : reqId }])
  const done = () => goBack(...dest(), { force: true })
  const saved = id => finish(...dest(), `Approved ${id}`)
  useExit(done, true)
  if (sq.error || rq.error) return h(Missing, { project, text: errText(sq.error || rq.error) })
  if ((spec && !s) || !r) return h(Page, { project }, h(Loading))
  const save = async () => {
    let x
    if (s) x = await post(`${P(project)}/rungs/${s.id}/edit`, { text: t, detail: d, approve: true, version: base })
    else {
      x = await post(`${P(project)}/rungs/${reqId}/spec`, { text: t, detail: d, suggestion: mark === 'accepted' ? sug : null })
      if (x.ok) x = await post(`${P(project)}/rungs/${x.data.id}/approve`)
    }
    if (!x.ok) { setConflict(x.code === 'conflict' ? x : null); return setErr(x.code === 'conflict' ? '' : x.error) }
    saved((x.data && x.data.id) || (s && s.id) || 'specification')
  }
  const path = s ? s.path : [...r.path, { id: r.id }]
  const body = h('div', { className: 'flex flex-col gap-4 bg-card border border-line rounded-[6px] p-5', 'data-testid': 'spec-editor' },
    h('div', 'flex items-center justify-between',
      h(Crumbs, { path, last: s ? s.id : 'New specification' }),
      h(Badge, { status: s ? s.status : 'draft' })),
    h('div', 'flex flex-col gap-1.5',
      h('label', 'text-[11px] font-semibold uppercase tracking-wider text-muted', 'Specification'),
      h('input', { className: 'w-full bg-well border border-line rounded-[6px] px-3 py-2 text-sm font-semibold text-fg focus:outline-none focus:border-needs', type: 'text', name: 'spec-text', value: t, autoFocus: true, onChange: e => setText(e.target.value) })),
    h('div', 'flex flex-col gap-1.5',
      h('label', 'text-[11px] font-semibold uppercase tracking-wider text-muted', 'Approach'),
      h('textarea', { className: 'w-full bg-well border border-line rounded-[6px] p-3 text-xs text-fg font-mono leading-relaxed focus:outline-none focus:border-needs resize-none', rows: 3, name: 'spec-detail', value: d, onChange: e => setDetail(e.target.value) })),
    sug ? h('div', { className: cx('flex items-center justify-between bg-well border border-line2 rounded-[6px] p-3', mark === 'dismissed' && 'opacity-40 line-through'), 'data-testid': 'support' },
      h('div', 'flex flex-col gap-0.5',
        h('span', 'text-[11px] font-semibold text-muted', 'Suggested by writer'),
        h('span', 'text-xs text-fg', sug)),
      h('div', 'flex items-center gap-2',
        h('button', { type: 'button', className: 'px-2.5 py-1 rounded-[6px] bg-btn border border-line text-fg text-xs font-medium', 'data-testid': 'accept-support', disabled: !!mark, onClick: () => { setMark('accepted'); setDetail((d ? d + '\n' : '') + sug) } }, mark === 'accepted' ? 'Accepted' : 'Accept'),
        h('button', { type: 'button', className: 'px-2.5 py-1 rounded-[6px] bg-btn border border-line text-muted text-xs font-medium', disabled: !!mark, onClick: () => setMark('dismissed') }, 'Dismiss'))) : null,
    s ? null : h(DraftBar, { project, kind: 'specification', parent: reqId, fields: { text: t, detail: d }, apply: v => { if (v.text != null) setText(v.text); if (v.detail != null) setDetail(v.detail) } }),
    h(ErrorLine, { text: err }),
    h(Conflict, { res: conflict, path: s ? `/projects/${encodeURIComponent(project)}/rungs/${encodeURIComponent(s.id)}` : null }),
    h('div', 'flex items-center gap-2 pt-2 border-t border-line',
      h('button', { type: 'button', className: 'px-3 py-1.5 rounded-[6px] bg-needs text-on-needs font-semibold text-xs', 'data-testid': 'save-approve', onClick: save }, 'Save and approve'),
      h('button', { type: 'button', className: 'px-3 py-1.5 rounded-[6px] bg-btn border border-line text-fg text-xs font-medium', onClick: done }, 'Cancel')))
  return h(Page, { project, sel: s ? s.id : reqId }, body)
}

// ------------------------------------------------------------------ test detail

function TestView({ project, r }) {
  const [err, setErr] = useState('')
  const [result, setResult] = useState('')
  const [note, setNote] = useState('')
  useDirty(r.type === 'manual' && (result || note.trim()))
  const leave = () => goBack('rung', { rid: r.parent }, { force: true })
  useExit(() => { if (r.type === 'manual') leave() })
  const execs = r.executions || []
  const act = async (path, body, go) => {
    const x = await post(path, body)
    if (!x.ok) return setErr(x.error)
    setErr('')
    if (go) go(x.data)
  }
  const runOne = () => act(`${P(project)}/tests/${r.id}/run`, {}, d => navigate('exec', { test: r.id, n: d.n }))
  const headline = (badge) => h('div', 'flex flex-col gap-1.5',
    h('div', 'flex items-center justify-between', pathCrumbs(r), badge),
    h('div', 'flex items-center gap-2', h('h2', 'text-sm font-semibold text-fg mono', r.type === 'manual' ? r.text : (r.command || r.text))),
    h('div', 'text-[11px] text-muted', h('span', null, TYPE_WORD[r.type] || 'Command test')))
  if (r.type === 'manual') {
    const pending = execs.find(x => x.status === 'pending' && !x.invalidated)
    const res = r.result || 'not_run'
    const badge = res === 'not_run'
      ? h('span', 'inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-line/50 text-muted border border-line', 'Not run')
      : h(Badge, { status: res })
    const body = h('div', 'flex flex-col gap-6',
      h(Card, { className: 'p-4 flex flex-col gap-4', testid: 'manual-test' },
        headline(badge),
        h('div', 'flex flex-col gap-2 pt-3 border-t border-line',
          h(Label, null, 'Steps'),
          h('div', 'flex flex-col gap-1.5 text-xs text-fg mono',
            ...(r.steps || []).map((st, i) => h('div', { key: i, className: 'flex items-start gap-2 bg-well p-2.5 rounded-[6px] border border-line2' }, h('span', null, String(i + 1)), h('span', null, st))))),
        pending
          ? h('div', { className: 'flex flex-col gap-2 pt-3 border-t border-line', 'data-testid': 'pending' },
            h(Label, null, 'Result'),
            h('div', 'flex items-center justify-between bg-well p-2.5 rounded-[6px] border border-needs/30 font-mono text-[11px] text-fg',
              h('div', 'flex items-center gap-2', h(Dot, { t: 'needs' }), h('span', null, `#${pending.n} pass · ${pending.recorder} · ${clock(pending.started_at)}`)),
              h('span', 'text-[10px] text-needs font-medium', 'waiting for approval')),
            pending.note ? h('div', 'text-xs mono text-muted', pending.note) : null)
          : frag(
            h('div', 'flex flex-col gap-2 pt-3 border-t border-line',
              h(Label, null, 'Result'),
              h('div', 'flex items-center gap-2',
                h('button', { type: 'button', className: cx('px-4 py-1.5 rounded-[6px] border font-semibold text-xs', result === 'pass' ? 'border-pass bg-pass/10 text-pass' : 'border-line bg-well text-muted'), 'data-testid': 'result-pass', 'aria-pressed': result === 'pass' ? 'true' : 'false', onClick: () => setResult('pass') }, 'Pass'),
                h('button', { type: 'button', className: cx('px-4 py-1.5 rounded-[6px] border font-semibold text-xs', result === 'fail' ? 'border-fail bg-fail/10 text-fail' : 'border-line bg-well text-muted'), 'data-testid': 'result-fail', 'aria-pressed': result === 'fail' ? 'true' : 'false', onClick: () => setResult('fail') }, 'Fail'))),
            h('div', 'flex flex-col gap-2 pt-3 border-t border-line',
              h(Label, null, 'Evidence'),
              h('textarea', { className: 'w-full bg-well border border-line rounded-[6px] p-2.5 text-xs mono text-fg focus:outline-none focus:border-needs', rows: 2, name: 'evidence', value: note, onChange: e => setNote(e.target.value) }))),
        execs.length ? h('div', 'flex flex-col gap-2 pt-3 border-t border-line', h(Label, null, 'Executions'), h(ExecList, { test: r.id, execs, limit: 6 })) : null,
        h(ErrorLine, { text: err }),
        h('div', 'flex items-center gap-2 pt-3 border-t border-line',
          pending
            ? frag(
              h(Btn, { kind: 'primary', testid: 'approve-result', onClick: () => act(`${P(project)}/tests/${r.id}/executions/${pending.n}/approve`) }, 'Approve result'),
              h(Btn, { onClick: () => goBack('rung', { rid: r.parent }) }, 'Back'))
            : frag(
              h(Btn, { kind: 'primary', testid: 'record', disabled: !result, onClick: () => act(`${P(project)}/tests/${r.id}/record`, { result, note }, () => { setResult(''); setNote(''); notify(`Recorded a result on ${r.id}`) }) }, 'Record'),
              h(Btn, { onClick: leave }, 'Cancel')))))
    return h(Page, { project, sel: r.id }, body)
  }
  const badge = h('span', 'flex items-center gap-1.5', h(SeenFailing, { value: r.seen_failing }),
    r.status === 'stale' ? h(Badge, { status: 'stale' }) : h(Badge, { status: r.result === 'not_run' ? 'not_run' : (r.result || 'not_run') }))
  const failing = execs.filter(x => x.status === 'fail')  // fails stay failed after an upstream edit
  const body = h('div', 'flex flex-col gap-6',
    h(Card, { className: 'p-4 flex flex-col gap-4', testid: 'command-test' },
      headline(badge),
      h('div', 'flex flex-col gap-1.5 pt-3 border-t border-line',
        h(Label, null, 'Pass rule'),
        h('div', { className: 'text-xs mono text-fg', 'data-testid': 'pass-rule' }, passRule(r))),
      r.type === 'ai_judged' ? h('div', { className: 'text-[11px] text-dim', 'data-testid': 'no-gate' }, 'Cannot release a gate') : null,
      h('div', 'flex flex-col gap-2 pt-3 border-t border-line',
        h('div', 'flex items-center justify-between', h(Label, null, 'Executions'), h(SeenFailing, { value: r.seen_failing, small: true })),
        h('div', { className: 'flex flex-col gap-2', 'data-testid': 'executions' },
          ...(execs.length ? execs : []).map(x => h(ExecRow, { key: x.n, test: r.id, x })),
          execs.length ? null : h(Empty, { text: 'No executions yet', action: 'Run tests', actionTestid: 'run-tests', onClick: runOne }))),
      h('div', { className: 'flex flex-col gap-2 pt-3 border-t border-line', 'data-testid': (r.defects || []).length ? 'defects' : 'no-defects' },
        h(Label, null, 'Defects'),
        (r.defects || []).length ? null : h(Well, { className: 'text-xs text-dim' }, 'No defects'),
        ...(r.defects || []).map(dx => h(Well, { key: dx.id, className: 'flex items-center justify-between text-xs' },
          h('span', 'text-fg', `${dx.id} · ${dx.title}`),
          h('span', 'mono text-[11px] text-muted', `${dx.category} · ${dx.executions.map(n => '#' + n).join(' ')}`)))),
      h(ErrorLine, { text: err }),
      h('div', 'flex items-center gap-2 pt-3 border-t border-line',
        execs.length ? h(Btn, { kind: 'primary', testid: 'run-tests', onClick: runOne }, 'Run tests') : null,
        h(Btn, { testid: 'raise-defect', disabled: !failing.length, onClick: () => openDefect(r.id) }, 'Raise defect'))))
  return h(Page, { project, sel: r.id, back: () => goBack('rung', { rid: r.parent }) }, body)
}

function ExecRow({ test, x }) {
  const dead = x.invalidated && x.status === 'pass'
  if (dead) {
    return h('div', { className: 'flex items-center justify-between bg-well p-2.5 rounded-[6px] border border-line2 font-mono text-[11px] line-through text-dim cursor-pointer', 'data-exec': `${test}#${x.n}`, onClick: () => navigate('exec', { test, n: x.n }) },
      h('div', 'flex items-center gap-2', h('span', 'w-1.5 h-1.5 rounded-full bg-dim'), h('span', null, execLine(x))),
      h('span', 'inline-flex items-center px-1.5 py-0.5 rounded text-[10px] no-underline font-medium bg-stale/15 text-stale border border-stale/30', 'Stale'))
  }
  const t = x.status === 'pass' ? 'pass' : x.status === 'fail' ? 'fail' : ['running', 'pending', 'error'].includes(x.status) ? 'needs' : 'dim'
  return h('div', { className: cx('flex items-center justify-between bg-well p-2.5 rounded-[6px] border font-mono text-[11px] text-fg cursor-pointer', t === 'fail' ? 'border-fail/30' : t === 'pass' ? 'border-pass/30' : 'border-line2'), 'data-exec': `${test}#${x.n}`, onClick: () => navigate('exec', { test, n: x.n }) },
    h('div', 'flex items-center gap-2', h(Dot, { t }), h('span', null, execLine(x))),
    h('span', { className: cx('text-[10px] font-medium', TONE_TEXT[t]) }, x.status === 'pass' ? 'pass' : x.status === 'fail' ? 'failed' : x.status))
}

// ------------------------------------------------------------------ test editor

function TestEdit({ project, test, spec, ret, need }) {
  const tq = useRung(project, test)
  const t = tq.data
  const base = useBase(t && t.version)
  const specId = spec || (t && t.parent)
  const sq = useRung(project, specId)
  const stQ = useApi('/settings')
  const st = stQ.data
  const pre = usePrefill(test ? '' : 'test-edit')
  const [f, setF] = useState(null)
  const [err, setErr] = useState('')
  const [ran, setRan] = useState(null)
  const [conflict, setConflict] = useState(null)
  const init = useRef(null)
  useDirty(f && init.current && JSON.stringify(f) !== init.current)
  const dest = () => {
    const s = sq.data
    if (!s) return ['home', null]
    return ret ? ['build', { need: need || (s.path[0] && s.path[0].id), step: ret }] : ['rung', { rid: t ? t.id : s.id }]
  }
  const done = () => goBack(...dest(), { force: true })
  const saved = () => finish(...dest())
  useExit(done, true)
  useEffect(() => {
    if (f) return
    if (test && !t) return
    if (!st) return
    const proj = (st.projects || []).find(p => p.name === project) || {}
    const blank = t
      ? { type: t.type, command: t.command || '', folder: t.folder || '.', rule: (t.pass_rule || {}).kind || 'exit_code', value: String((t.pass_rule || {}).value ?? 0), timeout: `${t.timeout || 120}s`, limit: `${Math.round((t.output_limit || 64000) / 1000)} KB`, steps: (t.steps || []).join('\n'), text: t.type === 'ai_judged' ? t.text : '' }
      : { type: 'command', command: '', folder: '.', rule: 'exit_code', value: '0', timeout: `${st.settings.test_timeout || 120}s`, limit: `${Math.round((st.settings.output_limit || 64000) / 1000)} KB`, steps: '', text: '', _folder: proj.folder }
    // A pasted text is typed text: the blank form is what counts as unchanged.
    init.current = JSON.stringify(blank)
    setF(t ? blank : { ...blank, ...pre })
  }, [t, st])
  useEffect(() => { if (f && !init.current) init.current = JSON.stringify(f) }, [f])
  if (tq.error || sq.error || stQ.error) return h(Missing, { project, text: errText(tq.error || sq.error || stQ.error) })
  if (!f || !sq.data) return h(Page, { project }, h(Loading))
  const s = sq.data
  const set = k => e => setF({ ...f, [k]: e.target.value })
  const fields = () => {
    if (f.type === 'manual') return { type: 'manual', steps: f.steps.split('\n').map(x => x.trim()).filter(Boolean) }
    const out = { type: f.type, command: f.command, folder: f.folder || '.', pass_rule: { kind: f.rule, value: f.rule === 'exit_code' ? parseInt(f.value, 10) || 0 : f.value }, timeout: parseInt(f.timeout, 10) || 120, output_limit: (parseInt(f.limit, 10) || 64) * 1000 }
    if (f.type === 'ai_judged') out.text = f.text || f.command
    return out
  }
  const save = async () => {
    const x = t ? await post(`${P(project)}/tests/${t.id}`, { fields: { ...fields(), version: base } }) : await post(`${P(project)}/specs/${s.id}/tests`, { fields: fields() })
    if (!x.ok) { setConflict(x.code === 'conflict' ? x : null); return setErr(x.code === 'conflict' ? '' : x.error) }
    saved()
    notify(t ? `Saved ${t.id}` : `Added ${x.data && x.data.id ? x.data.id : 'test'}`)
  }
  const runOnce = async () => {
    let id = t && t.id
    if (!id) {
      const x = await post(`${P(project)}/specs/${s.id}/tests`, { fields: fields() })
      if (!x.ok) return setErr(x.error)
      id = x.data.id
    } else {
      const x = await post(`${P(project)}/tests/${id}`, { fields: fields() })
      if (!x.ok) return setErr(x.error)
    }
    const r = await post(`${P(project)}/tests/${id}/run`, { once: true })
    if (!r.ok) return setErr(r.error)
    finish('exec', { test: id, n: r.data.n })
  }
  const input = (k, extra) => h('input', { className: cx('bg-well border border-line rounded-[6px] px-3 py-2 mono text-xs text-fg focus:outline-none focus:border-needs', (extra && extra.w) || 'w-full'), type: 'text', name: k, value: f[k], onChange: set(k), 'aria-label': (extra && extra.label) || undefined })
  const body = h('section', { className: 'bg-card border border-line rounded-[6px] p-5 flex flex-col gap-5', 'data-testid': 'test-editor' },
    h('div', 'flex flex-col gap-1.5 pb-4 border-b border-line',
      h('h2', 'text-base font-semibold text-fg', 'Test editor'),
      h(Crumbs, { path: [...s.path, { id: s.id }], last: t ? t.id : 'New test' })),
    h('div', 'flex flex-col gap-1.5',
      h('span', 'text-xs font-medium text-muted', 'Type'),
      h('div', { className: 'inline-flex bg-well p-1 rounded-[6px] border border-line w-fit', 'data-testid': 'test-type', role: 'radiogroup' },
        ...[['command', 'Command'], ['manual', 'Manual'], ['ai_judged', 'AI judged']].map(([v, label]) => h('button', {
          key: v, type: 'button', role: 'radio', 'aria-checked': f.type === v ? 'true' : 'false',
          className: f.type === v ? 'px-3 py-1 rounded-[4px] bg-needs text-on-needs text-xs font-semibold' : 'px-3 py-1 rounded-[4px] text-muted text-xs font-medium',
          onClick: () => setF({ ...f, type: v })
        }, label)))),
    f.type === 'manual'
      ? h('div', 'flex flex-col gap-1.5',
        h('span', 'text-xs font-medium text-muted', 'Steps'),
        h('textarea', { className: 'w-full bg-well border border-line rounded-[6px] p-3 mono text-xs text-fg focus:outline-none focus:border-needs leading-relaxed', rows: 4, name: 'steps', value: f.steps, onChange: set('steps') }))
      : frag(
        f.type === 'ai_judged' ? h('div', 'flex flex-col gap-1.5',
          h('span', 'text-xs font-medium text-muted', 'Judge question'),
          input('text'),
          h('span', { className: 'text-[11px] text-dim', 'data-testid': 'no-gate' }, 'Cannot release a gate')) : null,
        h('div', 'flex flex-col gap-1.5', h('span', 'text-xs font-medium text-muted', 'Command'), input('command')),
        h('div', 'flex flex-col gap-1.5', h('span', 'text-xs font-medium text-muted', 'Working folder'), input('folder', { label: 'Working folder' })),
        h('div', 'flex flex-col gap-1.5',
          h('span', 'text-xs font-medium text-muted', 'Pass rule'),
          h('div', 'flex items-center gap-3',
            h('div', 'relative w-44',
              h('select', { className: 'w-full appearance-none bg-well border border-line rounded-[6px] px-3 py-2 text-xs text-fg focus:outline-none focus:border-needs cursor-pointer', name: 'rule', value: f.rule, onChange: set('rule') },
                h('option', { value: 'exit_code' }, 'Exit code'),
                h('option', { value: 'output_contains' }, 'Output contains')),
              h('div', 'pointer-events-none absolute inset-y-0 right-0 flex items-center px-2.5 text-muted', '▾')),
            input('value', { w: 'w-24' }))),
        h('div', 'grid grid-cols-2 gap-4',
          h('div', 'flex flex-col gap-1.5', h('span', 'text-xs font-medium text-muted', 'Timeout'), input('timeout')),
          h('div', 'flex flex-col gap-1.5', h('span', 'text-xs font-medium text-muted', 'Output limit'), input('limit')))),
    t ? null : h(DraftBar, { project, kind: 'test', parent: s.id, fields: { command: f.command, steps: f.steps }, apply: v => setF(cur => ({ ...cur, ...v, type: v.steps && !v.command ? 'manual' : cur.type })) }),
    h(ErrorLine, { text: err }),
    h(Conflict, { res: conflict, path: t ? `/projects/${encodeURIComponent(project)}/rungs/${encodeURIComponent(t.id)}` : null }),
    h('div', 'flex items-center gap-2.5 pt-4 border-t border-line',
      h('button', { type: 'button', className: 'px-3.5 py-1.5 rounded-[6px] bg-needs text-on-needs font-semibold text-xs', 'data-testid': 'save-test', onClick: save }, 'Save test'),
      f.type === 'manual' ? null : h('button', { type: 'button', className: 'px-3.5 py-1.5 rounded-[6px] bg-btn border border-line text-fg text-xs font-medium', 'data-testid': 'run-once', onClick: runOnce }, 'Run once'),
      h('button', { type: 'button', className: 'px-3 py-1.5 rounded-[6px] text-muted text-xs font-medium', onClick: done }, 'Cancel')))
  return h(Page, { project, sel: t ? t.id : s.id }, body)
}
