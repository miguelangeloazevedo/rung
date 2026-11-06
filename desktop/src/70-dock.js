// Rung desktop pane: the dock, a compact companion beside the chat (PANES_AREA, right, collapsible).
// Shows Needs you, Running, the current need's
// ladder with a need picker, and Open Rung. Same data, status colours and labels as the full page.

const DOCK_PANE = 'dock'
const DOCK_KEY = 'rung.dock'
const LAST_NEED_KEY = 'rung.lastNeed'

function readJSON(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key) || '') || fallback } catch (_) { return fallback }
}

const $dockOpen = atom(readJSON(DOCK_KEY, false) === true)
const $lastNeed = atom(readJSON(LAST_NEED_KEY, {}))

function noteNeed(project, need) {
  if (!project || !need || !/^N-\d+$/.test(need)) return
  const cur = $lastNeed.get()
  if (cur[project] === need) return
  const next = { ...cur, [project]: need }
  $lastNeed.set(next)
  try { localStorage.setItem(LAST_NEED_KEY, JSON.stringify(next)) } catch (_) { /* private mode */ }
}

// The label a rung carries on the full page, shared by the rail (as data-label) and the dock.
function rungLabel(n) {
  if (!n) return ''
  if (n.kind === 'test') return n.status === 'stale' ? 'stale' : resultWord(n.result)
  if (n.status === 'stale') return 'stale'
  if (n.status === 'draft' || n.status === 'proposed') return n.status
  if (n.kind === 'specification') {
    if (n.released) return 'released'
    if ((n.blockers || []).some(b => /failed/.test(b))) return 'failing'
    return 'open'
  }
  if (n.kind === 'requirement') return { covered: 'covered', failing: 'failing', stale: 'stale', draft: 'draft' }[n.coverage] || 'not covered'
  return n.status || ''
}

function liveKids(n) {
  return (n.children || []).filter(c => c.status !== 'dismissed' && c.status !== 'proposed')
}

// The ids above a rung, need first: [N-1, R-2] for S-2.1.
function chainOf(nodes, rid, above) {
  for (const x of nodes || []) {
    if (x.id === rid) return above
    const got = chainOf(x.children, rid, [...above, x.id])
    if (got) return got
  }
  return null
}

function needOf(tree, rid) {
  for (const n of tree || []) {
    const stack = [n]
    while (stack.length) {
      const x = stack.pop()
      if (x.id === rid) return n.id
      stack.push(...(x.children || []))
    }
  }
  return null
}

const ITEM_BADGE = { stale: 'stale', proposed: 'proposed', approval: 'pending', error: 'error', needs_input: 'needs_input' }

function openItem(i) {
  if (i.type === 'error') return navigate('exec', { test: i.id, n: i.n })
  if (i.type === 'needs_input') return navigate('run', { run: i.run })
  return navigate('rung', { rid: i.id })
}

function DockSection({ id, title, count, tone: t, children }) {
  return h('section', { className: 'dk-sec', 'aria-labelledby': id, 'data-testid': 'dock-' + id.split('-')[1] },
    h('h3', { id, className: 'dk-h' },
      h(Dot, { t: t || 'dim' }), h('span', null, title),
      count == null ? null : h('span', { className: 'dk-count mono', 'data-testid': 'dock-count' }, String(count))),
    children)
}

function DockEmpty({ label, action, onAction }) {
  return h('div', { className: 'dk-empty', 'data-testid': 'dock-empty' },
    h('span', null, label),
    action ? h('button', { type: 'button', className: 'dk-btn', onClick: onAction }, action) : null)
}

function DockNeedRow({ i, path }) {
  const label = `${i.id} ${i.text || ''}`
  const meta = i.type === 'approval' ? `#${i.n} recorded by ${i.recorder || 'you'}`
    : i.type === 'error' ? `#${i.n} ${i.reason || ''}`.trim()
      : i.type === 'proposed' && i.proposer ? `by ${i.proposer}${i.source_chat ? ' · ' + i.source_chat : ''}`
        : i.type === 'stale' && i.change ? `${i.change.rung} changed · ${ago(i.change.at)}` : ''
  return h('button', { type: 'button', className: 'dk-row', title: label, 'data-testid': 'dock-item', 'data-item': i.id, onClick: () => openItem(i) },
    h('span', 'dk-row-top',
      h('span', { className: cx('mono dk-id', i.type === 'proposed' ? 'text-needs' : 'text-fg') }, i.id),
      h(Badge, { status: ITEM_BADGE[i.type] || i.type, small: true }),
      path ? h('span', { className: 'dk-path mono truncate', title: path }, path) : null),
    i.text ? h('span', { className: 'dk-text truncate', title: i.text }, i.text) : null,
    meta ? h('span', { className: 'dk-meta mono truncate', title: meta }, meta) : null)
}

function DockRunRow({ run }) {
  useTick(1000)
  const last = run.attempts[run.attempts.length - 1]
  const n = last ? last.n : 1
  const secs = run.started_at ? Date.now() / 1000 - run.started_at : 0
  const meta = `${run.profile} · attempt ${n} of ${run.max_attempts}`
  return h('button', { type: 'button', className: 'dk-row', title: `${run.spec} run`, 'data-testid': 'dock-run', 'data-run': run.id, onClick: () => navigate('run', { run: run.id }) },
    h('span', 'dk-row-top',
      h('span', 'mono dk-id text-fg', run.spec),
      h('span', 'dk-chip', run.status === 'queued' ? 'queued' : 'run'),
      h('span', { className: 'dk-path mono', 'data-testid': 'dock-elapsed' }, dur(secs))),
    h('span', { className: 'dk-meta mono truncate', title: meta }, meta),
    h('span', { className: 'dk-bar', role: 'progressbar', 'aria-label': `${run.spec} attempts`, 'aria-valuemin': 0, 'aria-valuemax': run.max_attempts, 'aria-valuenow': n },
      h('span', { style: { width: `${Math.round(100 * n / Math.max(1, run.max_attempts))}%` } })))
}

function DockClaimRow({ c }) {
  useTick(15000)
  const blocked = c.check && !c.check.ok
  const meta = `${c.profile} · ${c.chat}`
  const check = blocked ? blockedText(c.check) : 'passes'
  return h('button', { type: 'button', className: 'dk-row', title: `${c.spec} claimed by ${c.profile}`, 'data-testid': 'dock-claim', 'data-claim': c.id, onClick: () => navigate('rung', { rid: c.spec }) },
    h('span', 'dk-row-top',
      h('span', 'mono dk-id text-fg', c.spec),
      h('span', 'dk-chip', 'claimed'),
      h('span', 'dk-path mono', ago(c.opened_at))),
    h('span', { className: 'dk-meta mono truncate', title: meta }, meta),
    h('span', { className: 'dk-meta mono truncate', title: `check: ${check}` }, 'check: ',
      h('span', { className: blocked ? 'text-fail' : 'text-pass' }, check)))
}

function DockTree({ nodes, depth, cur }) {
  return h('ul', { className: cx('dk-tr', depth && 'dk-tr-sub'), role: depth ? 'group' : 'tree', 'aria-label': depth ? undefined : 'Ladder' },
    ...nodes.map(n => {
      const kids = n.kind === 'test' ? [] : liveKids(n)
      const t = tone(n)
      const label = rungLabel(n)
      return h('li', { key: n.id, role: 'treeitem', 'aria-expanded': kids.length ? 'true' : undefined },
        h('button', {
          type: 'button', className: cx('dk-tr-row', cur === n.id && 'dk-tr-cur'), title: `${n.id} ${n.text || ''}`.trim(),
          'data-rung': n.id, 'data-tone': t, 'data-label': label, onClick: () => navigate('rung', { rid: n.id })
        },
        h(Dot, { t }),
        h('span', { className: cx('mono dk-tr-id', cur === n.id ? 'text-needs' : t === 'dim' ? 'text-dim' : 'text-fg') }, n.id),
        n.kind !== 'test' && n.text ? h('span', { className: cx('dk-tr-text truncate', t === 'dim' && 'text-dim'), title: n.text }, n.text) : null,
        label ? h('span', { className: cx('dk-tr-label mono', TONE_TEXT[t] || 'text-muted') }, label) : null),
        kids.length ? h(DockTree, { nodes: kids, depth: (depth || 0) + 1, cur }) : null)
    }))
}

function DockProject({ project }) {
  const q = useApi(`/projects/${encodeURIComponent(project)}/home`, { live: true })
  const last = useValue($lastNeed)[project]
  const d = q.data
  if (!d) {
    return h('div', 'dk-body', q.error ? h(DockEmpty, { label: errText(q.error) }) : h(DockEmpty, { label: 'Loading' }))
  }
  const tree = (d.tree || []).filter(n => n.status !== 'dismissed')
  const items = d.needs_you || []
  const runs = d.running || []
  const claims = d.claims || []
  const ids = tree.map(n => n.id)
  const firstHot = items.map(i => needOf(tree, i.id)).find(Boolean)
  const need = (last && ids.includes(last) && last) || firstHot || ids[0]
  const node = tree.find(n => n.id === need)
  const hl = d.allocation && d.allocation.spec
  const pathOf = i => {
    const up = chainOf(tree, i.id, []) || []
    return (up.length > 2 ? [up[0], up[up.length - 1]] : up).join(' › ')
  }
  const n = d.tiles ? d.tiles.needs_you : items.length
  return h('div', 'dk-body',
    h(DockSection, { id: 'dk-needs', title: 'Needs you', count: n, tone: n ? 'needs' : 'dim' },
      items.length ? frag(...items.map(i => h(DockNeedRow, { key: i.type + i.id + (i.n || '') + (i.run || ''), i, path: pathOf(i) })))
        : h(DockEmpty, { label: 'Nothing needs you' })),
    h(DockSection, { id: 'dk-running', title: 'Running', count: runs.length + claims.length, tone: runs.length + claims.length ? 'needs' : 'dim' },
      runs.length + claims.length
        ? frag(...runs.map(r => h(DockRunRow, { key: 'r' + r.id, run: r })), ...claims.map(c => h(DockClaimRow, { key: 'c' + c.id, c })))
        : h(DockEmpty, { label: 'Nothing running' })),
    h(DockSection, { id: 'dk-ladder', title: 'Ladder', tone: 'dim' },
      tree.length
        ? frag(
          h('label', { className: 'sr-only', htmlFor: 'rung-dock-need' }, 'Need'),
          h('select', { id: 'rung-dock-need', className: 'dk-select', value: need, 'data-testid': 'dock-need', onChange: e => noteNeed(project, e.target.value) },
            ...tree.map(x => h('option', { key: x.id, value: x.id }, `${x.id}  ${x.text}`))),
          node ? h(DockTree, { nodes: liveKids(node), depth: 0, cur: hl }) : null)
        : h(DockEmpty, { label: 'No needs yet', action: 'Write the first need', onAction: () => navigate('need-new') })))
}

function Dock() {
  const st = useApi('/state').data
  const project = st && st.current
  return h(Root, { className: 'h-full w-full min-w-0 overflow-hidden' },
    h('div', { className: 'dk', 'data-testid': 'rung-dock' },
      st && project
        ? h('header', 'dk-head',
          h('span', { className: 'dk-project truncate', title: project, 'data-testid': 'dock-project' }, project),
          h('button', { type: 'button', className: 'dk-btn', 'aria-label': `Open Rung on ${project}`, 'data-testid': 'dock-open', onClick: () => navigate('home') }, 'Open Rung',
            h('svg', { viewBox: '0 0 16 16', 'aria-hidden': 'true' }, h('path', { d: 'M6 3h7v7M13 3 6 10M3 6v7h7' }))))
        : null,
      !st ? h('div', 'dk-body', h(DockEmpty, { label: 'Loading' }))
        : project ? h(DockProject, { project })
          : h('div', 'dk-body', h(DockEmpty, { label: 'No project', action: 'Open Rung', onAction: () => navigate('home') }))))
}

const DOCK_CSS = `
.rung .dk{height:100%;width:100%;max-width:100%;overflow:hidden;display:flex;flex-direction:column;background:var(--r-card);min-width:0;font-size:13px;line-height:1.4}
.rung .dk-head{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:12px 16px;border-bottom:1px solid var(--r-line)}
.rung .dk-project{font-size:14px;font-weight:600;letter-spacing:-0.01em;color:var(--r-fg)}
.rung .dk-body{flex:1;overflow-y:auto;padding:12px 12px 24px;display:flex;flex-direction:column;gap:24px;min-width:0}
.rung .dk-sec{display:flex;flex-direction:column;gap:8px;min-width:0}
.rung .dk-h{margin:0 4px;display:flex;align-items:center;gap:6px;font-size:11px;font-weight:600;letter-spacing:0.06em;text-transform:uppercase;color:var(--r-muted)}
.rung .dk-count{margin-left:auto;font-size:11px;letter-spacing:0;color:var(--r-muted)}
.rung .dk-row{box-sizing:border-box;width:100%;display:flex;flex-direction:column;align-items:stretch;text-align:left;gap:3px;padding:8px 10px;border:1px solid var(--r-line2);border-radius:6px;background:var(--r-btn);cursor:pointer;min-width:0;transition:background-color 140ms cubic-bezier(.16,1,.3,1)}
.rung .dk-row:hover{background:var(--r-btnh)}
.rung .dk-row:active{background:var(--r-line)}
.rung .dk-row-top{display:flex;align-items:center;gap:6px;min-width:0}
.rung .dk-id{font-size:12px;font-weight:600;flex:none}
.rung .dk-path{margin-left:auto;font-size:11px;color:var(--r-muted);flex:none;max-width:40%}
.rung .dk-text{font-size:12px;color:var(--r-fg2)}
.rung .dk-meta{font-size:11px;color:var(--r-muted)}
.rung .dk-chip{font-size:11px;line-height:16px;padding:0 5px;border-radius:4px;border:1px solid var(--r-line2);color:var(--r-muted);flex:none}
.rung .dk-bar{display:block;height:3px;margin-top:4px;border-radius:2px;background:var(--r-well);overflow:hidden}
.rung .dk-bar>span{display:block;height:100%;background:var(--r-needs);border-radius:2px}
.rung .dk-empty{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:9px 10px;border:1px solid var(--r-line);border-radius:6px;font-size:12px;color:var(--r-muted);min-width:0}
.rung .dk-btn{display:inline-flex;align-items:center;gap:5px;padding:3px 8px;font-size:12px;font-weight:500;color:var(--r-fg);border:1px solid var(--r-line2)!important;border-radius:4px;white-space:nowrap;flex:none}
.rung .dk-btn:hover{background:var(--r-btnh)}
.rung .dk-btn svg{width:12px;height:12px;fill:none;stroke:currentColor;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round}
.rung .dk-select{width:100%;max-width:100%;text-overflow:ellipsis;padding:6px 8px;font-size:12px;font-weight:500;color:var(--r-fg);background:var(--r-btn);border:1px solid var(--r-line2);border-radius:6px;min-width:0}
.rung .dk-tr{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:1px;min-width:0}
.rung .dk-tr-sub{margin-left:10px;padding-left:8px;border-left:1px solid var(--r-line2)}
.rung .dk-tr-row{box-sizing:border-box;width:100%;display:flex;align-items:center;gap:6px;padding:4px 6px;border-radius:4px;cursor:pointer;min-width:0;text-align:left}
.rung .dk-tr-row:hover{background:var(--r-btnh)}
.rung .dk-tr-cur{background:color-mix(in srgb, var(--r-needs) 8%, transparent)}
.rung .dk-tr-id{font-size:11px;font-weight:600;flex:none}
.rung .dk-tr-text{font-size:11px;color:var(--r-muted)}
.rung .dk-tr-label{margin-left:auto;font-size:11px;flex:none}
.rung .dk .truncate{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0}
.rung .dk-row:focus-visible,.rung .dk-btn:focus-visible,.rung .dk-select:focus-visible{outline-offset:1px!important}
.rung .dk-tr-row:focus-visible{outline-offset:-2px!important}
.rung [data-testid=main]{container-type:inline-size}
@container (max-width: 680px){.rung .rs-step:not(.rs-on) .rs-label{display:none}}
`

function setDock(open) {
  $dockOpen.set(!!open)
  try { localStorage.setItem(DOCK_KEY, JSON.stringify(!!open)) } catch (_) { /* private mode */ }
}

// Summon-only, like the Desktop's own logs pane: the pane exists while the dock is on, and the choice persists.
function bindDock(ctx) {
  let off = null
  const sync = open => {
    if (open && !off) {
      off = ctx.register({
        id: DOCK_PANE, area: PANES_AREA, title: 'Rung',
        data: {
          placement: 'right', collapsible: true, dock: { pane: 'workspace', pos: 'right' },
          width: '288px', minWidth: '237px', maxWidth: '360px', tabTitleText: () => 'Rung'
        },
        render: () => h(Dock)
      })
      try { host.revealPane && host.revealPane('rung:' + DOCK_PANE) } catch (_) { /* older desktops */ }
    } else if (!open && off) {
      off()
      off = null
    }
  }
  sync($dockOpen.get())
  const unsub = $dockOpen.listen(sync)
  ctx.onDispose(() => { unsub(); if (off) off() })
}
