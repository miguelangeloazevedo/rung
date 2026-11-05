// Rung desktop pane: start screen, First green, read-out, project settings, archive, retire, dialogs.

// ------------------------------------------------------------------ dialog

const FOCUSABLE = 'button:not([disabled]), [href], input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])'

function Dialog({ title, onClose, children, footer, testid }) {
  const box = useRef(null)
  useEffect(() => {
    const opener = document.activeElement
    const first = box.current && (box.current.querySelector('[data-autofocus]') || box.current.querySelector(FOCUSABLE))
    if (first) first.focus()
    return () => { if (opener && opener.focus && document.contains(opener)) opener.focus() }
  }, [])
  const onKeyDown = e => {
    if (e.key === 'Escape') { e.stopPropagation(); onClose(); return }
    if (e.key !== 'Tab' || !box.current) return
    const els = [...box.current.querySelectorAll(FOCUSABLE)].filter(el => el.offsetParent !== null)
    if (!els.length) return
    const i = els.indexOf(document.activeElement)
    if (e.shiftKey && i <= 0) { e.preventDefault(); els[els.length - 1].focus() }
    else if (!e.shiftKey && i === els.length - 1) { e.preventDefault(); els[0].focus() }
  }
  const tid = (testid || 'dialog') + '-title'
  return h('div', { className: 'absolute inset-0 bg-well/75 flex items-center justify-center z-50 p-4', onMouseDown: e => { if (e.target === e.currentTarget) onClose() } },
    h('div', { ref: box, role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': tid, 'data-testid': testid, onKeyDown, className: 'w-[480px] bg-card border border-line rounded-[6px] shadow-2xl flex flex-col' },
      h('div', 'flex items-center justify-between px-5 py-4 border-b border-line',
        h('h3', { id: tid, className: 'text-sm font-semibold text-fg' }, title),
        h('button', { type: 'button', className: 'text-muted', 'aria-label': 'Close', onClick: onClose }, '✕')),
      h('div', 'p-5 flex flex-col gap-4', children),
      footer ? h('div', 'flex items-center justify-end gap-2 px-5 py-3.5 border-t border-line bg-card', footer) : null))
}

function DangerBtn({ onClick, disabled, children, testid }) {
  return h('button', {
    type: 'button', disabled: !!disabled, 'aria-disabled': disabled ? 'true' : undefined, 'data-testid': testid,
    className: cx('px-3.5 py-1.5 rounded-[6px] bg-btn border border-fail text-fail font-semibold text-xs', disabled && 'opacity-40 cursor-not-allowed'),
    onClick
  }, children)
}

function Field({ label, error, children }) {
  return h('div', 'flex flex-col gap-1.5',
    h('span', 'text-xs font-medium text-muted', label),
    children,
    error ? h('span', { className: 'text-[11px] text-fail', 'data-testid': 'field-error' }, error) : null)
}

const INPUT = 'w-full px-3 py-2 bg-well border border-line rounded-[6px] text-xs text-fg outline-none focus:border-needs'

// ------------------------------------------------------------------ start screen

function StartScreen() {
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const sample = async () => {
    setBusy(true)
    const r = await post('/sample')
    setBusy(false)
    if (!r.ok) return setErr(r.error)
    navigate('home')
  }
  const dismiss = async () => {
    const r = await post('/onboarding', { start_dismissed: true })
    if (!r.ok) return setErr(r.error)
    navigate('project-new')
  }
  return h('div', { className: 'flex flex-row h-full w-full overflow-hidden', 'data-testid': 'start' },
    h('div', 'flex-1 h-full overflow-y-auto flex items-center justify-center p-8',
      h('div', 'w-[520px] bg-card border border-line rounded-[6px] p-6 flex flex-col gap-6',
        h('div', 'flex items-center justify-between',
          h('h1', 'text-xl font-bold tracking-tight text-fg', 'Rung'),
          h('button', { type: 'button', className: 'px-2 py-1 rounded text-xs text-muted hover:text-fg', 'aria-label': 'Dismiss', 'data-testid': 'start-dismiss', onClick: dismiss }, '✕')),
        h('div', 'flex flex-col gap-2.5',
          h(Btn, { kind: 'primaryLg', testid: 'start-sample', disabled: busy, onClick: sample }, 'Try the sample project'),
          h(Btn, { testid: 'start-new', onClick: () => navigate('project-new') }, 'New project')),
        h(ErrorLine, { text: err }))))
}

// ------------------------------------------------------------------ First green checklist

// Projects whose checklist was shown incomplete in this window: it stays up, all ticked, once complete.
const FG_SEEN = new Set()

function FirstGreen({ project }) {
  const q = useApi(`/projects/${encodeURIComponent(project)}/first-green`, { live: true })
  const fg = q.data
  if (fg && fg.done < fg.total) FG_SEEN.add(project)
  if (!fg || fg.hidden || (fg.done === fg.total && !FG_SEEN.has(project))) return null
  const hide = () => post('/onboarding', { checklist_hidden: true })
  return h('section', { className: 'bg-card border border-line rounded-[6px] p-4 flex flex-col gap-3', 'data-testid': 'first-green', 'aria-labelledby': 'rung-first-green' },
    h('div', 'flex items-center justify-between',
      h('h2', { id: 'rung-first-green', className: 'text-xs font-semibold uppercase tracking-wider text-muted' }, 'First green'),
      h('div', 'flex items-center gap-2',
        h('span', { className: 'text-[11px] mono text-muted', 'data-testid': 'first-green-count' }, `${fg.done} of ${fg.total}`),
        h('button', { type: 'button', className: 'px-1.5 text-xs text-muted hover:text-fg', 'aria-label': 'Dismiss First green', 'data-testid': 'first-green-dismiss', onClick: hide }, '✕'))),
    h('ul', 'flex flex-col gap-1.5',
      ...fg.items.map(i => h('li', { key: i.key, className: 'flex items-center gap-2 text-xs', 'data-item': i.key, 'data-done': i.done ? '1' : '0' },
        h('span', { className: cx('w-4 text-center font-bold', i.done ? 'text-pass' : 'text-dim'), 'aria-hidden': 'true' }, i.done ? '✓' : '○'),
        h('span', { className: i.done ? 'text-fg' : 'text-muted' }, i.label),
        h('span', { className: 'sr-only' }, i.done ? 'done' : 'not done')))))
}

// ------------------------------------------------------------------ Needs you: error and needs input

function ErrorCard({ project, item, ro }) {
  return h(Card, { className: 'px-4 py-3 flex items-center justify-between', testid: 'needs-you-item', style: { borderLeft: '3px solid var(--r-needs)' } },
    h('div', 'flex flex-col gap-1 min-w-0',
      h('div', 'flex items-center gap-2 text-xs', h(Badge, { status: 'error' }), h('span', 'mono text-muted', `${item.id} #${item.n}`)),
      h('span', 'text-sm text-fg', item.text),
      item.reason ? h('span', { className: 'text-[11px] mono text-muted truncate', 'data-testid': 'error-reason' }, item.reason) : null),
    h('div', 'flex items-center gap-2',
      h(Btn, { kind: 'small', testid: 'open-error', onClick: () => navigate('exec', { test: item.id, n: item.n }) }, 'Open'),
      ro ? null : h(Btn, { kind: 'small', onClick: () => navigate('rung', { rid: item.id }) }, 'Open test')))
}

function NeedsInputCard({ project, item, ro }) {
  const [err, setErr] = useState('')
  const again = async () => {
    const x = await post(`/projects/${encodeURIComponent(project)}/specs/${item.id}/send`, {})
    if (!x.ok) return setErr(x.error)
    navigate('run', { run: x.data.id })
  }
  return h(Card, { className: 'px-4 py-3 flex items-center justify-between', testid: 'needs-you-item', style: { borderLeft: '3px solid var(--r-needs)' } },
    h('div', 'flex flex-col gap-1 min-w-0',
      h('div', 'flex items-center gap-2 text-xs', h(Badge, { status: 'needs_input' }), h('span', 'mono text-muted', `${item.id} · run ${item.run} · ${item.profile}`)),
      h('span', { className: 'text-sm text-fg', 'data-testid': 'needs-input-reason' }, item.text),
      h(ErrorLine, { text: err })),
    h('div', 'flex items-center gap-2',
      h(Btn, { kind: 'small', onClick: () => navigate('run', { run: item.run }) }, 'Open run'),
      ro ? null : h(Btn, { kind: 'acceptSolid', testid: 'run-again', onClick: again }, 'Run again')))
}

function ArchivedBar({ project }) {
  const [err, setErr] = useState('')
  return h('div', { className: 'flex items-center justify-between px-3 py-2 rounded-[6px] bg-well border border-line2 text-xs', 'data-testid': 'archived-bar' },
    h('div', 'flex items-center gap-2 text-muted', h(Badge, { status: 'archived' }), h('span', null, project)),
    h('div', 'flex items-center gap-2',
      h(ErrorLine, { text: err }),
      h(Btn, { kind: 'small', testid: 'restore-project', onClick: async () => { const x = await post(`/projects/${encodeURIComponent(project)}/restore`); setErr(x.ok ? '' : x.error) } }, 'Restore')))
}

// ------------------------------------------------------------------ read-out

function ReadOut({ project, need }) {
  const q = useApi(`${P(project)}/needs/${need}/readout`, { live: true })
  const [exported, setExported] = useState(null)
  const [err, setErr] = useState('')
  const d = q.data
  if (q.error) return h(Page, { project }, h(ErrorLine, { text: errText(q.error) }), h(Btn, { onClick: () => navigate('home') }, 'Back'))
  if (!d) return h(Page, { project, sel: need }, h(Loading))
  const n = d.need
  const exp = async () => {
    const x = await post(`${P(project)}/needs/${need}/readout/export`)
    if (!x.ok) return setErr(x.error)
    setErr(''); setExported(x.data.path)
  }
  const proof = p => [`${p.test} #${p.n}`, 'pass', p.carried_by, `${dayClock(p.at)}`].filter(Boolean).join(' · ')
  const body = h(Card, { className: 'p-4 flex flex-col gap-4', testid: 'readout' },
    h('div', 'flex items-center justify-between',
      h(Crumbs, { path: [{ id: n.id }], last: 'Read-out' }),
      n.retired ? h(Badge, { status: 'retired' }) : h(Badge, { status: n.status })),
    h(Section, { title: 'Intent', testid: 'readout-intent' },
      h(Well, { className: 'flex flex-col gap-1' },
        h('span', { className: 'text-sm font-semibold text-fg', 'data-testid': 'intent-text' }, n.text),
        h('span', { className: 'text-[11px] mono text-muted', 'data-testid': 'intent-version' }, [`version ${n.version}`, n.approved_by && `approved by ${n.approved_by}`, n.approved_at && dayClock(n.approved_at)].filter(Boolean).join(' · ')))),
    h(Section, { title: 'Plan', testid: 'readout-plan' },
      d.plan.length ? h('div', 'flex flex-col gap-2',
        ...d.plan.map(r => h(Well, { key: r.id, className: 'flex flex-col gap-1.5', testid: 'plan-' + r.id },
          h('div', 'flex items-center justify-between text-xs',
            h('span', null, h('span', 'mono font-semibold text-fg', r.id), ' ', h('span', 'text-fg', r.text)),
            h(Badge, { status: r.status, small: true })),
          ...r.specifications.map(s => h('div', { key: s.id, className: 'pl-3 border-l border-line flex flex-col gap-1' },
            h('div', 'flex items-center justify-between text-xs',
              h('span', null, h('span', 'mono text-fg', s.id), ' ', h('span', 'text-muted', s.text)),
              h(Badge, { status: s.status, small: true })),
            ...s.tests.map(t => h('div', { key: t.id, className: 'pl-3 border-l border-line flex items-center justify-between text-[11px]', 'data-plan-test': t.id },
              h('span', 'mono text-muted truncate', `${t.id} · ${t.type === 'manual' ? t.text : t.command}`),
              h('span', 'flex items-center gap-1.5', h(SeenFailing, { value: t.seen_failing, small: true }),
                h(Badge, { status: t.status === 'stale' ? 'stale' : t.result, small: true })))))))))
        : h(Well, { className: 'text-xs text-dim' }, 'No requirements')),
    h(Section, { title: 'Delivered', testid: 'readout-delivered', right: h('span', { className: 'text-[11px] mono text-muted', 'data-testid': 'proven-count' }, `${d.proven} of ${d.total} proven`) },
      d.delivered.length ? h('div', 'flex flex-col gap-1.5',
        ...d.delivered.map(r => h(Well, { key: r.id, className: 'flex items-center justify-between text-xs gap-3', testid: 'delivered-' + r.id },
          h('span', 'min-w-0', h('span', 'mono font-semibold text-fg', r.id), ' ', h('span', 'text-fg', r.text)),
          r.proven
            ? h('span', 'flex items-center gap-1.5 shrink-0',
              h('span', { className: 'mono text-[11px] text-muted', 'data-testid': 'proof' }, proof(r.proof)),
              h(SeenFailing, { value: r.proof.seen_failing, small: true }),
              h(Badge, { status: 'proven', small: true }))
            : h('span', 'flex items-center gap-1.5 shrink-0',
              h('span', { className: 'text-[11px] text-muted', 'data-testid': 'not-proven-reason' }, r.reason),
              h(Badge, { status: 'not_proven', small: true })))))
        : h(Well, { className: 'text-xs text-dim' }, 'No requirements')),
    exported ? h(Well, { className: 'flex items-center justify-between text-xs', testid: 'export-path' },
      h('span', 'text-muted', 'Exported'), h('span', 'mono text-fg', shortPath(exported))) : null,
    h(ErrorLine, { text: err }),
    h('div', 'flex items-center gap-2 pt-3 border-t border-line',
      h(Btn, { kind: 'primary', testid: 'export', onClick: exp }, 'Export'),
      h(Btn, { testid: 'back', onClick: () => navigate('rung', { rid: n.id }) }, 'Back')))
  return h(Page, { project, sel: n.id }, body)
}

// ------------------------------------------------------------------ retire a need

function RetireDialog({ project, need, onClose }) {
  const [reason, setReason] = useState('')
  const [err, setErr] = useState('')
  const go = async () => {
    const x = await post(`${P(project)}/needs/${need}/retire`, { reason })
    if (!x.ok) return setErr(x.error)
    onClose()
    navigate('home')
  }
  return h(Dialog, {
    title: `Retire ${need}`, onClose, testid: 'retire-dialog',
    footer: frag(h(Btn, { onClick: onClose }, 'Cancel'), h(DangerBtn, { testid: 'retire-confirm', disabled: !reason.trim(), onClick: go }, 'Retire'))
  },
  h(Field, { label: 'Reason' }, h('textarea', { className: INPUT, rows: 3, name: 'reason', value: reason, 'data-autofocus': '1', onChange: e => setReason(e.target.value) })),
  h(ErrorLine, { text: err }))
}

function RetiredBar({ project, r }) {
  const [err, setErr] = useState('')
  return h('div', { className: 'flex items-center justify-between px-3 py-2 rounded-[6px] bg-well border border-line2 text-xs', 'data-testid': 'retired-bar' },
    h('div', 'flex items-center gap-2 min-w-0',
      h(Badge, { status: 'retired' }),
      h('span', { className: 'text-fg truncate', 'data-testid': 'retired-reason' }, r.retired_reason || ''),
      r.retired_at ? h('span', 'mono text-[11px] text-muted', dayClock(r.retired_at)) : null),
    h('div', 'flex items-center gap-2',
      h(ErrorLine, { text: err }),
      h(Btn, { kind: 'small', testid: 'restore-need', onClick: async () => { const x = await post(`${P(project)}/needs/${r.id}/restore`); setErr(x.ok ? '' : x.error) } }, 'Restore')))
}

function Retired({ project }) {
  const q = useApi(`${P(project)}/retired`, { live: true })
  const rows = q.data || []
  const main = frag(
    h('header', 'flex items-center justify-between',
      h('h1', 'text-xl font-bold tracking-tight text-fg', 'Retired needs'),
      h(Btn, { onClick: () => navigate('home') }, 'Back')),
    h('div', { className: 'flex flex-col gap-2.5', 'data-testid': 'retired-list' },
      q.data && !rows.length ? h('div', { className: 'bg-card border border-line rounded-[6px] p-3 text-xs text-dim', 'data-testid': 'empty' }, 'No retired needs') : null,
      ...rows.map(n => h(Card, { key: n.id, className: 'p-4 flex items-center justify-between', testid: 'retired-row', onClick: () => navigate('rung', { rid: n.id }) },
        h('div', 'flex flex-col gap-1 min-w-0',
          h('div', 'flex items-center gap-2 text-xs', h('span', 'mono font-semibold text-fg', n.id), h('span', 'text-fg', n.text)),
          h('span', { className: 'text-[11px] text-muted', 'data-testid': 'retired-reason' }, n.retired_reason || '')),
        h('div', 'flex items-center gap-2 shrink-0',
          h('span', 'text-[11px] mono text-muted', dayClock(n.retired_at)),
          h(Badge, { status: 'retired' }))))))
  return h(Frame, { main })
}

// ------------------------------------------------------------------ delete a project

function DeleteDialog({ name, onClose, after }) {
  const [typed, setTyped] = useState('')
  const [err, setErr] = useState('')
  const go = async () => {
    const x = await post(`/projects/${encodeURIComponent(name)}/delete`, { confirm: typed })
    if (!x.ok) return setErr(x.error)
    onClose()
    if (after) after(x.data)
  }
  return h(Dialog, {
    title: `Delete ${name}`, onClose, testid: 'delete-dialog',
    footer: frag(h(Btn, { onClick: onClose }, 'Cancel'), h(DangerBtn, { testid: 'delete-confirm', disabled: typed !== name, onClick: go }, 'Delete'))
  },
  h(Field, { label: 'Project name' }, h('input', { className: INPUT, type: 'text', name: 'confirm', value: typed, autoComplete: 'off', 'data-autofocus': '1', onChange: e => setTyped(e.target.value) })),
  h(ErrorLine, { text: err }))
}

function afterDelete(out) {
  navigate(out && out.current ? 'projects' : 'home')
}

// ------------------------------------------------------------------ project settings

function ProjectSettings({ project }) {
  const st = useApi('/state').data
  const pq = useApi(`/projects/${encodeURIComponent(project)}/events`)
  const proj = st && ((st.projects || []).find(p => p.name === project))
  const [f, setF] = useState(null)
  const [errs, setErrs] = useState({})
  const [err, setErr] = useState('')
  const [del, setDel] = useState(false)
  useEffect(() => {
    if (!f && proj) setF({ name: proj.name, folder: proj.folder, test_command: proj.test_command, profiles: proj.profiles })
  }, [proj && proj.name])
  if (!st) return h(Frame, { main: h(Loading) })
  if (!proj || !f) {
    return h(Frame, { main: frag(h(ErrorLine, { text: st.current_archived ? `${project} is archived` : `no project ${project}` }), h('div', null, h(Btn, { onClick: () => navigate('projects') }, 'Projects'))) })
  }
  const all = (st.profiles || []).map(p => p.name)
  const set = k => e => setF({ ...f, [k]: e.target.value })
  const save = async () => {
    const x = await post(`/projects/${encodeURIComponent(project)}/update`, f)
    if (!x.ok) { setErrs(x.field ? { [x.field]: x.error } : {}); return setErr(x.field ? '' : x.error) }
    setErrs({}); setErr('')
    if (x.data.name !== project) navigate('project-settings', { k: Date.now() })
  }
  const archive = async () => {
    const x = await post(`/projects/${encodeURIComponent(project)}/archive`)
    if (!x.ok) return setErr(x.error)
    navigate('projects', { tab: 'archived' })
  }
  const events = (pq.data || []).filter(e => e.kind === 'project_changed').slice().reverse()
  const main = frag(
    h('header', 'flex items-center justify-between',
      h('h1', 'text-xl font-bold tracking-tight text-fg', 'Project settings'),
      h(Btn, { onClick: () => navigate('home') }, 'Back')),
    h('section', { className: 'bg-card border border-line rounded-[6px] p-5 flex flex-col gap-4', 'data-testid': 'project-settings' },
      h(Field, { label: 'Name', error: errs.name }, h('input', { className: INPUT, type: 'text', name: 'name', value: f.name, onChange: set('name') })),
      h(Field, { label: 'Folder', error: errs.folder }, h('input', { className: cx(INPUT, 'font-mono'), type: 'text', name: 'folder', value: f.folder, onChange: set('folder') })),
      h(Field, { label: 'Test command', error: errs.test_command }, h('input', { className: cx(INPUT, 'font-mono'), type: 'text', name: 'test_command', value: f.test_command, onChange: set('test_command') })),
      h(Field, { label: 'Profiles', error: errs.profiles },
        h('div', 'flex flex-col gap-2 pt-1',
          ...all.map(p => h('label', { key: p, className: 'flex items-center gap-2.5 text-xs text-fg cursor-pointer' },
            h('input', { type: 'checkbox', className: 'rounded accent-needs', name: 'profile', value: p, checked: f.profiles.includes(p), onChange: e => setF({ ...f, profiles: e.target.checked ? [...f.profiles, p] : f.profiles.filter(x => x !== p) }) }),
            h('span', null, p))))),
      h(ErrorLine, { text: err }),
      h('div', 'flex items-center justify-end gap-2 pt-3 border-t border-line',
        h(Btn, { kind: 'primary', testid: 'save-project', onClick: save }, 'Save'))),
    h('section', { className: 'flex flex-col gap-2', 'data-testid': 'project-history' },
      h(SectionTitle, null, 'History'),
      events.length
        ? h('div', 'bg-well p-2.5 rounded-[6px] border border-line2 font-mono text-[11px] flex flex-col gap-1',
          ...events.map((e, i) => h('div', { key: i, className: 'flex items-center justify-between text-fg' },
            h('span', 'truncate', Object.entries(e.data).map(([k, v]) => `${k.replace('_', ' ')}: ${[].concat(v.before).join(', ')} > ${[].concat(v.after).join(', ')}`).join(' · ')),
            h('span', 'text-muted shrink-0', `${e.by} · ${dayClock(e.at)}`))))
        : h('div', 'bg-card border border-line rounded-[6px] p-3 text-xs text-dim', 'No changes')),
    h('section', { className: 'flex items-center gap-2 pt-2', 'data-testid': 'project-danger' },
      h(Btn, { testid: 'archive-project', onClick: archive }, 'Archive'),
      h(DangerBtn, { testid: 'delete-project', onClick: () => setDel(true) }, 'Delete')),
    del ? h(DeleteDialog, { name: project, onClose: () => setDel(false), after: afterDelete }) : null)
  return h('div', 'relative h-full w-full', h(Frame, { main }))
}

// ------------------------------------------------------------------ archived projects

function ArchivedList() {
  const q = useApi('/projects/archived', { live: true })
  const rows = q.data || []
  const [del, setDel] = useState(null)
  const [err, setErr] = useState('')
  const act = async (name, what) => {
    const x = await post(`/projects/${encodeURIComponent(name)}/${what}`)
    if (!x.ok) return setErr(x.error)
    setErr('')
    if (what === 'open') navigate('home')
  }
  return h('div', { className: 'flex flex-col gap-2.5', 'data-testid': 'archived-list' },
    q.data && !rows.length ? h('div', { className: 'bg-card border border-line rounded-[6px] p-3 text-xs text-dim', 'data-testid': 'empty' }, 'No archived projects') : null,
    ...rows.map(p => h(Card, { key: p.name, className: 'p-4 flex items-center justify-between', testid: 'archived-row' },
      h('div', 'flex flex-col gap-1',
        h('div', 'flex items-center gap-2', h('span', { className: 'text-sm font-semibold text-fg', 'data-testid': 'project-row-name' }, p.name), h(Badge, { status: 'archived', small: true })),
        h('div', 'text-xs mono text-muted', shortPath(p.folder))),
      h('div', 'flex items-center gap-2',
        h(Btn, { kind: 'small', testid: 'open-archived', onClick: () => act(p.name, 'open') }, 'Open'),
        h(Btn, { kind: 'small', testid: 'restore', onClick: () => act(p.name, 'restore') }, 'Restore'),
        h(DangerBtn, { testid: 'delete', onClick: () => setDel(p.name) }, 'Delete')))),
    h(ErrorLine, { text: err }),
    del ? h(DeleteDialog, { name: del, onClose: () => setDel(null), after: () => {} }) : null)
}

// ------------------------------------------------------------------ edit conflicts

async function reloadView(path) {
  if (path) {
    try { queryClient.setQueryData(['rung', path], await rest(path)) } catch (_) { /* the view shows the error */ }
  }
  $nav.set({ ...$nav.get(), k: Date.now() })
}

function Conflict({ res, path }) {
  if (!res || res.code !== 'conflict') return null
  return h('div', { className: 'flex items-center justify-between px-3 py-2 rounded-[6px] bg-needs/10 border border-needs/30 text-xs text-needs', 'data-testid': 'conflict', role: 'alert' },
    h('span', null, res.error),
    h(Btn, { kind: 'small', testid: 'reload', onClick: () => reloadView(path) }, 'Reload'))
}

Object.assign(VIEWS, {
  readout: ReadOut,
  retired: Retired,
  'project-settings': ProjectSettings
})
