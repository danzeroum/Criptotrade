/* ============================================================
   Criptotrade — Mesa Multi-Ativo (N2): todos os pares operados
   numa visão só. 1 request (GET /v1/desk/summary), fan-out no
   backend. Clique numa linha/célula → Mercado daquele par (a Mesa
   é o hub; o Mercado, o drill-down).
   11c: toggle lista⇄heatmap (preferência persistida, sem auto-switch),
   filtro por grupo (watchlists) e hint discreto único acima de ~10 pares.
   ============================================================ */
const { useState, useEffect } = React;

const _REGIME_META = {
  strong_uptrend:   { label: 'Alta forte',   cls: 'badge-ok' },
  strong_downtrend: { label: 'Baixa forte',  cls: 'badge-down' },
  sideways:         { label: 'Lateral',      cls: 'badge-neutral' },
  chaotic:          { label: 'Caótico',      cls: 'badge-warn' },
  unknown:          { label: 'Desconhecido', cls: 'badge-neutral' },
};

// Regime → heatmap-cell color class (reusa os tokens de dado existentes:
// --up/--down/--warn/-bg/-line — nada de paleta nova).
const _REGIME_HEAT = {
  strong_uptrend: 'regime-up', strong_downtrend: 'regime-down',
  chaotic: 'regime-warn', sideways: 'regime-neutral', unknown: 'regime-neutral',
};

const _SIGNAL_CLS = { buy: 'badge-ok', sell: 'badge-down' };

const _PAUSED_TIP = 'Pausado — sem novas ordens; posições abertas seguem geridas (stop/TP ativos)';

// Deterministic mock — 5 majors in MIXED states (position aberta, sinal ativo,
// aguardando), so the demo mirrors the real Mesa and screenshots stay stable.
// e2e: window.MOCK_OPERATED (array) força um conjunto arbitrário (ex.: 12+ pares
// para o hint) — determinístico por índice, sem backend.
function _mockDesk() {
  const now = new Date();
  const iso = (minsAgo) => new Date(now - minsAgo * 60000).toISOString();
  const override = (typeof window !== 'undefined' && window.MOCK_OPERATED) || null;
  if (override && override.length) {
    const regimes = ['strong_uptrend', 'strong_downtrend', 'sideways', 'chaotic', 'unknown'];
    const actions = ['buy', 'sell', null];
    const rows = override.map((symbol, i) => {
      const regime = regimes[i % regimes.length];
      const action = actions[i % actions.length];
      return {
        symbol, last: 100 + i, change_24h_pct: ((i % 7) - 3) * 1.1,
        regime, regime_label: _REGIME_META[regime].label,
        signal_action: action,
        signal_confidence: action ? 0.6 + (i % 4) * 0.1 : null,
        position_side: null, position_qty: null, position_entry: null, unrealized_pnl: null,
        as_of: iso(1 + (i % 5)), last_cycle_at: iso(1 + (i % 5)), paused: false,
      };
    });
    return { rows, slots_used: 0, slots_max: 3, capital_allocated: 0, capital_free: 10000,
             signals_active: rows.filter(r => (r.signal_confidence || 0) >= 0.6).length };
  }
  const rows = [
    { symbol: 'SOL/USDT', last: 160.42, change_24h_pct: 4.81, regime: 'strong_uptrend', regime_label: 'Alta forte',
      signal_action: 'buy', signal_confidence: 0.90, position_side: 'buy', position_qty: 1.2, position_entry: 150.1, unrealized_pnl: 12.38, as_of: iso(1), last_cycle_at: iso(1) },
    { symbol: 'BTC/USDT', last: 64810.0, change_24h_pct: 2.34, regime: 'strong_uptrend', regime_label: 'Alta forte',
      signal_action: 'buy', signal_confidence: 0.82, position_side: 'buy', position_qty: 0.03, position_entry: 61200.0, unrealized_pnl: 108.30, as_of: iso(1), last_cycle_at: iso(1) },
    { symbol: 'ETH/USDT', last: 3208.5, change_24h_pct: -1.12, regime: 'sideways', regime_label: 'Lateral',
      signal_action: 'sell', signal_confidence: 0.71, position_side: null, position_qty: null, position_entry: null, unrealized_pnl: null, as_of: iso(2), last_cycle_at: iso(2) },
    { symbol: 'BNB/USDT', last: 592.3, change_24h_pct: 0.42, regime: 'chaotic', regime_label: 'Caótico', paused: true,
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

function ScreenDesk({ navigate, addToast } = {}) {
  const mock = window.USE_MOCK_DATA;
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [sortBy, setSortBy] = useState('default');
  const [viewMode, setViewMode] = useState(CT_DESK_VIEW.get());   // 'list' | 'heatmap'
  const [groupFilter, setGroupFilter] = useState('ALL');
  const [groups, setGroups] = useState(CT_GROUPS.names());
  const [hintDismissed, setHintDismissed] = useState(CT_DESK_VIEW.hintSeen());
  const canEdit = CT_AUTH.can('edit_settings');

  const load = () => {
    if (mock) { setData(_mockDesk()); return; }
    CT_API.getDeskSummary().then((d) => { setData(d); setError(null); }).catch(setError);
  };

  // N9: pausar/retoma um par direto da Mesa — aplica por ciclo, sem restart.
  const pausePair = async (sym, paused) => {
    if (mock) {
      setData((d) => ({ ...d, rows: d.rows.map((r) => r.symbol === sym ? { ...r, paused } : r) }));
      addToast?.(paused ? 'Par pausado.' : 'Par retomado.', 'check');
      return;
    }
    try {
      await CT_API.setPairPaused(sym, paused);
      addToast?.(paused ? 'Par pausado — sem novas ordens; posições seguem geridas.' : 'Par retomado.', 'check');
      load();
    } catch (e) { addToast?.(e?.message ?? 'Falha ao pausar par.', 'alert'); }
  };
  useEffect(() => { load(); }, []);
  useEffect(() => {
    if (mock) return;
    const id = setInterval(load, 15000);  // server TTL is ~8s; poll a bit slower
    return () => clearInterval(id);
  }, []);
  // Live-reflect view-mode + groups edited elsewhere (Config) within the tab.
  useEffect(() => CT_DESK_VIEW.subscribe(setViewMode), []);
  useEffect(() => CT_GROUPS.subscribe(() => setGroups(CT_GROUPS.names())), []);
  // Housekeeping: drop group memberships for pairs no longer operated (11a removal).
  useEffect(() => { if (data) CT_GROUPS.gc(data.rows.map((r) => r.symbol)); }, [data]);

  if (error) return <ErrorState message={error.message} onRetry={load} />;
  if (!data) return <LoadingState />;

  const open = (sym) => { CT_PAIR.set(sym); navigate?.('market'); };
  const setView = (m) => {
    CT_DESK_VIEW.set(m);
    // Escolher o heatmap conta como "descobriu o modo": não repropor o hint.
    if (m === 'heatmap' && !hintDismissed) { CT_DESK_VIEW.markHintSeen(); setHintDismissed(true); }
  };
  const dismissHint = () => { CT_DESK_VIEW.markHintSeen(); setHintDismissed(true); };

  const sorted = _sortRows(data.rows, sortBy);
  // Filtro de grupo (watchlist). "Todos" = sem filtro. groupOf só é chamado para
  // pares operados (as linhas), então órfãos do localStorage nunca aparecem aqui.
  const visible = groupFilter === 'ALL'
    ? sorted
    : sorted.filter((r) => CT_GROUPS.groupOf(r.symbol) === groupFilter);
  // Nota 1: o hint considera as linhas VISÍVEIS (pós-filtro), não o total —
  // 15 operados filtrados num grupo de 4 não é "muitos pares".
  const showHint = viewMode === 'list' && !hintDismissed && visible.length > 10;
  const emptyGroup = groupFilter !== 'ALL' && visible.length === 0;

  const pausedBadge = (r) => r.paused && (
    <span className="pair-paused-badge" title={_PAUSED_TIP}>PAUSADO</span>
  );

  const listRow = (r) => {
    const rm = _REGIME_META[r.regime] || _REGIME_META.unknown;
    const chg = r.change_24h_pct;
    return (
      <div key={r.symbol} className={'desk-row' + (r.paused ? ' paused' : '')} role="row" tabIndex={0}
           onClick={() => open(r.symbol)}
           onKeyDown={(e) => { if (e.key === 'Enter') open(r.symbol); }}>
        <span className="desk-sym">
          {r.symbol}
          {pausedBadge(r)}
          {canEdit && (
            <button className="desk-pause-btn"
              title={r.paused ? 'Retomar par (aplica no próximo ciclo)' : 'Pausar par — sem novas ordens, sem restart'}
              aria-label={`${r.paused ? 'Retomar' : 'Pausar'} ${r.symbol}`}
              onClick={(e) => { e.stopPropagation(); pausePair(r.symbol, !r.paused); }}>{r.paused ? '▶' : '❙❙'}</button>
          )}
        </span>
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
  };

  // Heatmap: célula compacta, cor por regime. M8 — regime legível SEM cor (rótulo
  // + inicial), célula com role="img" + aria-label resumindo. Pausar é ação da
  // lista/Config (a célula é leitura rápida); aqui só o badge PAUSADO é respeitado.
  const heatCell = (r) => {
    const rm = _REGIME_META[r.regime] || _REGIME_META.unknown;
    const heatCls = _REGIME_HEAT[r.regime] || 'regime-neutral';
    const chg = r.change_24h_pct;
    const label = rm.label;
    const aria = [
      r.symbol, label,
      chg != null ? `24h ${chg >= 0 ? '+' : ''}${fmtNum(chg, 2)}%` : null,
      r.signal_action ? `sinal ${r.signal_action.toUpperCase()}${r.signal_confidence != null ? ` ${Math.round(r.signal_confidence * 100)}%` : ''}` : null,
      r.paused ? 'pausado' : null,
    ].filter(Boolean).join(', ');
    return (
      <div key={r.symbol} className={'heat-cell ' + heatCls + (r.paused ? ' paused' : '')}
           role="img" aria-label={aria} tabIndex={0}
           onClick={() => open(r.symbol)}
           onKeyDown={(e) => { if (e.key === 'Enter') open(r.symbol); }}>
        <div className="heat-top">
          <span className="heat-sym">{r.symbol}</span>
          {pausedBadge(r)}
        </div>
        <div className="heat-regime">
          <span className="heat-reg-ini" aria-hidden="true">{label.charAt(0)}</span>{label}
        </div>
        <div className="heat-metrics">
          {chg != null && (
            <span className={'heat-chg ' + (chg >= 0 ? 'up' : 'down')}>{chg >= 0 ? '+' : ''}{fmtNum(chg, 2)}%</span>
          )}
          {r.signal_action && (
            <span className="heat-sig">{r.signal_action.toUpperCase()}{r.signal_confidence != null ? ` ${Math.round(r.signal_confidence * 100)}%` : ''}</span>
          )}
        </div>
      </div>
    );
  };

  return (
    <div>
      <div className="page-head">
        <div>
          <div className="page-title">Mesa Multi-Ativo</div>
          <div className="page-sub">Todos os pares operados numa visão — clique para abrir o Mercado.</div>
        </div>
        <div className="desk-controls">
          <Seg
            value={viewMode}
            onChange={setView}
            options={[{ value: 'list', label: 'Lista' }, { value: 'heatmap', label: 'Heatmap' }]}
          />
          <Seg
            value={sortBy}
            onChange={setSortBy}
            options={[{ value: 'default', label: 'Acionável' }, { value: 'pnl', label: 'P&L' }, { value: 'change', label: 'Variação' }]}
          />
        </div>
      </div>

      {/* Linha-resumo fixa: slots, capital, sinais ativos — GLOBAL (do sistema,
          não do filtro de grupo). */}
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

      {/* Filtro por grupo (watchlist) — só aparece quando há grupos definidos. */}
      {groups.length > 0 && (
        <div className="desk-group-filter" role="group" aria-label="Filtrar por grupo">
          {['ALL', ...groups].map((g) => (
            <button key={g} className={'group-chip' + (groupFilter === g ? ' active' : '')}
              aria-pressed={groupFilter === g}
              onClick={() => setGroupFilter(g)}>{g === 'ALL' ? 'Todos' : g}</button>
          ))}
        </div>
      )}

      {showHint && (
        <div className="desk-hint" role="status">
          <Icon name="grid" size={13} />
          <span>Muitos pares — experimente o modo heatmap.</span>
          <button className="desk-hint-x" aria-label="Dispensar dica" onClick={dismissHint}>×</button>
        </div>
      )}

      {emptyGroup ? (
        <div className="card desk-empty">
          <div className="desk-empty-msg">Nenhum par operado neste grupo.</div>
          <Btn size="sm" onClick={() => setGroupFilter('ALL')}>Ver Todos</Btn>
        </div>
      ) : viewMode === 'heatmap' ? (
        <div className="card desk-heat-wrap">
          <div className="desk-heat-grid" role="list" aria-label="Mesa Multi-Ativo (heatmap)">
            {visible.map(heatCell)}
          </div>
        </div>
      ) : (
        <div className="card desk-grid" role="table" aria-label="Mesa Multi-Ativo">
          <div className="desk-row desk-head" role="row">
            <span>Par</span><span>Preço · 24h</span><span>Regime</span><span>Sinal</span><span>Posição · P&L</span><span>Ciclo</span>
          </div>
          {visible.map(listRow)}
        </div>
      )}
    </div>
  );
}
window.ScreenDesk = ScreenDesk;
