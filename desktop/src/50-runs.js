// Rung desktop pane: runs, attempts, executions, defects.

function Fact({ label, value, mono, tone, big, tile }) {
  if (tile) {
    return h('div', 'bg-card border border-line rounded-[6px] p-2.5 flex flex-col gap-0.5',
      h('span', 'text-[11px] text-muted', label),
      h('span', { className: cx('mono text-xs font-medium', tone ? TONE_TEXT[tone] : 'text-fg'), 'data-fact': label }, value))
  }
  if (big) {
    return h('div', 'bg-card border border-line rounded-[6px] p-3 flex flex-col justify-between',
      h('span', 'text-[11px] font-medium text-muted', label),
      h('span', { className: cx('text-sm font-semibold mt-1', mono && 'mono', tone ? TONE_TEXT[tone] : 'text-fg'), 'data-fact': label }, value))
  }
  return h('div', 'flex flex-col gap-1 bg-well p-2.5 rounded-[6px] border border-line2',
    h('span', 'text-[11px] text-muted', label),
    h('span', { className: cx('text-xs font-medium', mono && 'mono', tone ? TONE_TEXT[tone] : 'text-fg'), 'data-fact': label }, value))
}

function elapsed(from, to) {
  if (!from) return ''
  const s = Math.max(0, Math.round((to || Date.now() / 1000) - from))
  if (s < 60) return `${s}s`
  return `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, '0')}s`
}

// ------------------------------------------------------------------ run

const OUTCOME_WORD = { needs_input: 'needs input', no_change: 'no change', unknown: 'unknown', partial: 'partial', error: 'error' }

// pass and fail come from the tests; every other outcome is what the worker or the runner reported
function outcomeTone(st) {
  if (st === 'pass' || st === 'passed') return 'pass'
  if (st === 'fail' || st === 'failed') return 'fail'
  if (['running', 'queued', 'needs_input', 'partial', 'error'].includes(st)) return 'needs'
  return 'dim'
}

function attemptLine(a) {
  const ex = (a.executions || [])
  const failed = ex.filter(x => x.status === 'fail').map(x => x.test)
  const passed = ex.filter(x => x.status === 'pass').map(x => x.test)
  if (a.status === 'running') return `Attempt ${a.n} · running`
  const tests = a.status === 'pass' ? passed : failed.length ? failed : ex.map(x => x.test)
  const word = OUTCOME_WORD[a.status] || a.status
  const why = a.reason && a.status !== 'pass' && a.status !== 'fail' ? ' · ' + a.reason : ''
  return `Attempt ${a.n} · ${word}${tests.length ? ' · ' + [...new Set(tests)].join(', ') : ''}${why}${a.ended_at ? ' · ' + dur(a.ended_at - a.started_at) : ''}`
}

function RunView({ project, run }) {
  const q = useApi(`/runs/${run}`, { live: true })
  useTick(1000)
  const r = q.data
  const specQ = useRung(project, r && r.spec)
  const st = useApi('/settings').data
  const [err, setErr] = useState('')
  if (q.error || specQ.error) return h(Missing, { project, text: errText(q.error || specQ.error) })
  if (!r || !specQ.data) return h(Page, { project }, h(Loading))
  const spec = specQ.data
  const live = r.status === 'running' || r.status === 'queued'
  const atts = r.attempts || []
  const cur = atts[atts.length - 1]
  const budget = `${r.max_attempts} attempts · ${Math.round(r.timeout_s / 60)} min`
  const needId = spec.path[0] && spec.path[0].id
  const stop = async () => { const x = await post(`/runs/${r.id}/cancel`); setErr(x.ok ? '' : x.error) }
  if (!live) {
    const tone = outcomeTone(r.status)
    const reqText = (spec.path.find(p => p.id === r.requirement) || {}).text || ''
    const body = h(Card, { className: 'p-4 flex flex-col gap-4', testid: 'run' },
      h('div', 'flex flex-col gap-2',
        h(Crumbs, { path: spec.path, last: spec.id }),
        h('div', 'flex items-center justify-between',
          h('div', 'flex items-center gap-2.5',
            h('h2', 'text-sm font-semibold text-fg', 'Develop until green'),
            h(Badge, { status: r.status })),
          h('span', { className: 'text-xs mono text-muted', 'data-testid': 'run-time' }, `Finished in ${elapsed(r.started_at || r.created_at, r.ended_at)}`))),
      h('div', 'grid grid-cols-3 gap-4',
        ...[['Carried by', r.profile, null], ['Attempts', `${atts.length} of ${r.max_attempts}`, 'attempt-count'], ['Commit', r.commit || 'none', null]]
          .map(([label, value, testid]) => h('div', { key: label, className: 'p-3.5 rounded-[6px] bg-well border border-line' },
            h('div', 'text-xs text-muted mono mb-1', label),
            h('div', { className: 'text-sm font-semibold mono text-fg', 'data-testid': testid || undefined }, value)))),
      h('div', 'flex flex-col gap-2 pt-2 border-t border-line',
        h('h3', 'text-xs font-semibold uppercase tracking-wider text-muted', 'Attempts'),
        h('div', { className: 'flex flex-col gap-1.5 bg-well p-2.5 rounded-[6px] border border-line2 font-mono text-[11px]', 'data-testid': 'attempts' },
          ...atts.map(a => {
            const t = outcomeTone(a.status)
            return h('div', { key: a.n, className: 'flex items-center justify-between py-0.5 cursor-pointer', 'data-attempt': a.n, 'data-outcome': a.status, onClick: () => navigate('attempt', { run: r.id, n: a.n }) },
              h('div', { className: cx('flex items-center gap-2', TONE_TEXT[t]) }, h(Dot, { t }), h('span', null, attemptLine(a))),
              h('span', 'text-[10px] text-muted', 'Details'))
          }))),
      h('div', 'flex flex-col gap-2 pt-2 border-t border-line',
        h('h3', 'text-xs font-semibold uppercase tracking-wider text-muted', 'Coverage'),
        h('div', { className: 'flex items-center justify-between bg-well p-2.5 rounded-[6px] border border-line2', 'data-testid': 'run-coverage' },
          h('span', 'text-xs mono text-fg', `${r.requirement} ${reqText}`),
          h(Badge, { status: r.coverage === 'covered' ? 'covered' : r.coverage === 'failing' ? 'failing' : r.coverage === 'stale' ? 'stale' : 'open' }))),
      r.reason && r.status !== 'passed' ? h('div', { className: cx('text-xs', TONE_TEXT[tone === 'dim' ? 'muted' : tone]), 'data-testid': 'run-reason' }, r.reason) : null,
      h(ErrorLine, { text: err }),
      h('div', 'flex items-center gap-2 pt-2 border-t border-line',
        h(Btn, { kind: 'primary', testid: 'back-to-build', onClick: () => navigate('build', { need: needId, step: 'develop' }) }, 'Back to build'),
        h(Btn, { testid: 'open-spec', onClick: () => navigate('rung', { rid: spec.id }) }, 'Open specification'),
        r.status !== 'passed' ? h(Btn, { testid: 'run-again', disabled: !spec.develop.available, onClick: async () => { const x = await post(`${P(project)}/specs/${spec.id}/send`, {}); if (!x.ok) return setErr(x.error); navigate('run', { run: x.data.id }) } }, 'Run again') : null))
    return h(Page, { project, sel: spec.id }, body)
  }
  const out = cur ? String(cur.worker_output || '').split('\n').filter(Boolean).slice(-8) : []
  const body = h(Card, { className: 'p-4 flex flex-col gap-4', testid: 'run' },
    h('div', 'flex flex-col gap-2',
      h(Crumbs, { path: spec.path, last: spec.id }),
      h('div', 'flex items-center justify-between',
        h('div', 'flex items-center gap-2.5',
          h('span', { className: 'w-2 h-2 rounded-full bg-needs', style: { animation: 'rung-pulse 2s ease-in-out infinite' } }),
          h('h2', 'text-sm font-semibold text-fg', 'Develop until green')),
        h('span', { className: 'text-xs mono text-needs font-medium', 'data-testid': 'run-time' }, `Running ${elapsed(r.started_at || r.created_at)}`))),
    h('div', 'grid grid-cols-3 gap-3 bg-well p-2.5 rounded-[6px] border border-line2 text-xs',
      h('div', 'flex flex-col gap-0.5', h('span', 'text-[11px] text-muted', 'Carried by'), h('span', 'font-medium mono text-fg', r.profile)),
      h('div', 'flex flex-col gap-0.5', h('span', 'text-[11px] text-muted', 'Attempt'), h('span', { className: 'font-medium mono text-fg', 'data-testid': 'attempt-count' }, `${cur ? cur.n : 0} of ${r.max_attempts}`)),
      h('div', 'flex flex-col gap-0.5', h('span', 'text-[11px] text-muted', 'Budget'), h('span', 'font-medium mono text-fg', budget))),
    h('div', 'flex flex-col gap-2 pt-2 border-t border-line',
      h('h3', 'text-xs font-semibold uppercase tracking-wider text-muted', 'Attempts'),
      h('div', { className: 'flex flex-col gap-1.5 bg-well p-2.5 rounded-[6px] border border-line2 font-mono text-[11px]', 'data-testid': 'attempts' },
        ...(atts.length ? atts : [{ n: 1, status: 'running' }]).map(a => {
          const t = outcomeTone(a.status)
          return h('div', { key: a.n, className: 'flex items-center justify-between text-fg py-0.5 cursor-pointer', 'data-attempt': a.n, 'data-outcome': a.status, onClick: () => navigate('attempt', { run: r.id, n: a.n }) },
            h('div', 'flex items-center gap-2',
              h('span', { className: cx('w-1.5 h-1.5 rounded-full', TONE_BG[t]), style: t === 'needs' ? { animation: 'rung-pulse 2s ease-in-out infinite' } : undefined }),
              h('span', null, attemptLine(a))),
            h('span', { className: cx('text-[10px]', TONE_TEXT[t]) }, a.status === 'pass' ? 'passed' : a.status === 'fail' ? 'failed' : OUTCOME_WORD[a.status] || a.status))
        }))),
    h('div', 'flex flex-col gap-1.5 pt-2 border-t border-line',
      h('div', { className: 'bg-well p-3 rounded-[6px] border border-line2 font-mono text-xs text-fg flex flex-col gap-1.5', 'data-testid': 'live-output' },
        ...(out.length ? out : ['waiting for the worker']).map((l, i) => h('div', { key: i, className: 'flex items-center gap-2 text-muted' }, h('span', null, '>'), h('span', 'text-fg', l))))),
    h(ErrorLine, { text: err }),
    h('div', 'flex items-center gap-2 pt-2 border-t border-line',
      h('button', { type: 'button', className: 'px-3 py-1.5 rounded-[6px] bg-btn border border-fail text-fail font-medium text-xs', 'data-testid': 'stop', onClick: stop }, 'Cancel'),
      h(Btn, { testid: 'open-session', disabled: !r.session, onClick: () => host.navigate(`/${r.session}`) }, 'Open session')))
  return h(Page, { project, sel: spec.id }, body)
}

// ------------------------------------------------------------------ attempt

function AttemptView({ project, run, n }) {
  const q = useApi(`/runs/${run}`, { live: true })
  const r = q.data
  const specQ = useRung(project, r && r.spec)
  if (q.error || specQ.error) return h(Missing, { project, text: errText(q.error || specQ.error) })
  if (!r || !specQ.data) return h(Page, { project }, h(Loading))
  const spec = specQ.data
  const a = (r.attempts || []).find(x => String(x.n) === String(n))
  if (!a) return h(Missing, { project, text: `no attempt ${n} in run ${run}` })
  const next = (r.attempts || []).find(x => x.n === a.n + 1)
  const fails = (a.executions || []).filter(x => x.status === 'fail')
  const tone = outcomeTone(a.status) === 'dim' ? 'muted' : outcomeTone(a.status)
  const outText = (fails[0] || (a.executions || [])[0] || {}).output || ''
  const outLines = outText.split('\n').filter(Boolean).slice(-12)
  const body = h(Card, { className: 'p-4 flex flex-col gap-4', testid: 'attempt' },
    h('div', 'flex flex-col gap-1.5',
      h(Crumbs, { path: [...spec.path, { id: spec.id }], last: `Attempt ${a.n}` }),
      h('div', 'flex items-center justify-between mt-0.5',
        h('div', 'flex items-center gap-2.5',
          h('h2', 'text-base font-semibold text-fg', `Attempt ${a.n}`),
          h(Badge, { status: a.status === 'pass' ? 'pass' : a.status === 'fail' ? 'fail' : a.status })),
        h('span', 'text-xs mono text-muted', `${r.profile}${a.ended_at ? ' · ' + dur(a.ended_at - a.started_at) : ''}`)),
      a.reason ? h('div', { className: cx('text-xs', TONE_TEXT[tone]), 'data-testid': 'attempt-reason' }, a.reason) : null),
    h('div', 'flex flex-col gap-1.5 pt-3 border-t border-line',
      h('div', 'text-xs font-semibold uppercase tracking-wider text-muted', 'Files changed'),
      h('div', { className: 'flex flex-col gap-1 bg-well p-2.5 rounded-[6px] border border-line2 font-mono text-[11px]', 'data-testid': 'files-changed' },
        ...((a.files_changed || []).length ? a.files_changed.map(fc => h('div', { key: fc.path, className: 'flex items-center justify-between text-fg py-0.5' },
          h('span', null, fc.path),
          h('span', null, h('span', 'text-pass', `+${fc.added}`), ' ', h('span', 'text-fail', `-${fc.removed}`)))) : [h('span', { key: 'none', className: 'text-dim' }, 'No files changed')]))),
    h('div', 'flex flex-col gap-1.5 pt-3 border-t border-line',
      h('div', 'text-xs font-semibold uppercase tracking-wider text-muted', 'Commands'),
      ...(a.executions || []).map(x => h('div', { key: `${x.test}#${x.n}`, className: 'flex items-center justify-between bg-well px-2.5 py-1.5 rounded-[6px] border border-line2 font-mono text-[11px] cursor-pointer', onClick: () => navigate('exec', { test: x.test, n: x.n }) },
        h('span', 'text-fg', x.command),
        h('span', { className: cx('inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium border', x.status === 'pass' ? 'bg-pass/10 text-pass border-pass/30' : x.status === 'fail' ? 'bg-fail/10 text-fail border-fail/30' : 'bg-needs/10 text-needs border-needs/30') }, `exit ${x.exit_code == null ? x.status : x.exit_code}`)))),
    h('div', 'flex flex-col gap-1.5 pt-3 border-t border-line',
      h('div', 'text-xs font-semibold uppercase tracking-wider text-muted', 'Test output'),
      h('div', { className: cx('bg-well p-3 rounded-[6px] border border-line2 font-mono text-[11px] flex flex-col gap-1', TONE_TEXT[tone]), 'data-testid': 'test-output' },
        ...(outLines.length ? outLines : ['no output']).map((l, i) => h('div', { key: i, className: /FAILED|Error|assert/.test(l) ? '' : 'text-fg' }, l)))),
    a.status === 'fail' ? h('div', 'flex flex-col gap-1.5 pt-3 border-t border-line',
      h('div', 'text-xs font-semibold uppercase tracking-wider text-muted', next ? `Sent to attempt ${next.n}` : 'Sent forward'),
      h('div', { className: 'text-xs text-fg', 'data-testid': 'fed-forward' }, fails.length ? `Failure output of ${[...new Set(fails.map(x => x.test))].join(', ')}` : (a.fed_forward || '').split('\n')[0])) : null,
    h('div', 'flex items-center gap-2 pt-3 border-t border-line',
      h(Btn, { kind: 'primary', testid: 'back-to-run', onClick: () => navigate('run', { run: r.id }) }, 'Back to run'),
      h(Btn, { testid: 'open-session', disabled: !r.session, onClick: () => host.navigate(`/${r.session}`) }, 'Open session')))
  return h(Page, { project, sel: spec.id }, body)
}

// ------------------------------------------------------------------ execution

function OutputLines({ text, status }) {
  const lines = String(text || '').split('\n').filter(l => l.length)
  return lines.map((l, i) => {
    const bad = /FAILED|Error|assert|Traceback/.test(l)
    const summary = /\d+ (passed|failed)/.test(l)
    const cls = summary ? (/failed/.test(l) ? 'text-muted' : 'text-pass pt-1') : bad ? 'text-fail font-medium' : i === 0 ? 'text-muted' : 'text-fg'
    return h('div', { key: i, className: cls }, l)
  })
}

function ExecView({ project, test, n }) {
  const q = useApi(`${P(project)}/tests/${test}/executions/${n}`, { live: true })
  const tq = useRung(project, test)
  useTick(1000)
  const [err, setErr] = useState('')
  const x = q.data
  const t = tq.data
  if (q.error || tq.error) return h(Missing, { project, text: errText(q.error || tq.error) })
  if (!x || !t) return h(Page, { project, sel: test }, h(Loading))
  const voided = x.invalidated && x.status === 'pass'  // an upstream edit voids passes; fails stay failed
  const crumbs = h(Crumbs, { path: [...t.path, { id: t.id }], last: `#${x.n}`, lastTone: x.status === 'fail' ? 'text-fail' : 'text-needs' })
  const again = async () => {
    const r = await post(`${P(project)}/tests/${test}/run`)
    if (!r.ok) return setErr(r.error)
    navigate('exec', { test, n: r.data.n })
  }
  const back = () => navigate('rung', { rid: test })
  if (x.status === 'running') {
    const lines = String(x.output || '').split('\n').filter(Boolean)
    const body = h('section', { className: 'flex flex-col gap-4 bg-card border border-line rounded-[6px] p-4', 'data-testid': 'execution', 'data-exec-status': 'running' },
      h('div', 'flex flex-col gap-2 pb-3 border-b border-line', crumbs,
        h('div', 'flex items-center justify-between',
          h('div', 'flex items-center gap-3',
            h('div', 'flex items-center gap-2',
              h('span', { className: 'w-2 h-2 rounded-full bg-needs', style: { animation: 'rung-pulse 2s ease-in-out infinite' } }),
              h('h2', 'text-base font-bold text-fg', `Execution #${x.n}`)),
            h('span', 'inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-needs/10 text-needs border border-needs/30', `Running ${elapsed(x.started_at)}`)),
          h('button', { type: 'button', className: 'px-3 py-1 rounded-[6px] border border-fail text-fail text-xs font-medium', 'data-testid': 'cancel', onClick: async () => { const r = await post(`${P(project)}/tests/${test}/executions/${x.n}/cancel`); setErr(r.ok ? '' : r.error) } }, 'Cancel'))),
      h('div', 'grid grid-cols-4 gap-3 py-1',
        h(Fact, { label: 'Commit', value: x.commit || 'none', mono: true }),
        h(Fact, { label: 'Carried by', value: x.carried_by || 'engine', mono: true }),
        h(Fact, { label: 'Context', value: x.context || '' }),
        h(Fact, { label: 'Timeout', value: `${x.timeout || 120}s`, mono: true })),
      h('div', 'flex flex-col gap-2 pt-2',
        h('div', 'flex items-center justify-between text-[11px] text-muted',
          h('span', 'font-medium uppercase tracking-wider text-[10px]', 'Live Output'),
          h('span', 'mono text-needs', 'streaming')),
        h('div', { className: 'bg-well p-3 rounded-[6px] border border-line2 font-mono text-[11px] text-fg flex flex-col gap-1 min-h-[180px]', 'data-testid': 'output' },
          ...lines.slice(-30).map((l, i) => h('div', { key: i }, l)),
          h('span', { className: 'inline-block w-1.5 h-3.5 bg-needs ml-0.5', style: { animation: 'rung-pulse 1s steps(2) infinite' } }))),
      h(ErrorLine, { text: err }))
    return h(Page, { project, sel: test }, body)
  }
  const pass = x.status === 'pass'
  const facts = big => [
    h(Fact, { key: 'c', big, label: 'Commit', value: x.commit || 'none', mono: true }),
    h(Fact, { key: 'b', big, label: 'Carried by', value: x.carried_by || 'engine' }),
    h(Fact, { key: 'd', big, label: 'Duration', value: x.duration != null ? dur(x.duration) : '' }),
    h(Fact, { key: 's', big, label: 'Started', value: clock(x.started_at) }),
    h(Fact, { key: 'e', big, label: 'Exit code', value: x.exit_code == null ? 'none' : String(x.exit_code), mono: true, tone: pass ? 'pass' : x.status === 'fail' ? 'fail' : x.exit_code == null ? undefined : 'needs' }),
    h(Fact, { key: 'x', big, label: 'Context', value: x.context || '' })
  ]
  if (voided) {
    // exec-3: an old result that no longer counts
    const body = h('div', { className: 'flex flex-col gap-4', 'data-testid': 'execution', 'data-exec-status': x.status },
      h('div', 'flex flex-col gap-2', crumbs,
        h('div', 'flex items-center justify-between',
          h('div', 'flex items-center gap-2.5',
            h('h2', 'text-lg font-bold text-fg', `Execution #${x.n}`),
            h(Badge, { status: x.status, struck: true, testid: 'voided-result' }), h(Badge, { status: 'stale' })),
          h('div', 'flex items-center gap-2',
            h(Btn, { kind: 'primary', testid: 'run-again', onClick: again }, 'Run again'),
            h(Btn, { testid: 'back-to-test', onClick: back }, 'Back to test')))),
      h('div', { className: 'flex items-center gap-2 px-3 py-2 rounded-[6px] bg-stale/15 border border-stale/30 text-xs text-stale', 'data-testid': 'no-longer-counts' },
        h('span', 'w-1.5 h-1.5 rounded-full bg-stale'), `No longer counts · ${x.invalidated_by || 'an upstream rung edited'} after this run`),
      h('div', 'grid grid-cols-3 gap-2.5', ...facts(false).map(f => h(Fact, { ...f.props, key: f.key, tile: true }))),
      h('div', 'flex flex-col gap-1.5',
        h('span', 'text-[11px] font-semibold uppercase tracking-wider text-muted', 'Output log'),
        h('div', { className: 'bg-well border border-line2 rounded-[6px] p-3 font-mono text-xs flex flex-col gap-1 leading-relaxed text-muted', 'data-testid': 'output' }, ...OutputLines({ text: x.output }))),
      h(ErrorLine, { text: err }))
    return h(Page, { project, sel: test }, body)
  }
  if (pass && x.counts) {
    // exec-4: a pass that counts
    const reqText = (t.path.find(p => p.id === x.requirement) || {}).text || ''
    const body = h('div', { className: 'flex flex-col gap-5', 'data-testid': 'execution', 'data-exec-status': x.status },
      h('div', 'flex items-center justify-between', crumbs,
        h('div', 'flex items-center gap-3',
          h(Btn, { testid: 'open-spec', onClick: () => navigate('rung', { rid: x.spec }) }, 'Open specification'),
          h(Btn, { kind: 'primary', testid: 'back-to-test', onClick: back }, 'Back to test'))),
      h(Card, { className: 'p-5 flex items-center justify-between' },
        h('div', 'flex items-center gap-3',
          h('h2', 'text-xl font-bold text-fg tracking-tight', `Execution #${x.n}`),
          h(Badge, { status: 'pass' }),
          h('span', { className: 'px-2.5 py-0.5 rounded text-xs font-semibold bg-pass/10 text-pass', 'data-testid': 'counts' }, 'Counts'))),
      h('div', { className: cx('rounded-[6px] px-4 py-3 flex items-center gap-3 text-xs font-medium border', x.coverage === 'covered' ? 'bg-pass/10 border-pass/30 text-pass' : 'bg-well border-line2 text-muted'), 'data-testid': 'exec-coverage' },
        h('span', { className: cx('w-2 h-2 rounded-full shrink-0', x.coverage === 'covered' ? 'bg-pass' : 'bg-dim') }),
        `${x.requirement} ${reqText} · ${BADGE[x.coverage] ? BADGE[x.coverage][0] : x.coverage}`),
      h('div', 'grid grid-cols-12 gap-5 min-h-[300px]',
        h('div', 'col-span-5 bg-card border border-line rounded-[6px] p-4 flex flex-col justify-between',
          h('div', 'grid grid-cols-2 gap-3', ...facts(false)),
          h('div', 'mt-4 pt-3 border-t border-line text-[11px] text-dim font-mono', x.command || '')),
        h('div', 'col-span-7 bg-well border border-line rounded-[6px] flex flex-col overflow-hidden',
          h('div', 'px-4 py-2.5 border-b border-line bg-card flex items-center justify-between',
            h('span', 'text-xs font-mono text-muted', 'OUTPUT LOG'),
            h('span', 'text-[10px] font-mono text-pass', `exit ${x.exit_code}`)),
          h('div', { className: 'p-4 font-mono text-xs flex flex-col gap-1.5 text-muted', 'data-testid': 'output' }, ...OutputLines({ text: x.output })))),
      h(ErrorLine, { text: err }))
    return h(Page, { project, sel: test }, body)
  }
  // exec-1: a failed (or cancelled, or pending) execution
  const body = h('div', { className: 'flex flex-col gap-4', 'data-testid': 'execution', 'data-exec-status': x.status },
    h('div', 'flex flex-col gap-2 bg-card border border-line rounded-[6px] p-4',
      h('div', 'flex items-center justify-between', crumbs, h(Badge, { status: x.status })),
      h('div', 'flex items-center justify-between pt-1',
        h('div', 'text-base font-bold text-fg', `Execution #${x.n}`),
        h('div', 'flex items-center gap-2',
          t.type === 'manual' ? null : h(Btn, { kind: 'primary', testid: 'run-again', onClick: again }, 'Run again'),
          x.status === 'fail' ? h(Btn, { testid: 'raise-defect', onClick: () => openDefect(test, [x.n]) }, 'Raise defect') : null,
          h(Btn, { testid: 'back-to-test', onClick: back }, 'Back to test')))),
    h('div', 'grid grid-cols-3 gap-2.5', ...facts(true)),
    h('div', 'bg-card border border-line rounded-[6px] p-4 flex flex-col gap-2.5',
      h('div', 'text-[11px] font-semibold tracking-wider text-muted uppercase', 'OUTPUT LOG'),
      h('div', { className: 'bg-well border border-line2 rounded-[6px] p-3 flex flex-col gap-1 font-mono text-xs leading-relaxed', 'data-testid': 'output' }, ...OutputLines({ text: x.output || x.note || '' }))),
    h(ErrorLine, { text: err }))
  return h(Page, { project, sel: test }, body)
}

// ------------------------------------------------------------------ defect

const $defect = atom(null)

function openDefect(test, preselect) {
  $defect.set({ test, preselect: preselect || null })
}

ON_LEAVE.push(() => { if ($defect.get()) $defect.set(null) })

function DefectModal({ project }) {
  const d = useValue($defect)
  const tq = useRung(project, d && d.test)
  const [title, setTitle] = useState('')
  const [picked, setPicked] = useState(null)
  const [cat, setCat] = useState('Implementation')
  const [err, setErr] = useState('')
  const [done, setDone] = useState(null)
  useEffect(() => { setTitle(''); setPicked(null); setErr(''); setDone(null) }, [d && d.test])
  useDirty(d && title.trim())
  if (!d) return null
  const t = tq.data
  const fails = t ? (t.executions || []).filter(x => x.status === 'fail') : []
  const sel = picked || new Set(d.preselect || fails.map(x => x.n))
  const toggle = n => { const s = new Set(sel); if (s.has(n)) s.delete(n); else s.add(n); setPicked(s) }
  // Closing returns to the page that opened the dialog: the Raise defect route stands on Home.
  const close = () => { $defect.set(null); if ($nav.get().view === 'defect-new') navigate('home', null, { force: true, replace: true }) }
  const raise = async () => {
    const x = await post(`${P(project)}/tests/${d.test}/defects`, { title, executions: [...sel], category: cat })
    if (!x.ok) return setErr(x.error)
    setDone(x.data)
    close()
  }
  const ready = title.trim() && sel.size
  return h(Dialog, {
    title: 'Raise defect', onClose: close, testid: 'defect-modal',
    footer: frag(
      h('button', { type: 'button', className: 'px-3.5 py-1.5 rounded-[6px] bg-btn border border-line text-fg text-xs font-medium', onClick: close }, 'Cancel'),
      h('button', { type: 'button', 'aria-disabled': ready ? undefined : 'true', className: cx('px-3.5 py-1.5 rounded-[6px] bg-needs text-on-needs font-semibold text-xs', !ready && 'opacity-40 cursor-not-allowed'), 'data-testid': 'raise', onClick: () => ready && raise() }, 'Raise'))
  },
        h('div', 'flex flex-col gap-1.5',
          h('label', 'text-[11px] font-semibold text-muted uppercase tracking-wider', 'Title'),
          h('input', { className: 'w-full bg-well border border-line rounded-[6px] px-3 py-2 text-xs text-fg focus:border-needs', type: 'text', name: 'defect-title', value: title, 'data-autofocus': '1', onChange: e => setTitle(e.target.value) })),
        h('div', 'flex flex-col gap-1.5',
          h('label', 'text-[11px] font-semibold text-muted uppercase tracking-wider', 'Linked executions'),
          h('div', { className: 'flex flex-col gap-1.5 bg-well border border-line rounded-[6px] p-2.5 font-mono text-[11px]', 'data-testid': 'linked' },
            ...fails.map(x => h('label', { key: x.n, className: 'flex items-center gap-2.5 text-fg cursor-pointer' },
              h('input', { type: 'checkbox', className: 'accent-needs rounded', checked: sel.has(x.n), 'data-exec': x.n, onChange: () => toggle(x.n) }),
              h('span', 'flex items-center gap-2', h('span', 'w-1.5 h-1.5 rounded-full bg-fail'), `#${x.n} fail${x.commit ? ' · ' + x.commit : ''}`))))),
        h('div', 'flex flex-col gap-1.5',
          h('label', 'text-[11px] font-semibold text-muted uppercase tracking-wider', 'Category'),
          h('div', 'relative',
            h('select', { className: 'w-full bg-well border border-line rounded-[6px] px-3 py-2 text-xs text-fg focus:border-needs appearance-none cursor-pointer', name: 'category', value: cat, onChange: e => setCat(e.target.value) },
              ...['Implementation', 'Specification', 'Requirement', 'Test'].map(c => h('option', { key: c, value: c }, c))),
            h('div', 'pointer-events-none absolute inset-y-0 right-0 flex items-center px-3 text-muted', '▾'))),
        h(ErrorLine, { text: err }))
}

function DefectNew({ project, test }) {
  useEffect(() => { openDefect(test) }, [test])
  return h(Home, { project })
}

Object.assign(VIEWS, {
  'need-new': NeedNew,
  build: Build,
  rung: RungView,
  'req-new': ReqNew,
  change: ChangeView,
  'spec-edit': SpecEdit,
  'test-edit': TestEdit,
  run: RunView,
  attempt: AttemptView,
  exec: ExecView,
  'defect-new': DefectNew
})
