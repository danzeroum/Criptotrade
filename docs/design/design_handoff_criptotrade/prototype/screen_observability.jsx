/* ============================================================
   Criptotrade — Screen: Observabilidade / Process  (#observability)
   Event log do orquestrador — GET /v1/process/events (XES)
   agent_cycle_started / completed / failed
   ============================================================ */
const { useState: _useObs } = React;

const AGENT_DOT = {
  completed: 'var(--ink-3)',
  failed: 'var(--down)',
  skipped: 'var(--border-2)',
};

function PipelineBar({ agents, maxDur }) {
  return (
    <div style={{ display: 'flex', gap: 2, alignItems: 'stretch', height: 16, width: 200 }}>
      {agents.map(a => {
        const w = a.status === 'skipped' ? 8 : Math.max(6, a.duration_ms / maxDur * 180);
        return (
          <div key={a.id} title={`${a.name} · ${a.status} · ${a.duration_ms}ms`}
            style={{
              width: w, borderRadius: 3,
              background: a.status === 'failed' ? 'var(--down)' : a.status === 'skipped' ? 'var(--surface-3)' : 'var(--ink-3)',
              border: a.status === 'skipped' ? '1px dashed var(--border-2)' : 'none',
              opacity: a.status === 'completed' ? 0.55 : 1,
            }} />
        );
      })}
    </div>
  );
}

function CycleRow({ ev, maxDur, open, onToggle, latest }) {
  const ok = ev.status === 'completed';
  return (
    <>
      <tr data-tip="Clique para expandir os passos deste ciclo (strategy → risk → HITL → execução)." style={{ cursor: 'pointer', background: open ? 'var(--surface-2)' : undefined }} onClick={onToggle}>
        <td>
          <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {latest && <span style={{ width: 7, height: 7, borderRadius: 99, background: 'var(--up)', boxShadow: '0 0 0 3px var(--up-bg)' }} />}
            <span className="mono" style={{ fontWeight: 600 }}>#{ev.cycle}</span>
          </span>
        </td>
        <td className="mono" style={{ fontSize: 12, color: 'var(--ink-2)' }}>{ev.started_at}</td>
        <td className="num">{ev.duration_ms} ms</td>
        <td><PipelineBar agents={ev.agents} maxDur={maxDur} /></td>
        <td className="num">{ev.signals}</td>
        <td className="num">{ev.orders}</td>
        <td><Badge kind={ok ? 'ok' : 'down'} dot>{ok ? 'completo' : 'falhou'}</Badge></td>
        <td><Icon name={open ? 'chevronDown' : 'chevron'} size={15} style={{ color: 'var(--ink-4)' }} /></td>
      </tr>
      {open && (
        <tr>
          <td colSpan={8} style={{ background: 'var(--surface-2)', padding: '4px 14px 16px' }}>
            <div className="grid" style={{ gridTemplateColumns: '1fr 280px', gap: 18, paddingTop: 8 }}>
              <div>
                <div className="label-xs" style={{ marginBottom: 10 }}>Agentes do ciclo · duração por estágio</div>
                {ev.agents.map(a => (
                  <div key={a.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '5px 0' }}>
                    <span style={{ width: 7, height: 7, borderRadius: 99, background: AGENT_DOT[a.status], flexShrink: 0 }} />
                    <span style={{ fontSize: 12.5, width: 110 }}>{a.name}</span>
                    <div style={{ flex: 1 }}><Meter value={a.status === 'skipped' ? 0 : a.duration_ms} max={maxDur} color={a.status === 'failed' ? 'var(--down)' : 'var(--ink-3)'} height={6} /></div>
                    <span className="mono" style={{ fontSize: 11.5, width: 66, textAlign: 'right', color: 'var(--ink-2)' }}>
                      {a.status === 'skipped' ? 'pulado' : a.duration_ms + ' ms'}
                    </span>
                  </div>
                ))}
              </div>
              <div>
                <div className="label-xs" style={{ marginBottom: 10 }}>Resultado do ciclo</div>
                <StatRow k="Regime detectado" v={<Badge kind="info">{ev.regime === 'strong_uptrend' ? 'Alta forte' : 'Lateral'}</Badge>} />
                <StatRow k="Sinais gerados" v={ev.signals} />
                <StatRow k="Ordens criadas" v={ev.orders} />
                <StatRow k="Duração total" v={ev.duration_ms + ' ms'} />
                {ev.error && (
                  <div className="card card-pad" style={{ marginTop: 10, borderLeft: '3px solid var(--down)', fontSize: 12, lineHeight: 1.45, display: 'flex', gap: 8 }}>
                    <Icon name="warn" size={15} style={{ color: 'var(--down)', flexShrink: 0 }} />
                    <span>{ev.error}</span>
                  </div>
                )}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function ObservabilityScreen() {
  const [openId, setOpenId] = _useObs(null);
  const [state, setState] = _useObs('ok');
  const ev = CT.processEvents;
  const sum = CT.processSummary;
  const maxDur = Math.max(...ev.map(e => e.duration_ms));

  return (
    <div className="content-inner screen-enter">
      <div className="page-head">
        <div>
          <div className="page-title">Observabilidade</div>
          <div className="page-sub">Event log do orquestrador (XES) · ciclos do loop · GET /v1/process/events</div>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <span className="chip">
            <span style={{ width: 6, height: 6, borderRadius: 99, background: sum.loopRunning ? 'var(--up)' : 'var(--down)' }} />
            {sum.loopRunning ? 'loop rodando' : 'loop parado'}
          </span>
          <span className="chip"><Icon name="refresh" size={13} />ciclo a cada {sum.intervalS}s</span>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid" style={{ gridTemplateColumns: 'repeat(4,1fr)', marginBottom: 16 }}>
        <KPI label="Ciclos hoje" value={sum.cyclesToday} icon="refresh" sub={`último às ${sum.lastCycleAt}`} />
        <KPI label="Taxa de sucesso" value={fmtPct(sum.successRate * 100, 1)} icon="check" accent={sum.successRate > 0.9 ? 'var(--up)' : 'var(--warn)'} sub={`${ev.length} ciclos recentes`} />
        <KPI label="Duração média" value={sum.avgDurationMs + ' ms'} icon="clock" sub="por ciclo completo" />
        <KPI label="Falhas" value={sum.failures} icon="warn" accent={sum.failures ? 'var(--down)' : 'var(--ink)'} sub="nos ciclos recentes" />
      </div>

      {/* state preview (UX P0 — estados honestos) */}
      <div className="card card-pad" style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16, padding: '11px 16px' }}>
        <Icon name="info" size={15} style={{ color: 'var(--ink-3)' }} />
        <span className="label-xs">Pré-visualizar estado</span>
        <Seg value={state} onChange={setState} tip="Demonstra como a tela responde a cada estado de dados: normal, carregando, vazio e backend offline."
          options={[{ value: 'ok', label: 'OK' }, { value: 'loading', label: 'Carregando' }, { value: 'empty', label: 'Vazio' }, { value: 'error', label: 'Offline' }]} />
      </div>

      <div className="card">
        <CardHead icon="pulse" title="Ciclos do orquestrador" sub={`${ev.length} eventos recentes`} />
        {state === 'loading' && <LoadingState min={300} />}
        {state === 'empty' && <EmptyState min={300} message="Sem ciclos registrados" hint="O loop ainda não emitiu eventos de processo." />}
        {state === 'error' && <ErrorState min={300} onRetry={() => setState('ok')} />}
        {state === 'ok' && (
          <table className="tbl">
            <thead>
              <tr>
                <th>Ciclo</th><th>Início</th><th className="th-num">Duração</th><th>Pipeline</th>
                <th className="th-num">Sinais</th><th className="th-num">Ordens</th><th>Status</th><th></th>
              </tr>
            </thead>
            <tbody>
              {ev.map((e, i) => (
                <CycleRow key={e.cycle} ev={e} maxDur={maxDur} latest={i === 0}
                  open={openId === e.cycle} onToggle={() => setOpenId(openId === e.cycle ? null : e.cycle)} />
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* pipeline legend */}
      <div style={{ display: 'flex', gap: 16, marginTop: 12, fontSize: 11, color: 'var(--ink-3)' }}>
        <span style={{ display: 'flex', gap: 5, alignItems: 'center' }}><span style={{ width: 10, height: 10, borderRadius: 3, background: 'var(--ink-3)', opacity: .55 }} />completo</span>
        <span style={{ display: 'flex', gap: 5, alignItems: 'center' }}><span style={{ width: 10, height: 10, borderRadius: 3, background: 'var(--down)' }} />falhou</span>
        <span style={{ display: 'flex', gap: 5, alignItems: 'center' }}><span style={{ width: 10, height: 10, borderRadius: 3, background: 'var(--surface-3)', border: '1px dashed var(--border-2)' }} />pulado</span>
        <span className="muted" style={{ marginLeft: 'auto' }}>Largura ∝ duração do estágio · clique para detalhar o ciclo</span>
      </div>
    </div>
  );
}

window.ObservabilityScreen = ObservabilityScreen;
