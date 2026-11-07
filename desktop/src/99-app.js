// Rung desktop pane: router, status bar chip, registration.

function App() {
  const nav = useValue($nav)
  const { state, project, loading, error } = useCurrent()
  if (loading && !state) return h(Root, { className: 'h-full' }, h(Loading))
  if (error && !state) return h(Root, { className: 'h-full' }, h('div', 'p-8 flex flex-col gap-3', h(ErrorLine, { text: 'Rung backend unavailable: ' + errText(error) }), h('div', null, h(Btn, { testid: 'retry', onClick: () => refresh() }, 'Retry'))))
  if (state && state.settings && $colours.get() == null) $colours.set(state.settings.colours || {})
  let view = nav.view
  const noProjects = state && !(state.projects || []).length && !state.current
  if (noProjects) {
    // No project to open: the start screen until it is dismissed, then the new project form.
    const start = state.onboarding && state.onboarding.start
    if (!['project-new', 'projects', 'start'].includes(view)) view = start ? 'start' : state.archived ? 'projects' : 'project-new'
  }
  if (!project && !noProjects && !['projects', 'project-new', 'settings'].includes(view)) view = 'projects'
  CUR_PROJECT = project || null
  const props = { ...nav, project, state }
  let body
  if (view === 'home') body = h(Home, { key: 'home:' + project, project })
  else if (view === 'start') body = h(StartScreen)
  else if (view === 'projects') body = h(Projects, { key: 'projects:' + (nav.tab || ''), tab: nav.tab })
  else if (view === 'project-new') body = h(NewProject)
  else if (view === 'settings') body = h(Settings, { project })
  else if (VIEWS[view]) body = h(VIEWS[view], { key: view + ':' + JSON.stringify(nav), ...props })
  else body = h(Missing, { project, text: 'Page not found' })
  return h(Root, { className: 'relative h-full w-full' },
    h(ViewFocus, { nav }),
    h('div', { className: 'h-full w-full', 'data-rung-view': view }, body),
    project ? h(DefectModal, { project }) : null,
    h(LeaveDialog))
}

// After a view change, focus goes to the new view: its first field when it puts one in focus, else its title.
function ViewFocus({ nav }) {
  const [entered, setEntered] = useState(0)
  useEffect(() => {
    const on = () => { if (String(location.hash || '').includes(ROUTE)) setEntered(x => x + 1) }
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  useEffect(() => {
    let tries = 0
    let id = 0
    const go = () => {
      const root = document.querySelector('.rung [data-rung-view]')
      if (!root || !String(location.hash || '').includes(ROUTE)) return
      const a = document.activeElement
      if (a && a !== document.body && root.contains(a)) return
      if (document.querySelector('.rung [role=dialog]')) return
      const t = root.querySelector('[data-page-title]') || root.querySelector('h1')
      if (t) { if (!t.hasAttribute('tabindex')) t.setAttribute('tabindex', '-1'); t.focus({ preventScroll: true }); return }
      if (++tries < 30) id = setTimeout(go, 100)  // the view is still loading: its title comes with its data
    }
    id = setTimeout(go, 60)
    return () => clearTimeout(id)
  }, [nav, entered])
  return null
}

function StatusChip() {
  const st = useApi('/state').data
  if (!st || !st.current) return null
  const n = st.needs_you || 0
  return h(Root, { className: 'inline-flex' },
    h('button', {
      type: 'button',
      className: cx('px-1.5 text-[11px] mono font-medium', n ? 'text-needs' : 'text-muted'),
      'data-testid': 'rung-status-chip',
      'aria-live': 'polite',
      onClick: () => openRung('home')
    }, `Rung: ${n} needs you`))
}

export default {
  id: 'rung',
  name: 'Rung',
  register(ctx) {
    CTX = ctx
    const style = document.createElement('style')
    style.setAttribute('data-rung', 'css')
    style.textContent = RUNG_CSS + DOCK_CSS + '\n@keyframes rung-pulse{50%{opacity:.5}}@keyframes rung-spin{to{transform:rotate(360deg)}}' +
      '\n.rung{color:var(--r-fg);font-family:var(--dt-font-sans, system-ui, sans-serif)}.rung *,.rung *::before,.rung *::after{box-sizing:border-box;border-color:var(--r-line)}' +
      '\n.rung button{font:inherit;background:none;border-style:solid;border-width:0;cursor:pointer;color:inherit}.rung input,.rung textarea,.rung select{font:inherit;color:inherit}' +
      '\n.rung h1,.rung h2,.rung h3,.rung p{margin:0}.rung table{border-spacing:0}.rung [data-locked="1"]{cursor:not-allowed}' +
      '\n.rung{overflow-wrap:anywhere}.rung :focus-visible{outline:2px solid var(--r-needs)!important;outline-offset:2px}.rung ul{list-style:none;margin:0;padding:0}' +
      // A long Needs you list keeps every card (the count is the list) but skips layout and paint off screen.
      '\n.rung .r-ny{content-visibility:auto;contain-intrinsic-size:auto 96px}' +
      // the front page: the list first, the projects beside it, below it when the pane is narrow (NAV-14)
      '\n.rung .r-col-main{flex:999 1 420px;min-width:0}.rung .r-side{flex:1 1 260px;min-width:0;max-width:100%}' +
      // every control is at least 24 by 24 CSS pixels (WCAG 2.5.8)
      '\n.rung button,.rung [role=button],.rung [role=switch],.rung select{min-height:24px;min-width:24px}' +
      '\n.rung .sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}' +
      '\n@media (prefers-reduced-motion: reduce){.rung *,.rung *::before,.rung *::after{animation:none!important;transition:none!important;scroll-behavior:auto!important}}'
    document.head.appendChild(style)
    window.__rungNavigate = (v, p) => openRung(v, p, { force: true })  // tests: open a view, moving the app
    document.addEventListener('keydown', onEscape)
    window.addEventListener('hashchange', onHashChange)
    if (window.navigation) window.navigation.addEventListener('navigate', onNavigate)
    ctx.onDispose(() => {
      document.removeEventListener('keydown', onEscape)
      window.removeEventListener('hashchange', onHashChange)
      if (window.navigation) window.navigation.removeEventListener('navigate', onNavigate)
    })
    window.__rungView = navigate      // tests: change the view as an in-page action does
    window.__rungDock = setDock
    window.__rungRest = rest
    ctx.onDispose(() => { delete window.__rungNavigate; delete window.__rungView; delete window.__rungDock })
    ctx.onDispose(() => style.remove())
    ctx.registerMany([
      { id: 'page', area: ROUTES_AREA, data: { path: ROUTE }, render: () => h(App) },
      { id: 'nav', area: SIDEBAR_NAV_AREA, data: { path: ROUTE, label: 'Rung', codicon: 'list-ordered' } },
      { id: 'chip', area: STATUSBAR_AREAS.left, order: 140, render: () => h(StatusChip) },
      { id: 'dock-toggle', area: PALETTE_AREA, data: { label: 'Rung dock', keywords: ['rung', 'dock', 'ladder'], detail: () => ($dockOpen.get() ? 'on' : 'off'), detailVariant: 'state', run: () => setDock(!$dockOpen.get()) } }
    ])
    bindDock(ctx)
    let last = -1
    const tick = async () => {
      try {
        const r = await ctx.rest('/rev')
        if (r && r.rev !== last) {
          last = r.rev
          $rev.set(r.rev)
          refresh()
        }
      } catch (_) { /* backend restarting */ }
    }
    ctx.setInterval(tick, 1500)
    ctx.onEvent('plugin.rung.changed', () => refresh())
    tick()
  }
}
