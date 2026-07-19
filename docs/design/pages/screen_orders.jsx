/* ============================================================
   Criptotrade — Screen: Orders history
   ============================================================ */
const { useState, useEffect } = React;

const ORDER_STATUS_VARIANT = {
  pending:   'warn',
  approved:  'ok',
  filled:    'ok',
  rejected:  'down',
  cancelled: 'neutral',
};

const ORDER_STATUS_LABEL = {
  pending:   'Pendente',
  approved:  'Aprovada',
  filled:    'Executada',
  rejected:  'Rejeitada',
  cancelled: 'Cancelada',
};

function ScreenOrders() {
  const mock = !!window.USE_MOCK_DATA;
  const mockOrders = CT.orders.map(o => ({
    ...o,
    stop_loss:         o.stop,
    take_profit:       o.takeProfit,
    position_size_pct: o.sizePct,
    operator_note:     o.operatorNote,
  }));

  // N5: mock closed trades (realized P&L) for the per-pair footer.
  const mockTrades = [
    { symbol: 'BTC/USDT', pnl: 108.30 }, { symbol: 'BTC/USDT', pnl: -42.10 },
    { symbol: 'ETH/USDT', pnl: 61.50 }, { symbol: 'SOL/USDT', pnl: 12.38 },
    { symbol: 'SOL/USDT', pnl: 24.90 }, { symbol: 'XRP/USDT', pnl: -8.20 },
  ];

  const [scope] = useCurrentPair();
  const [orders,  setOrders]  = useState(mock ? mockOrders : null);
  const [trades,  setTrades]  = useState(mock ? mockTrades : null);
  const [loading, setLoading] = useState(!mock);
  const [error,   setError]   = useState(null);
  const [statusF, setStatusF] = useState('all');
  const [sideF,   setSideF]   = useState('all');

  useEffect(() => {
    if (mock) return;
    setLoading(true);
    const pairQ = scope && scope !== 'ALL' ? `&pair=${encodeURIComponent(scope)}` : '';
    Promise.all([CT_API.getOrders(100, 0, pairQ), CT_API.getTrades(200, 0, pairQ).catch(() => [])])
      .then(([ords, trds]) => {
        setOrders(Array.isArray(ords) ? ords : []);
        setTrades(Array.isArray(trds) ? trds : []);
        setLoading(false);
      })
      .catch(e => { setError(e); setLoading(false); });
  }, [mock, scope]);

  if (loading) return <LoadingState label="Carregando ordens…" />;
  if (error)   return <ErrorState message="Erro ao carregar ordens" onRetry={() => { setError(null); setLoading(true); }} />;
  if (!orders) return <EmptyState />;

  const filtered = orders.filter(o => {
    if (statusF !== 'all' && o.status !== statusF) return false;
    if (sideF   !== 'all' && o.side   !== sideF)   return false;
    return true;
  });

  const pending = orders.filter(o => o.status === 'pending').length;
  const filled  = orders.filter(o => o.status === 'filled').length;
  const rejected = orders.filter(o => o.status === 'rejected').length;
  const winRate = filled > 0
    ? orders.filter(o => o.status === 'filled' && o.side === 'buy').length / filled
    : null;

  // N5: realized P&L per pair (closed trades). REALIZED ONLY — never mixed with
  // unrealized (that lives on the Mesa). Surfaced in ∑ mode, where the list spans
  // multiple pairs and a single number would be illegible.
  const pnlByPair = (trades || []).reduce((m, t) => {
    m[t.symbol] = (m[t.symbol] || 0) + (t.pnl || 0);
    return m;
  }, {});
  const showPnlByPair = (!scope || scope === 'ALL') && Object.keys(pnlByPair).length > 1;

  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="page-title">Ordens</h1>
          <div className="page-sub">
            {orders.length} ordens{scope && scope !== 'ALL' ? ` · ${scope}` : ' · todos os pares'}
          </div>
        </div>
        <PairSelect allowAll />
      </div>

      <div className="grid kpi-row" style={{ marginBottom: 20 }}>
        <div className="card"><KPI label="Total" value={orders.length} format="int" icon="list" /></div>
        <div className="card"><KPI label="Pendentes" value={pending} format="int" icon="clock" /></div>
        <div className="card"><KPI label="Executadas" value={filled} format="int" icon="check" /></div>
        <div className="card"><KPI label="Rejeitadas" value={rejected} format="int" icon="x" /></div>
      </div>

      <div className="card">
        <div className="card-head">
          <span className="card-title"><Icon name="list" />Histórico de Ordens</span>
          <div style={{ display: 'flex', gap: 10 }}>
            <Seg
              options={[
                { value: 'all',      label: 'Todas' },
                { value: 'pending',  label: 'Pendentes' },
                { value: 'filled',   label: 'Executadas' },
                { value: 'rejected', label: 'Rejeitadas' },
              ]}
              value={statusF}
              onChange={setStatusF}
            />
            <Seg
              options={[
                { value: 'all',  label: 'Todos' },
                { value: 'buy',  label: 'Compra' },
                { value: 'sell', label: 'Venda' },
              ]}
              value={sideF}
              onChange={setSideF}
            />
          </div>
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table className="tbl">
            <thead>
              <tr>
                <th>ID</th>
                <th>Par</th>
                <th>Lado</th>
                <th className="th-num">Qtd.</th>
                <th className="th-num">Preço</th>
                <th className="th-num">Nocional</th>
                <th className="th-num">Stop</th>
                <th className="th-num">Alvo</th>
                <th className="th-num">R/R</th>
                <th>Estratégia</th>
                <th className="th-num">Conf.</th>
                <th>Status</th>
                <th>Horário</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={13} style={{ textAlign: 'center', color: 'var(--ink-3)', padding: '32px 14px' }}>
                    Nenhuma ordem encontrada
                  </td>
                </tr>
              ) : filtered.map(o => (
                <tr key={o.id}>
                  <td style={{ fontFamily: 'var(--mono)', fontSize: 11.5, color: 'var(--ink-3)' }}>
                    {o.id.replace('ord_', '#')}
                  </td>
                  <td style={{ fontFamily: 'var(--mono)', fontWeight: 500 }}>{o.pair}</td>
                  <td>
                    <Badge variant={o.side === 'buy' ? 'ok' : 'down'}>
                      {o.side === 'buy' ? 'C' : 'V'}
                    </Badge>
                  </td>
                  <td className="num">{o.quantity}</td>
                  <td className="num">{fmtUsd(o.price ?? 0)}</td>
                  <td className="num">{fmtUsd(o.notional ?? 0)}</td>
                  <td className="num" style={{ color: 'var(--down)' }}>
                    {o.stop_loss ? fmtUsd(o.stop_loss) : '—'}
                  </td>
                  <td className="num" style={{ color: 'var(--up)' }}>
                    {o.take_profit ? fmtUsd(o.take_profit) : '—'}
                  </td>
                  <td className="num" style={{ fontWeight: 500 }}>
                    {o.rr ? `${o.rr}×` : '—'}
                  </td>
                  <td style={{ fontSize: 12, color: 'var(--ink-3)' }}>{o.strategy}</td>
                  <td className="num">{Math.round((o.confidence ?? 0) * 100)}%</td>
                  <td>
                    <Badge variant={ORDER_STATUS_VARIANT[o.status] ?? 'neutral'}>
                      {ORDER_STATUS_LABEL[o.status] ?? o.status}
                    </Badge>
                    {o.auto_approved && (
                      <span style={{ fontSize: 10, color: 'var(--ink-4)', marginLeft: 4 }}>auto</span>
                    )}
                  </td>
                  <td style={{ fontSize: 11.5, color: 'var(--ink-3)', fontFamily: 'var(--mono)', whiteSpace: 'nowrap' }}>
                    {(o.created_at ?? '').substring(0, 16)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {showPnlByPair && (
          <div className="pnl-by-pair">
            <span className="pnl-by-pair-l">P&L realizado por par <span className="desk-muted">(trades fechados)</span></span>
            <div className="pnl-by-pair-cells">
              {Object.entries(pnlByPair).sort((a, b) => b[1] - a[1]).map(([sym, v]) => (
                <span key={sym} className="pnl-by-pair-cell">
                  <b>{sym}</b>
                  <span className={v >= 0 ? 'up' : 'down'}>{v >= 0 ? '+' : ''}{fmtUsd(v)}</span>
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
window.ScreenOrders = ScreenOrders;
