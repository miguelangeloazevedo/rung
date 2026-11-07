// Rung desktop pane: bot help (decisions Round 13). Paste text, Draft on New forms, Suggest on a need.
// Every bot action only proposes: a placed or drafted text lands when you save the form, a suggestion when
// you accept it. Nothing here touches the check, the done hook or a test result.

// ------------------------------------------------------------------ prefill for a New form

// Fields handed to the next New form (from Paste text). Read when the form mounts, cleared once it has.
let PREFILL = null
function setPrefill(view, fields) { PREFILL = { view, fields } }
function usePrefill(view) {
  const got = useRef(PREFILL && PREFILL.view === view ? PREFILL.fields : null)
  useEffect(() => { if (PREFILL && PREFILL.view === view) PREFILL = null }, [])
  return got.current || {}
}

// ------------------------------------------------------------------ a bot job

// Starts a job, follows it until it ends, and cancels it when the view that started it goes away.
function useBotJob() {
  const [job, setJob] = useState(null)
  const [err, setErr] = useState('')
  const live = useRef(true)
  const cur = useRef(null)
  useEffect(() => {
    live.current = true  // a remount (React's strict mode runs effects twice) must follow again
    return () => {
      live.current = false
      if (cur.current) rest(`/bot/${cur.current}/cancel`, { method: 'POST', body: {} }).catch(() => {})
    }
  }, [])
  const follow = async id => {
    cur.current = id
    while (live.current && cur.current === id) {
      await new Promise(r => setTimeout(r, 300))
      let j
      try { j = await rest(`/bot/${id}`) } catch (e) { if (live.current) setErr(errText(e)); return }
      if (!live.current || cur.current !== id) return
      setJob(j)
      if (j.status !== 'running') { cur.current = null; return j }
    }
  }
  const start = async (path, body, pick) => {
    setErr('')
    const x = await post(path, body)
    if (!x.ok) { setErr(x.error); return null }
    const j = pick ? pick(x.data) : x.data
    setJob(j)
    if (j && j.status === 'running') return follow(j.id)
    return j
  }
  const cancel = async () => {
    const id = cur.current
    if (!id) return
    cur.current = null
    const x = await post(`/bot/${id}/cancel`)
    if (x.ok) setJob(x.data); else setErr(x.error)
  }
  return { job, setJob, err, setErr, start, cancel, busy: !!job && job.status === 'running' }
}

function BotFailure({ job, err, onRetry, testid }) {
  const text = err || (job && job.status === 'failed' ? job.error : '')
  if (!text) return null
  return h('div', { className: 'flex items-center justify-between gap-2', 'data-testid': testid || 'bot-failure' },
    h(ErrorLine, { text }),
    onRetry ? h(Btn, { kind: 'small', testid: 'bot-retry', onClick: onRetry }, 'Retry') : null)
}

// ------------------------------------------------------------------ Paste text

const NEW_VIEW = { need: 'need-new', requirement: 'req-new', specification: 'spec-edit', test: 'test-edit' }
const PARENT_OF = { requirement: 'need', specification: 'requirement', test: 'specification' }

function PasteBtn({ project, projects }) {
  const [open, setOpen] = useState(false)
  return frag(
    h(Btn, { testid: 'paste-text', onClick: () => setOpen(true) }, 'Paste text'),
    open ? h(PasteDialog, { project, projects, onClose: () => setOpen(false) }) : null)
}

function PasteDialog({ project, projects, onClose }) {
  const [proj, setProj] = useState(project || (projects && projects[0]) || '')
  const [text, setText] = useState('')
  const [kind, setKind] = useState('')
  const [parent, setParent] = useState('')
  const [check, setCheck] = useState({ valid: false, reason: '' })
  const bot = useBotJob()
  const tq = useApi(proj ? `${P(proj)}/bot/targets` : null, { enabled: !!proj })
  const targets = (tq.data && tq.data.targets) || []
  const res = bot.job && bot.job.status === 'done' ? bot.job.result : null
  // The answer fills the choices; an answer the engine refused leaves the parent for you to choose.
  useEffect(() => {
    if (!res) return
    setKind(res.kind || 'need')
    setParent(res.valid ? (res.parent || '') : '')
  }, [res && bot.job.id])
  useEffect(() => {
    if (!res || !kind) return
    let on = true
    rest(`${P(proj)}/bot/check-place`, { method: 'POST', body: { kind, parent: parent || null } }).then(x => { if (on) setCheck(x) }).catch(e => { if (on) setCheck({ valid: false, reason: errText(e) }) })
    return () => { on = false }
  }, [kind, parent, res && bot.job.id])
  const place = () => bot.start(`${P(proj)}/bot/place`, { text })
  const open = async () => {
    if (proj !== project) {
      const x = await post(`${P(proj)}/open`)
      if (!x.ok) return bot.setErr(x.error)
    }
    const view = NEW_VIEW[kind]
    const params = kind === 'need' ? null : kind === 'requirement' ? { need: parent } : kind === 'specification' ? { req: parent } : { spec: parent }
    setPrefill(view, kind === 'test' ? { command: res.text } : { text: res.text })
    onClose()
    navigate(view, params, { force: true })
  }
  const parents = targets.filter(t => t.kind === PARENT_OF[kind])
  const sel = (name, value, onChange, opts, label) => h('select', { className: INPUT, name, value, 'aria-label': label, onChange: e => onChange(e.target.value) }, ...opts.map(([v, l]) => h('option', { key: v, value: v }, l)))
  const footer = res
    ? frag(h(Btn, { onClick: onClose }, 'Cancel'), h(Btn, { kind: 'primary', testid: 'open-as-new', disabled: !check.valid, onClick: open }, `Open as new ${(KIND_WORD[kind] || 'rung').toLowerCase()}`))
    : bot.busy
      ? frag(h(Btn, { testid: 'bot-cancel', label: 'Cancel placing', onClick: bot.cancel }, 'Cancel'))
      : frag(h(Btn, { onClick: onClose }, 'Cancel'), h(Btn, { kind: 'primary', testid: 'place', disabled: !text.trim() || !proj, onClick: place }, 'Place'))
  return h(Dialog, { title: 'Paste text', onClose, dirty: !!text.trim(), testid: 'paste-dialog', footer },
    projects && projects.length > 1 && !res ? h(Field, { label: 'Project' }, sel('project', proj, setProj, projects.map(p => [p, p]), 'Project')) : null,
    res
      ? h('div', { className: 'flex flex-col gap-3', 'data-testid': 'placed' },
        h(Well, { className: 'text-xs text-fg', testid: 'placed-text' }, res.text),
        h('div', { className: 'flex items-center gap-2 text-xs', 'data-testid': 'placed-as' },
          h('span', 'font-semibold text-fg', KIND_WORD[res.kind] || res.kind || 'Unknown'),
          res.parent ? h('span', 'text-muted', 'under') : null,
          res.parent ? h('span', 'mono text-needs font-medium', res.parent) : null,
          h('span', 'text-muted', `· ${bot.job.profile}`)),
        res.why ? h('div', { className: 'text-xs text-muted', 'data-testid': 'placed-why' }, res.why) : null,
        res.valid ? null : h('div', { className: 'text-xs text-fail', 'data-testid': 'place-refused' }, `Not offered: ${res.reason}`),
        h('div', 'grid grid-cols-2 gap-3',
          h(Field, { label: 'Kind' }, sel('kind', kind, v => { setKind(v); setParent('') }, Object.entries(KIND_WORD), 'Kind')),
          kind === 'need' ? null : h(Field, { label: 'Parent' }, sel('parent', parent, setParent, [['', 'Choose'], ...parents.map(t => [t.id, `${t.id} ${t.text}`])], 'Parent'))),
        check.reason && (parent || kind === 'need') ? h('div', { className: 'text-[11px] text-fail', 'data-testid': 'place-check' }, check.reason) : null)
      : h(Field, { label: 'Text' }, h('textarea', { className: INPUT, rows: 4, name: 'paste', value: text, 'data-autofocus': '1', readOnly: bot.busy, onChange: e => setText(e.target.value) })),
    bot.busy ? h('div', { className: 'text-xs text-needs', 'data-testid': 'bot-running' }, `Placing · ${bot.job.profile}`) : null,
    bot.job && bot.job.status === 'cancelled' && !res ? h('div', { className: 'text-xs text-muted', 'data-testid': 'bot-cancelled' }, 'Cancelled') : null,
    h(BotFailure, { job: bot.job, err: bot.err, onRetry: text.trim() ? place : null }))
}

// ------------------------------------------------------------------ Draft on a New form

// `fields` is what the form holds now; `apply(values)` writes drafted values into the form. Fields with text
// are only replaced after you choose Replace.
function DraftBar({ project, kind, parent, fields, apply }) {
  const bot = useBotJob()
  const [asking, setAsking] = useState(false)
  const [by, setBy] = useState('')
  const typed = Object.values(fields).some(v => String(v || '').trim())
  const run = async replace => {
    setAsking(false)
    const keep = replace ? {} : fields
    const j = await bot.start(`${P(project)}/bot/draft`, { kind, parent: parent || null, fields: keep })
    if (j && j.status === 'done') {
      const got = j.result.fields || {}
      const out = {}
      for (const [k, v] of Object.entries(got)) {
        if (!(k in fields)) continue
        const val = Array.isArray(v) ? v.join('\n') : String(v)
        if (replace || !String(fields[k] || '').trim()) out[k] = val
      }
      apply(out)
      setBy(j.profile)
    }
  }
  return h('div', { className: 'flex flex-col gap-2', 'data-testid': 'draft-bar' },
    h('div', 'flex items-center gap-2',
      bot.busy
        ? frag(h('span', { className: 'text-xs text-needs', 'data-testid': 'bot-running' }, `Drafting · ${bot.job.profile}`),
          h(Btn, { kind: 'small', testid: 'bot-cancel', label: 'Cancel draft', onClick: bot.cancel }, 'Cancel'))
        : h(Btn, { kind: 'small', testid: 'draft', onClick: () => (typed ? setAsking(true) : run(true)) }, 'Draft'),
      by && !bot.busy ? h('span', { className: 'text-[11px] text-muted', 'data-testid': 'drafted-by' }, `Drafted by ${by}`) : null,
      bot.job && bot.job.status === 'cancelled' ? h('span', { className: 'text-[11px] text-muted', 'data-testid': 'bot-cancelled' }, 'Cancelled') : null),
    h(BotFailure, { job: bot.job, err: bot.err, onRetry: () => run(false) }),
    asking ? h(Dialog, {
      title: 'Draft', onClose: () => setAsking(false), testid: 'draft-ask',
      footer: frag(h(Btn, { testid: 'draft-keep', onClick: () => run(false) }, 'Keep'), h(Btn, { kind: 'primary', testid: 'draft-replace', onClick: () => run(true) }, 'Replace'))
    }, h('div', 'text-xs text-fg', 'Replace typed text')) : null)
}

// ------------------------------------------------------------------ Suggest on a need

function scoreLine(s) {
  return `score ${s.score} · tags ${s.parts.tags} · load ${s.parts.load} · reliability ${s.parts.reliability} · cost ${s.parts.cost}`
}

function SuggestPanel({ project, need, ro }) {
  const bot = useBotJob()
  const [choice, setChoice] = useState(null)
  const [none, setNone] = useState(false)
  const [itemErr, setItemErr] = useState('')
  const asked = useRef(false)
  const latest = useApi(`${P(project)}/needs/${need}/suggest-latest`, { live: true })
  // The latest result shows when you come back, and follows the need's requirements (Changed since).
  useEffect(() => {
    const j = latest.data && latest.data.job
    if (!j || bot.busy) return
    if ((!bot.job && !asked.current) || (bot.job && bot.job.id === j.id && j.status !== 'running')) { bot.setJob(j); setChoice((j.input || {}).choice || null) }
  }, [latest.data])
  const run = async () => {
    setNone(false); setItemErr('')
    asked.current = true
    await bot.start(`${P(project)}/needs/${need}/suggest-missing`, {}, d => { setChoice(d.choice); if (!d.job) setNone(true); return d.job })
  }
  const resolve = async (i, accept) => {
    const x = await post(`${P(project)}/bot/${bot.job.id}/items/${i}`, { accept })
    if (!x.ok) return setItemErr(x.error)
    setItemErr('')
    bot.setJob(x.data.job)
    queryClient.invalidateQueries({ queryKey: ['rung'] })
  }
  const j = bot.job
  const items = j && j.status === 'done' ? (j.result.items || []) : []
  const chosen = choice && choice.chosen
  const rank = chosen && choice.ranked ? choice.ranked.findIndex(s => s.profile === chosen.profile) + 1 : 0
  return h('div', { className: 'flex flex-col gap-2 pt-3 border-t border-line', 'data-testid': 'bot-suggest' },
    h('div', 'flex items-center justify-between pb-1',
      h('span', 'text-xs font-semibold uppercase tracking-wider text-muted', 'Suggested requirements'),
      ro ? null : bot.busy
        ? h(Btn, { kind: 'small', testid: 'bot-cancel', label: 'Cancel suggest', onClick: bot.cancel }, 'Cancel')
        : h(Btn, { kind: 'small', testid: 'suggest', onClick: run }, 'Suggest')),
    none ? h('div', { className: 'flex flex-col gap-2', 'data-testid': 'suggest-none' },
      h('div', 'text-xs text-fg', 'No profile can suggest')) : null,
    j && chosen ? h('div', { className: 'flex flex-wrap items-center gap-2 text-[11px]', 'data-testid': 'suggest-profile' },
      h('span', 'font-semibold text-fg text-xs', j.profile),
      h('span', 'mono text-muted', `ranked ${rank} of ${choice.ranked.length} · ${scoreLine(chosen)}`),
      j.changed_since ? h(Badge, { status: 'stale', label: 'Changed since', small: true }) : null) : null,
    bot.busy ? h('div', { className: 'text-xs text-needs', 'data-testid': 'bot-running' }, `Suggesting · ${j.profile}`) : null,
    j && j.status === 'cancelled' ? h('div', { className: 'text-xs text-muted', 'data-testid': 'bot-cancelled' }, 'Cancelled') : null,
    h(BotFailure, { job: j, err: bot.err, onRetry: ro ? null : run }),
    items.length ? h('div', { className: 'flex flex-col gap-2', 'data-testid': 'suggest-items' },
      ...items.map((it, i) => h('div', {
        key: i, className: cx('flex items-center justify-between gap-3 bg-well p-2.5 rounded-[6px] border border-line2', it.status === 'dismissed' && 'opacity-40 line-through'),
        'data-suggestion': it.text, 'data-mark': it.status
      },
      h('div', 'flex items-center gap-2 min-w-0',
        h('span', 'text-xs text-fg', it.text),
        it.rung ? h('span', 'mono text-[11px] text-needs', it.rung) : null),
      ro ? null : h('div', 'flex items-center gap-2 shrink-0',
        h(Btn, { kind: 'accept', disabled: it.status !== 'open', label: `Accept ${it.text}`, onClick: () => resolve(i, true) }, it.status === 'accepted' ? 'Accepted' : 'Accept'),
        h(Btn, { kind: 'ghost', disabled: it.status !== 'open', label: `Dismiss ${it.text}`, onClick: () => resolve(i, false) }, it.status === 'dismissed' ? 'Dismissed' : 'Dismiss'))))) : null,
    h(ErrorLine, { text: itemErr }),
    choice && (choice.excluded || []).length && (none || j) ? h('div', { className: 'flex flex-col gap-1', 'data-testid': 'suggest-excluded' },
      h('span', 'text-[11px] font-semibold uppercase tracking-wider text-muted', 'Excluded'),
      ...choice.excluded.map(x => h('div', { key: x.profile, className: 'flex items-center gap-2 text-[11px]', 'data-profile': x.profile },
        h('span', 'font-medium text-muted', x.profile), h('span', 'text-dim', x.reason)))) : null)
}
