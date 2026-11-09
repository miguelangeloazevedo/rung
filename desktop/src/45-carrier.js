// Rung desktop pane: what a specification asks of its carrier, excluded profiles, claims.

function ChipList({ items, onRemove, onAdd, testid, addLabel, attr }) {
  const [adding, setAdding] = useState(false)
  const [text, setText] = useState('')
  const done = () => { setAdding(false); setText('') }
  return h('div', { className: 'flex items-center gap-1.5 flex-wrap', 'data-testid': testid },
    ...items.map(t => h('span', { key: t, className: 'inline-flex items-center gap-1 px-2 py-0.5 rounded bg-btn border border-line text-fg text-[11px] mono', [attr]: t },
      t, onRemove ? h('button', { type: 'button', className: 'text-muted hover:text-fg', 'aria-label': `Remove ${t}`, 'data-remove': t, onClick: () => onRemove(t) }, '×') : null)),
    onAdd
      ? adding
        ? h('input', {
          autoFocus: true, className: 'w-24 bg-well border border-line rounded px-1.5 py-0.5 text-[11px] text-fg mono outline-none',
          value: text, 'aria-label': addLabel, 'data-testid': testid + '-input',
          onChange: e => setText(e.target.value),
          onBlur: done,
          onKeyDown: e => {
            if (e.key === 'Enter') {
              const v = text.trim()
              if (v && !items.includes(v)) onAdd(v)
              done()
            }
            if (e.key === 'Escape') { e.preventDefault(); done() }
          }
        })
        : h('button', { type: 'button', className: 'px-1.5 py-0.5 rounded bg-btn border border-line text-muted text-[11px]', 'aria-label': addLabel, 'data-testid': testid + '-add', onClick: () => setAdding(true) }, '+')
      : null)
}

function ExcludedList({ excluded, testid }) {
  if (!excluded || !excluded.length) return null
  return h('div', { className: 'flex flex-col gap-1', 'data-testid': testid || 'excluded' },
    h('span', 'text-[11px] font-semibold uppercase tracking-wider text-muted', 'Excluded'),
    ...excluded.map(x => h('div', { key: x.profile, className: 'flex items-center justify-between gap-3 text-[11px] min-w-0', 'data-excluded': x.profile },
      h('span', 'mono text-fg shrink-0', x.profile),
      h('span', { className: 'text-muted truncate', title: x.reason, 'data-reason': x.reason }, x.reason))))
}

function CarrierSection({ project, r, onErr }) {
  const a = r.allocation || {}
  const tools = a.required_tools || []
  const set = async body => {
    const x = await post(`${P(project)}/specs/${r.id}/allocation`, body)
    onErr(x.ok ? '' : x.error)
  }
  const row = (label, ctl, help) => h('div', 'flex items-center justify-between gap-3 text-xs',
    help ? h('span', { className: 'text-fg font-medium', tabIndex: 0, title: help, 'data-help': help, 'aria-label': `${label}: ${help}` }, label) : h('span', 'text-fg font-medium', label), ctl)
  return h('section', { className: 'bg-card border border-line rounded-[6px] p-4 flex flex-col gap-3', 'data-testid': 'carrier' },
    h('div', 'flex items-center justify-between pb-1.5 border-b border-line',
      h('h3', 'text-xs font-semibold uppercase tracking-wider text-muted', 'Carrier')),
    row('Required tools', h(ChipList, {
      items: tools, testid: 'required-tools', attr: 'data-required-tool', addLabel: `Add a required tool to ${r.id}`,
      onRemove: t => set({ required_tools: tools.filter(x => x !== t) }),
      onAdd: t => set({ required_tools: [...tools, t] })
    })),
    row('Independent carrier', h(Toggle, { on: !!a.independent, testid: 'independent', label: `${r.id} independent carrier`, onChange: v => set({ independent: v }) }), a.independent_help),
    row('Human only', h('div', 'flex items-center gap-2',
      a.human_only_reason === 'all tests manual' ? h('span', 'text-[11px] text-muted', 'all tests manual') : null,
      h(Toggle, { on: !!a.marked_human_only, testid: 'human-only', label: `${r.id} human only`, onChange: v => set({ human_only: v }) }))))
}

const CLAIM_WORD = { open: 'open', reported: 'reported', released: 'released' }

function claimLine(c) {
  if (c.status === 'reported') return `reported · ${(c.proof || []).join(', ')}`
  if (c.status === 'released') return `released by ${c.closed_by || 'you'}`
  return 'open'
}

function ClaimsSection({ project, r, onErr }) {
  const claims = r.claims || []
  if (!claims.length) return null
  const open = claims.some(c => c.status === 'open')
  const release = async () => {
    const x = await post(`${P(project)}/specs/${r.id}/claims/release`, {})
    onErr(x.ok ? '' : x.error)
  }
  return h('section', { className: 'bg-card border border-line rounded-[6px] p-4 flex flex-col gap-3', 'data-testid': 'claims' },
    h('div', 'flex items-center justify-between pb-1.5 border-b border-line',
      h('h3', 'text-xs font-semibold uppercase tracking-wider text-muted', 'Claims'),
      open ? h(Btn, { kind: 'small', testid: 'release-claim', onClick: release }, 'Release') : null),
    h('div', 'flex flex-col gap-2',
      ...claims.slice().reverse().map(c => h('div', { key: c.id, className: 'bg-well p-2.5 rounded-[6px] border border-line2 flex items-center justify-between gap-3 text-[11px] min-w-0', 'data-claim': c.id, 'data-status': c.status },
        h('div', 'flex flex-col gap-0.5 min-w-0',
          h('span', { className: 'mono text-fg truncate', title: `${c.profile} · ${c.chat}` }, `${c.profile} · ${c.chat}`),
          h('span', 'text-muted mono', `${clock(c.opened_at)}${c.closed_at ? ' to ' + clock(c.closed_at) : ''}`)),
        h('span', { className: cx('font-medium shrink-0', c.status === 'open' ? 'text-needs' : c.status === 'reported' ? 'text-pass' : 'text-muted'), 'data-testid': 'claim-state' }, claimLine(c))))))
}

// What holds a claimed specification back, in a few words: the first rung below it that blocks
// ("blocked by T-2.1a"), else the specification's own first blocker ("blocked: S-2.1 has no tests").
function blockedText(chk) {
  const list = ((chk && chk.blockers) || []).map(String)
  for (const b of list) {
    const m = b.match(/^[NRST]-\d+(?:\.\d+)?[a-z]?/)
    if (m && m[0] !== chk.id) return `blocked by ${m[0]}`
  }
  return list.length ? `blocked: ${list[0]}` : 'blocked'
}

function ClaimRow({ c }) {
  const blocked = c.check && !c.check.ok
  return h(Card, { className: 'p-3 flex items-center justify-between gap-3 text-xs', testid: 'running-claim', onClick: () => navigate('rung', { rid: c.spec }) },
    h('span', { className: 'text-fg mono truncate', title: `${c.spec} · ${c.profile} · ${c.chat}` }, `${c.spec} · ${c.profile} · ${c.chat}`),
    h('span', { className: cx('text-[11px] font-medium shrink-0', blocked ? 'text-fail' : 'text-pass') },
      blocked ? `claimed · ${blockedText(c.check)}` : 'claimed · check passes'))
}
