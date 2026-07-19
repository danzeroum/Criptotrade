/* ============================================================
   Criptotrade — Mesa Multi-Ativo (N2): todos os pares operados
   numa visão só. 1 request (GET /v1/desk/summary), fan-out no
   backend. Clique numa linha → Mercado daquele par (a Mesa é o
   hub; o Mercado, o drill-down).
   ============================================================ */
const { useState, useEffect } = React;

const _REGIME_META = {
  strong_uptrend:   { label: 'Alta forte',   cls: 'badge-ok' },
  strong_downtrend: { label: 'Baixa forte',  cls: 'badge-down' },
  sideways:         { label: 'Lateral',      cls: 'badge-neutral' },
  chaotic:          { label: 'Caótico',      cls: 'badge-warn' },
  unknown:          { label: 'Desconhecido', cls: 'badge-neutral' },
};

const _SIGNAL_CLS = { buy: 'badge-ok', sell: 'badge-down' };

// Deterministic mock — 5 majors in MIXED states (position aberta, sinal ativo,
// aguardando), so the demo mirrors the real Mesa and screenshots stay stable.
function _mockDesk() {
  const now = new Date();
  const iso = (minsAgo) => new Date(now - minsAgo * 60000).toISOString();
  const rows = [
    { symbol: 'SOL/USDT', last: 160.42, change_24h_pct: 4.81, regime: 'strong_uptrend', regime_label: 'Alta forte',
      signal_action: 'buy', signal_confidence: 0.90, position_side: 'buy', position_qty: 1.2, position_entry: 150.1, unrealized_pnl: 12.38, as_of: iso(1), last_cycle_at: iso(1) },
    { symbol: 'BTC/USDT', last: 64810.0, change_24h_pct: 2.34, regime: 'strong_uptrend', regime_label: 'Alta forte',
      signal_action: 'buy', signal_confidence: 0.82, position_side: 'buy', position_qty: 0.03, position_entry: 61200.0, unrealized_pnl: 108.30, as_of: iso(1), last_cycle_at: iso(1) },
    { symbol: 'ETH/USDT', last: 3208.5, change_24h_pct: -1.12, regime: 'sideways', regime_label: 'Lateral',
      signal_action: 'sell', signal_confidence: 0.71, position_side: null, position_qty: null, position_entry: null, unrealized_pnl: null, as_of: iso(2), last_cycle_at: iso(2) },
    { symbol: 'BNB/USDT', last: 592.3, change_24h_pct: 0.42, regime: 'chaotic', regime_label: 'Caótico',
      signal_action: 'hold', signal_confidence: 0.34, position_side: null, position_qty: null, position_entry: null, unrealized_pnl: null, as_of: iso(2), last_cycle_at: iso(2) },
    { symbol: 'XRP/USDT', last: 0.61, change_24h_pct: 1.05, regime: 'unknown', regime_label: 'Desconhecido',
      signal_action: null, signal_confidence: null, position_side: null, position_qty: null, position_entry: null, unrealized_pnl: null, as_of: null, last_cycle_at: null },
  ];
  return { rows, slots_used: 2, slots_max: 3, capital_allocated: 3673.0, capital_free: 6327.0, signals_active: 3 };
}

function _rel(iso) {
  if (!iso) return '—';
  const secs = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  if (secs < 60) return `há ${secs}s`;
  const m = Math.round(secs / 60);
  if (m < 60) return `há ${m}min`;
  return `há ${Math.round(m / 60)}h`;
}

function _sortRows(rows, by) {
  const r = [...rows];
  if (by === 'pnl') return r.sort((a, b) => (b.unrealized_pnl ?? -1e18) - (a.unrealized_pnl ?? -1e18));
  if (by === 'change') return r.sort((a, b) => (b.change_24h_pct ?? -1e18) - (a.change_24h_pct ?? -1e18));
  return r;  // 'default' = server order (actionable first)
}

function ScreenDesk({ navigate } = {}) {
  const mock = window.USE_MOCK_DATA;
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [sortBy, setSortBy] = useState('default');

  const load = () => {
    if (mock) { setData(_mockDesk()); return; }
    CT_API.getDeskSummary().then((d) => { setData(d); setError(null); }).catch(setError);
  };
  useEffect(() => { load(); }, []);
  useEffect(() => {
    if (mock) return;
    const id = setInterval(load, 15000);  // server TTL is ~8s; poll a bit slower
    return () => clearInterval(id);
  }, []);

  if (error) return <ErrorState message={error.message} onRetry={load} />;
  if (!data) return <LoadingState />;

  const rows = _sortRows(data.rows, sortBy);
  const open = (sym) => { CT_PAIR.set(sym); navigate?.('market'); };

  return (
    <div>
      <div className="page-head">
        <div>
          <div className="page-title">Mesa Multi-Ativo</div>
          <div className="page-sub">Todos os pares operados numa visão — clique numa linha para abrir o Mercado.</div>
        </div>
        <Seg
          value={sortBy}
          onChange={setSortBy}
          options={[{ value: 'default', label: 'Acionável' }, { value: 'pnl', label: 'P&L' }, { value: 'change', label: 'Variação' }]}
        />
      </div>

      {/* Linha-resumo fixa: slots, capital, sinais ativos */}
      <div className="desk-summary">
        <div className="desk-sum-cell">
          <div className="desk-sum-l">Slots de posição</div>
          <div className="desk-sum-v">{data.slots_used}<span className="desk-sum-of"> / {data.slots_max}</span></div>
        </div>
        <div className="desk-sum-cell">
          <div className="desk-sum-l">Capital alocado</div>
          <div className="desk-sum-v">{fmtUsd(data.capital_allocated)}</div>
        </div>
        <div className="desk-sum-cell">
          <div className="desk-sum-l">Capital livre</div>
          <div className="desk-sum-v">{fmtUsd(data.capital_free)}</div>
        </div>
        <div className="desk-sum-cell">
          <div className="desk-sum-l">Sinais ativos (≥0.6)</div>
          <div className="desk-sum-v">{data.signals_active}<span className="desk-sum-of"> / {data.rows.length}</span></div>
        </div>
      </div>

      <div className="card desk-grid" role="table" aria-label="Mesa Multi-Ativo">
        <div className="desk-row desk-head" role="row">
          <span>Par</span><span>Preço · 24h</span><span>Regime</span><span>Sinal</span><span>Posição · P&L</span><span>Ciclo</span>
        </div>
        {rows.map((r) => {
          const rm = _REGIME_META[r.regime] || _REGIME_META.unknown;
          const chg = r.change_24h_pct;
          return (
            <div key={r.symbol} className="desk-row" role="row" tabIndex={0}
                 onClick={() => open(r.symbol)}
                 onKeyDown={(e) => { if (e.key === 'Enter') open(r.symbol); }}>
              <span className="desk-sym">{r.symbol}</span>
              <span>
                <b>{r.last != null ? fmtPrice(r.last) : '—'}</b>
                {chg != null && (
                  <span className={'desk-chg ' + (chg >= 0 ? 'up' : 'down')}>
                    {chg >= 0 ? '+' : ''}{fmtNum(chg, 2)}%
                  </span>
                )}
              </span>
              <span><span className={'badge ' + rm.cls}>{r.regime_label || rm.label}</span></span>
              <span>
                {r.signal_action
                  ? <span className={'badge ' + (_SIGNAL_CLS[r.signal_action] || 'badge-neutral')}>
                      {r.signal_action.toUpperCase()}
                      {r.signal_confidence != null && <span className="desk-conf"> · {Math.round(r.signal_confidence * 100)}%</span>}
                    </span>
                  : <span className="desk-muted">aguardando</span>}
              </span>
              <span>
                {r.position_side
                  ? <span>
                      <span className={'badge ' + (r.position_side === 'buy' ? 'badge-ok' : 'badge-down')}>{r.position_side.toUpperCase()}</span>
                      {r.unrealized_pnl != null && (
                        <span className={'desk-pnl ' + (r.unrealized_pnl >= 0 ? 'up' : 'down')}>{fmtUsd(r.unrealized_pnl)}</span>
                      )}
                    </span>
                  : <span className="desk-muted">—</span>}
              </span>
              <span className="desk-muted">{_rel(r.as_of)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
window.ScreenDesk = ScreenDesk;
