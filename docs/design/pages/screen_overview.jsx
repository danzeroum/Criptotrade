/* ============================================================
   Criptotrade — Screen: Visão Geral / Portfólio
   KPIs de performance reais (GET /v1/metrics), curva de capital
   (GET /v1/metrics/equity) e últimas ordens. Escopo pelo seletor
   global de par ('ALL' = portfólio). Sem dados mockados.
   ============================================================ */
const { useState, useEffect } = React;

const PERIODS = [
  { value: '1d', label: '1D' },
  { value: '7d', label: '7D' },
  { value: '30d', label: '30D' },
  { value: '90d', label: '90D' },
  { value: 'all', label: 'Tudo' },
];

const O_STATUS = {
  pending: 'warn', approved: 'ok', filled: 'ok', rejected: 'down', cancelled: 'neutral',
};

function ScreenOverview() {
  const mock = !!window.USE_MOCK_DATA;
  const [scope] = useCurrentPair();
  const [period, setPeriod] = useState('7d');
  const [metrics, setMetrics] = useState(null);
  const [equity, setEquity] = useState(null);
  const [orders, setOrders] = useState(null);
  const [loading, setLoading] = useState(!mock);
  const [error, setError] = useState(null);

  const load = () => {
    if (mock) return;
    setLoading(true);
    setError(null);
    const sym = scope;
    const pairQ = sym && sym !== 'ALL' ? `&pair=${encodeURIComponent(sym)}` : '';
    const eqPeriod = period === '1d' ? '7d' : period;  // /equity não aceita 1d
    Promise.all([
      CT_API.getMetrics(period, sym),
      CT_API.getEquity(eqPeriod, sym).catch(() => []),
      CT_API.getOrders(8, 0, pairQ).catch(() => []),
    ])
      .then(([m, eq, ords]) => {
        setMetrics(m);
        setEquity(Array.isArray(eq) ? eq : []);
        setOrders(Array.isArray(ords) ? ords : []);
        setLoading(false);
      })
      .catch(e => { setError(e); setLoading(false); });
  };

  useEffect(() => { load(); }, [scope, period, mock]);

  // Honest formatting: null ≠ 0 → "Sem dados".
  const ratio = (v) => (v == null ? 'Sem dados' : (+v).toFixed(2));
  const pct = (v) => (v == null ? 'Sem dados' : `${(+v * 100).toFixed(1)}%`);

  let body;
  if (mock) {
    body = <EmptyState label="Visão Geral conecta ao backend" sub="Inicie a API para ver os KPIs reais do portfólio." />;
  } else if (loading) {
    body = <LoadingState label="Carregando métricas…" />;
  } else if (error) {
    body = <ErrorState message="Erro ao carregar métricas" onRetry={load} />;
  } else if (metrics && !metrics.has_data) {
    body = <EmptyState label="Sem trades fechados ainda" sub="Os KPIs aparecem quando houver histórico no ledger." />;
  } else if (metrics) {
    body = (
      <>
        <div className="grid kpi-row" style={{ marginBottom: 16 }}>
          <div className="card"><KPI label="Valor do portfólio" value={metrics.portfolio_value_usdt} format="usd" icon="dollar" /></div>
          <div className="card"><KPI label={`P&L (${period})`} value={metrics.pnl_period_usdt} format="usd" delta={(metrics.pnl_period_pct ?? 0) * 100} icon="trending" /></div>
          <div className="card"><KPI label="Trades" value={metrics.total_trades} format="int" icon="list" /></div>
          <div className="card"><KPI label="Posições abertas" value={metrics.open_positions} format="int" sub={`exposição ${pct(metrics.exposure_pct)}`} icon="activity" /></div>
        </div>
        <div className="grid kpi-row" style={{ marginBottom: 20 }}>
          <div className="card"><KPI label="Sharpe" value={ratio(metrics.sharpe_ratio)} /></div>
          <div className="card"><KPI label="Win rate" value={pct(metrics.win_rate)} /></div>
          <div className="card"><KPI label="Max drawdown" value={pct(metrics.max_drawdown)} /></div>
          <div className="card"><KPI label="Profit factor" value={ratio(metrics.profit_factor)} /></div>
        </div>

        <div className="grid" style={{ gridTemplateColumns: '1fr 360px', marginBottom: 20, alignItems: 'start' }}>
          <div className="card">
            <div className="card-head"><span className="card-title"><Icon name="activity" />Curva de capital</span></div>
            <div className="card-pad">
              {equity && equity.length > 1
                ? <EquityChart points={equity} />
                : <EmptyState label="Sem curva ainda" sub="Precisa de pelo menos 2 trades fechados." />}
            </div>
          </div>
          <div className="card">
            <div className="card-head"><span className="card-title"><Icon name="list" />Últimas ordens</span></div>
            <div className="card-pad" style={{ padding: '6px 0' }}>
              {orders && orders.length > 0 ? orders.map(o => (
                <div key={o.id} className="stat-row" style={{ padding: '9px 16px' }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
                    <Badge variant={o.side === 'buy' ? 'ok' : 'down'}>{o.side === 'buy' ? 'C' : 'V'}</Badge>
                    <span style={{ fontFamily: 'var(--mono)', fontSize: 12.5, overflow: 'hidden', textOverflow: 'ellipsis' }}>{o.pair}</span>
                  </span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span className="stat-v" style={{ fontSize: 12 }}>${(o.notional ?? 0).toLocaleString('en', { maximumFractionDigits: 0 })}</span>
                    <Badge variant={O_STATUS[o.status] ?? 'neutral'} dot={false}>{o.status}</Badge>
                  </span>
                </div>
              )) : <EmptyState label="Nenhuma ordem" />}
            </div>
          </div>
        </div>
      </>
    );
  }

  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="page-title">Visão Geral</h1>
          <div className="page-sub">{scope === 'ALL' ? 'Portfólio consolidado' : `Par ${scope}`}</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <PairSelect allowAll />
          <Seg options={PERIODS} value={period} onChange={setPeriod} />
          <Btn variant="ghost" size="sm" onClick={load}><Icon name="refresh" size={13} /></Btn>
        </div>
      </div>
      {body}
    </div>
  );
}
window.ScreenOverview = ScreenOverview;
