// Rung desktop pane: router, status bar chip, registration.

function App() {
  const nav = useValue($nav)
  const { state, project, loading, error } = useCurrent()
  if (loading && !state) return h(Root, { className: 'h-full' }, h(Loading))
  if (error && !state) return h(Root, { className: 'h-full' }, h('div', 'p-8', h(ErrorLine, { text: 'Rung backend unavailable: ' + errText(error) })))
  if (state && state.settings && $colours.get() == null) $colours.set(state.settings.colours || {})
  let view = nav.view
  const noProjects = state && !(state.projects || []).length && !state.current
  if (noProjects) {
    // No project to open: the start screen until it is dismissed, then the new project form.
    const start = state.onboarding && state.onboarding.start
    if (!['project-new', 'projects'].includes(view) && !(view === 'start' && start)) view = start ? 'start' : state.archived ? 'projects' : 'project-new'
  }
  if (!project && !noProjects && !['projects', 'project-new', 'settings'].includes(view)) view = 'projects'
  const props = { ...nav, project, state }
  let body
  if (view === 'home') body = h(Home, { key: 'home:' + project, project })
  else if (view === 'start') body = h(StartScreen)
  else if (view === 'projects') body = h(Projects, { key: 'projects:' + (nav.tab || ''), tab: nav.tab })
  else if (view === 'project-new') body = h(NewProject)
  else if (view === 'settings') body = h(Settings, { project })
  else if (VIEWS[view]) body = h(VIEWS[view], { key: view + ':' + JSON.stringify(nav), ...props })
  else body = h(Home, { project })
  return h(Root, { className: 'relative h-full w-full' }, h('div', { className: 'h-full w-full', 'data-rung-view': view }, body), project ? h(DefectModal, { project }) : null)
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
      onClick: () => navigate('home')
    }, `Rung: ${n} needs you`))
}

export default {
  id: 'rung',
  name: 'Rung',
  register(ctx) {
    CTX = ctx
    const style = document.createElement('style')
    style.setAttribute('data-rung', 'css')
    style.textContent = RUNG_CSS + '\n@keyframes rung-pulse{50%{opacity:.5}}@keyframes rung-spin{to{transform:rotate(360deg)}}' +
      '\n.rung{color:var(--r-fg);font-family:var(--dt-font-sans, system-ui, sans-serif)}.rung *,.rung *::before,.rung *::after{box-sizing:border-box;border-color:var(--r-line)}' +
      '\n.rung button{font:inherit;background:none;border-style:solid;border-width:0;cursor:pointer;color:inherit}.rung input,.rung textarea,.rung select{font:inherit;color:inherit}' +
      '\n.rung h1,.rung h2,.rung h3,.rung p{margin:0}.rung table{border-spacing:0}.rung [data-locked="1"]{cursor:not-allowed}' +
      '\n.rung :focus-visible{outline:2px solid var(--r-needs)!important;outline-offset:2px}.rung ul{list-style:none;margin:0;padding:0}' +
      '\n.rung .sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}' +
      '\n@media (prefers-reduced-motion: reduce){.rung *,.rung *::before,.rung *::after{animation:none!important;transition:none!important;scroll-behavior:auto!important}}'
    document.head.appendChild(style)
    window.__rungNavigate = navigate
    ctx.onDispose(() => { delete window.__rungNavigate })
    ctx.onDispose(() => style.remove())
    ctx.registerMany([
      { id: 'page', area: ROUTES_AREA, data: { path: ROUTE }, render: () => h(App) },
      { id: 'nav', area: SIDEBAR_NAV_AREA, data: { path: ROUTE, label: 'Rung', codicon: 'list-ordered' } },
      { id: 'chip', area: STATUSBAR_AREAS.left, order: 140, render: () => h(StatusChip) }
    ])
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
