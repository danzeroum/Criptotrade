/* ============================================================
   Criptotrade — Screen: Visão Geral / Portfólio  (#overview)
   Headline de performance — GET /v1/metrics (+?symbol &period)
   + GET /v1/metrics/equity + GET /v1/orders
   ============================================================ */
const { useState: _useOv, useEffect: _useOvE } = React;

const OV_STATUS = {
  pending:   { label: 'Pendente',  kind: 'warn',    icon: 'clock' },
  approved:  { label: 'Aprovada',  kind: 'info',    icon: 'check' },
  filled:    { label: 'Executada', kind: 'ok',      icon: 'check' },
  rejected:  { label: 'Rejeitada', kind: 'down',    icon: 'x' },
  cancelled: { label: 'Cancelada', kind: 'neutral', icon: 'x' },
};

function MetricTileOv({ label, icon, raw, fmt, tone, sub, delta }) {
  if (raw == null) {
    return (
      <div className="card kpi">
        <div className="kpi-label">{icon && <Icon name={icon} size={13} />}{label}</div>
        <div className="kpi-value" style={{ fontSize: 19, color: 'var(--ink-4)' }}>Sem dados</div>
        <div className="kpi-sub">amostra insuficiente</div>
      </div>
    );
  }
  let v = raw, color = tone;
  if (fmt === 'usd') v = fmtUsd(raw);
  else if (fmt === 'usd0') v = fmtUsd(raw, 0);
  else if (fmt === 'pct') v = (raw >= 0 ? '+' : '') + fmtPct(raw);
  else if (fmt === 'pctp') v = fmtPct(raw * 100);
  else if (fmt === 'num') v = fmtNum(raw);
  else if (fmt === 'int') v = Math.round(raw).toLocaleString('pt-BR');
  if (delta) color = raw >= 0 ? 'var(--up)' : 'var(--down)';
  return (
    <div className="card kpi">
      <div className="kpi-label">{icon && <Icon name={icon} size={13} />}{label}</div>
      <div className="kpi-value" style={color ? { color } : null}>{v}</div>
      {sub && <div className="kpi-sub">{sub}</div>}
    </div>
  );
}

function AllocationCard({ pair }) {
  const rows = pair === 'ALL'
    ? CT.pairs.map(p => ({ ...p, m: CT.metricsBySymbol[p.symbol] }))
    : [{ ...(CT.pairBy[pair] || CT.pairs[0]), m: CT.metricsBySymbol[pair] }];
  const total = rows.reduce((s, r) => s + (r.m ? r.m.portfolio_value_usdt : 0), 0) || 1;
  return (
    <div className="card">
      <CardHead icon="layers" title="Alocação por par" sub={pair === 'ALL' ? 'portfólio' : pair} />
      <div className="card-pad" style={{ paddingTop: 12 }}>
        {rows.map(r => {
          const v = r.m ? r.m.portfolio_value_usdt : 0;
          const pct = v / total * 100;
          return (
            <div key={r.symbol} style={{ marginBottom: 13 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 6 }}>
                <PairGlyph p={r} size={20} />
                <b style={{ fontSize: 12.5 }}>{r.symbol}</b>
                <span className="mono muted" style={{ fontSize: 11, marginLeft: 'auto' }}>{fmtUsd(v, 0)}</span>
                <span className="mono" style={{ fontSize: 11.5, fontWeight: 600, width: 42, textAlign: 'right' }}>{pct.toFixed(1)}%</span>
              </div>
              <Meter value={pct} color={r.color} height={6} />
            </div>
          );
        })}
        <div className="hr" style={{ margin: '4px 0 12px' }} />
        <StatRow k="Capital total" v={fmtUsd(total, 0)} />
        <StatRow k="Posições abertas" v={rows.reduce((s, r) => s + (r.m ? r.m.open_positions : 0), 0)} />
      </div>
    </div>
  );
}

function OverviewScreen() {
  const [pair] = useCurrentPair();
  const [period, setPeriod] = _useOv('30d');
  const [state, setState] = _useOv('ok'); // ok | loading | empty | error  (preview de estados honestos)

  const m = CT.getMetrics(pair, period);
  const eq = CT.getEquity(pair, period);
  const orders = (pair === 'ALL' ? CT.orders : CT.orders.filter(o => o.pair === pair)).slice(0, 7);
  const periodLabel = { '1d': 'hoje', '7d': '7 dias', '30d': '30 dias', '90d': '90 dias', all: 'desde o início' }[period];

  return (
    <div className="content-inner screen-enter">
      <div className="page-head">
        <div>
          <div className="page-title">Visão Geral</div>
          <div className="page-sub">Headline de performance · {pair === 'ALL' ? 'portfólio consolidado' : pair} · {periodLabel}</div>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <PairSelect allowAll />
          <Seg value={period} onChange={setPeriod} tip="Período de análise das métricas: de 1 dia até todo o histórico."
            options={[{ value: '1d', label: '1d' }, { value: '7d', label: '7d' }, { value: '30d', label: '30d' }, { value: '90d', label: '90d' }, { value: 'all', label: 'Tudo' }]} />
        </div>
      </div>

      {/* honest-states preview — demonstra os 4 estados obrigatórios (UX P0) */}
      <div className="card card-pad" style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16, padding: '11px 16px' }}>
        <Icon name="info" size={15} style={{ color: 'var(--ink-3)' }} />
        <span className="label-xs">Pré-visualizar estado</span>
        <Seg value={state} onChange={setState} tip="Demonstra como a tela responde a cada estado de dados: normal, carregando, vazio e backend offline."
          options={[{ value: 'ok', label: 'OK' }, { value: 'loading', label: 'Carregando' }, { value: 'empty', label: 'Vazio' }, { value: 'error', label: 'Offline' }]} />
        <span className="muted" style={{ fontSize: 11.5, marginLeft: 4 }}>Toda área que busca dados desenha Loading · Vazio · Erro · OK — null ≠ 0.</span>
      </div>

      {state === 'loading' && <div className="card"><LoadingState min={420} /></div>}
      {state === 'empty' && <div className="card"><EmptyState min={420} message="Sem histórico no período" hint="Nenhuma operação registrada para este par no intervalo selecionado." /></div>}
      {state === 'error' && <div className="card"><ErrorState min={420} onRetry={() => setState('ok')} /></div>}

      {state === 'ok' && <>
        {/* KPI headline */}
        <div className="grid" style={{ gridTemplateColumns: 'repeat(4,1fr)', marginBottom: 16 }}>
          <MetricTileOv label="Valor do portfólio" icon="dollar" raw={m.portfolio_value_usdt} fmt="usd" sub={`exposição ${fmtPct(m.exposure_pct)}`} />
          <MetricTileOv label={`P&L · ${periodLabel}`} icon="trendUp" raw={m.pnl_period_pct} fmt="pct" delta sub={fmtUsd(m.pnl_period_usdt)} />
          <MetricTileOv label="Sharpe ratio" icon="pulse" raw={m.sharpe_ratio} fmt="num" sub="anualizado" />
          <MetricTileOv label="Win rate" icon="target" raw={m.win_rate} fmt="pctp" sub={`${m.total_trades} trades`} />
          <MetricTileOv label="Max drawdown" icon="trendDown" raw={m.max_drawdown} fmt="pct" tone="var(--down)" sub="pico → vale" />
          <MetricTileOv label="Profit factor" icon="backtest" raw={m.profit_factor} fmt="num" sub="ganho ÷ perda" />
          <MetricTileOv label="Total de trades" icon="orders" raw={m.total_trades} fmt="int" sub={periodLabel} />
          <MetricTileOv label="Posições abertas" icon="layers" raw={m.open_positions} fmt="int" sub={`${fmtPct(m.exposure_pct)} do capital`} />
        </div>

        {/* equity + allocation */}
        <div className="grid" style={{ gridTemplateColumns: '1fr 320px', gap: 16, marginBottom: 16 }}>
          <div className="card">
            <CardHead icon="pulse" title="Curva de capital" sub={`${pair === 'ALL' ? 'portfólio' : pair} · ${periodLabel}`}
              right={<div style={{ display: 'flex', gap: 12, fontSize: 10.5, color: 'var(--ink-3)' }}>
                <span style={{ display: 'flex', gap: 4, alignItems: 'center' }}><span style={{ width: 9, height: 3, background: 'var(--ink)', borderRadius: 2 }} />equity</span>
                <span style={{ display: 'flex', gap: 4, alignItems: 'center' }}><span style={{ width: 9, height: 9, background: 'var(--down)', opacity: .3, borderRadius: 2 }} />drawdown</span>
              </div>} />
            <div style={{ padding: '14px 16px 6px' }}>
              <EquityChart data={eq} height={260} showDrawdown />
            </div>
          </div>
          <AllocationCard pair={pair} />
        </div>

        {/* recent orders */}
        <div className="card">
          <CardHead icon="orders" title="Últimas ordens" sub={pair === 'ALL' ? 'todos os pares' : pair}
            right={<Btn kind="ghost" sm iconRight="arrowRight" data-tip="Abre a tela de Ordens com o ciclo de vida completo e o histórico fechado." onClick={() => location.hash = '#orders'}>Ver todas</Btn>} />
          {orders.length === 0 ? <EmptyState min={160} message="Sem ordens" hint="Nenhuma ordem registrada para este par." /> : (
            <table className="tbl">
              <thead>
                <tr>
                  <th>ID</th><th>Par</th><th>Lado</th><th className="th-num">Notional</th>
                  <th className="th-num">Confiança</th><th>Status</th><th>Horário</th>
                </tr>
              </thead>
              <tbody>
                {orders.map(o => {
                  const s = OV_STATUS[o.status];
                  return (
                    <tr key={o.id}>
                      <td className="mono" style={{ fontSize: 12, color: 'var(--ink-2)' }}>{o.id}</td>
                      <td><b>{o.pair}</b></td>
                      <td><span style={{ color: o.side === 'buy' ? 'var(--up)' : 'var(--down)', fontWeight: 600, fontSize: 12 }}>{o.side === 'buy' ? 'COMPRA' : 'VENDA'}</span></td>
                      <td className="num">{fmtUsd(o.notional)}</td>
                      <td className="num">{Math.round(o.confidence * 100)}%</td>
                      <td><Badge kind={s.kind} dot>{s.label}</Badge></td>
                      <td className="mono" style={{ fontSize: 11.5, color: 'var(--ink-3)' }}>{o.created_at.slice(11)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </>}
    </div>
  );
}

window.OverviewScreen = OverviewScreen;
