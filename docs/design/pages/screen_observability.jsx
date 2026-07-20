/* ============================================================
   Criptotrade — Screen: Observabilidade / Process
   Event log XES real (GET /v1/process/events) agrupado por case_id.
   Mostra o heartbeat do loop do orquestrador (ciclos: started →
   completed/failed) e KPIs derivados dos eventos. N6: dimensão de
   símbolo (filtro + duração por símbolo). Mock leve para a demo.
   ============================================================ */
const { useState, useEffect } = React;

function _ago(iso) {
  if (!iso) return '—';
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return `${Math.round(s)}s atrás`;
  if (s < 3600) return `${Math.round(s / 60)}min atrás`;
  if (s < 86400) return `${Math.round(s / 3600)}h atrás`;
  return `${Math.round(s / 86400)}d atrás`;
}

const TRACE_STATUS = { completed: 'ok', failed: 'down', running: 'warn' };
const TRACE_LABEL = { completed: 'Concluído', failed: 'Falhou', running: 'Em curso' };

function ScreenObservability() {
  const [events, setEvents] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [symbolF, setSymbolF] = useState('all');  // N6: filter cycles by symbol

  const load = () => {
    setLoading(true);
    setError(null);
    CT_API.getProcessEvents(400)
      .then(d => { setEvents(Array.isArray(d) ? d : []); setLoading(false); })
      .catch(e => { setError(e); setLoading(false); });
  };

  useEffect(() => { load(); }, []);

  // Group events into traces (one case_id = one cycle or one order flow).
  const traces = {};
  for (const ev of events ?? []) (traces[ev.case_id] ||= []).push(ev);
  const rows = Object.entries(traces).map(([caseId, evs]) => {
    evs.sort((a, b) => (a.timestamp < b.timestamp ? -1 : 1));
    const started = evs.find(e => e.activity === 'agent_cycle_started');
    const completed = evs.find(e => e.activity === 'agent_cycle_completed');
    const failed = evs.some(e => e.activity === 'agent_cycle_failed');
    const failures = completed?.attributes?.failures ?? (failed ? 1 : 0);
    // N6: per-symbol durations (additive) + the symbols this cycle covered.
    const perSymbol = completed?.attributes?.per_symbol ?? {};
    const symbols = Object.keys(perSymbol).length
      ? Object.keys(perSymbol) : (started?.attributes?.symbols ?? []);
    return {
      caseId,
      isCycle: caseId.startsWith('cycle'),
      start: evs[0].timestamp,
      durationMs: completed?.attributes?.duration_ms ?? null,
      ran: [...new Set(completed?.attributes?.ran ?? [])],
      failures,
      status: failures > 0 ? 'failed' : completed ? 'completed' : 'running',
      activities: evs.map(e => e.activity),
      symbols, perSymbol,
    };
  }).sort((a, b) => (a.start < b.start ? 1 : -1));

  // N6: symbol filter over cycle traces.
  const allSymbols = [...new Set(rows.flatMap(r => r.symbols))].sort();
  const rowsF = symbolF === 'all' ? rows : rows.filter(r => r.symbols.includes(symbolF));

  const cycles = rows.filter(r => r.isCycle);
  const durations = cycles.map(r => r.durationMs).filter(x => x != null);
  const avgMs = durations.length ? durations.reduce((a, b) => a + b, 0) / durations.length : null;
  const lastTs = rows.length ? rows[0].start : null;
  const isActive = lastTs && (Date.now() - new Date(lastTs).getTime()) < 5 * 60 * 1000;

  let body;
  if (loading) {
    body = <LoadingState label="Carregando eventos de processo…" />;
  } else if (error) {
    body = <ErrorState message="Erro ao carregar eventos" onRetry={load} />;
  } else if (!rows.length) {
    body = <EmptyState label="Nenhum evento de processo ainda" sub="O loop do orquestrador grava um evento por ciclo aqui. Inicie o loop para vê-los." />;
  } else {
    body = (
      <>
        <div className="grid kpi-row" style={{ marginBottom: 20 }}>
          <div className="card"><KPI label="Ciclos registrados" value={cycles.length} format="int" icon="refresh" /></div>
          <div className="card"><KPI label="Falhas" value={cycles.filter(r => r.status === 'failed').length} format="int" icon="alert" /></div>
          <div className="card"><KPI label="Duração média" value={avgMs == null ? 'Sem dados' : `${fmtNum(avgMs / 1000)}s`} icon="clock" /></div>
          <div className="card">
            <KPI label="Último ciclo" value={_ago(lastTs)} sub={isActive ? 'loop ativo' : 'sem atividade recente'} icon="activity" />
          </div>
        </div>

        <div className="card">
          <div className="card-head">
            <span className="card-title"><Icon name="activity" />Traços de processo (XES)</span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              {allSymbols.length > 1 && (
                <select className="input" value={symbolF} onChange={e => setSymbolF(e.target.value)}
                  aria-label="Filtrar por símbolo" style={{ width: 'auto', minWidth: 130 }}>
                  <option value="all">Todos os símbolos</option>
                  {allSymbols.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              )}
              <Badge variant={isActive ? 'ok' : 'neutral'}>{isActive ? 'Loop ativo' : 'Loop inativo'}</Badge>
            </span>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table className="tbl">
              <thead>
                <tr>
                  <th>Caso</th>
                  <th>Tipo</th>
                  <th>Início</th>
                  <th className="th-num">Duração</th>
                  <th>Duração por símbolo</th>
                  <th>Atividades</th>
                  <th className="th-num">Falhas</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {rowsF.slice(0, 40).map(r => (
                  <tr key={r.caseId}>
                    <td style={{ fontFamily: 'var(--mono)', fontSize: 11.5, color: 'var(--ink-3)' }}>{r.caseId}</td>
                    <td><Badge variant={r.isCycle ? 'violet' : 'info'} dot={false}>{r.isCycle ? 'Ciclo' : 'Ordem'}</Badge></td>
                    <td style={{ fontFamily: 'var(--mono)', fontSize: 11.5, whiteSpace: 'nowrap' }}>{(r.start ?? '').substring(11, 19)}</td>
                    <td className="num">{r.durationMs == null ? '—' : `${fmtNum(r.durationMs / 1000)}s`}</td>
                    <td style={{ fontSize: 11, color: 'var(--ink-2)' }}>
                      {Object.keys(r.perSymbol).length ? (
                        <span style={{ display: 'flex', flexWrap: 'wrap', gap: '2px 8px' }}>
                          {Object.entries(r.perSymbol).map(([s, ms]) => (
                            <span key={s} style={{ fontFamily: 'var(--mono)', whiteSpace: 'nowrap' }}>
                              {s.replace('/USDT', '')} <b>{Math.round(ms)}ms</b>
                            </span>
                          ))}
                        </span>
                      ) : '—'}
                    </td>
                    <td style={{ fontSize: 11.5, color: 'var(--ink-2)' }}>
                      {r.isCycle && r.ran.length ? r.ran.join(' · ') : r.activities.join(' → ')}
                    </td>
                    <td className="num" style={{ color: r.failures > 0 ? 'var(--down)' : 'var(--ink-3)' }}>{r.failures || '—'}</td>
                    <td><Badge variant={TRACE_STATUS[r.status] ?? 'neutral'}>{TRACE_LABEL[r.status] ?? r.status}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </>
    );
  }

  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="page-title">Observabilidade</h1>
          <div className="page-sub">Ciclos do orquestrador e transições de processo (event log XES)</div>
        </div>
        <Btn variant="ghost" size="sm" onClick={load}><Icon name="refresh" size={13} /> Atualizar</Btn>
      </div>
      {body}
    </div>
  );
}
window.ScreenObservability = ScreenObservability;
