/* ============================================================
   Criptotrade — data extensions (multi-cripto, metrics, process,
   per-agent config) + global pair store (CT_PAIR).
   Plain JS. Loads AFTER data.js, extends window.CT.
   ============================================================ */
(function () {
  const CT = window.CT;
  const btc = CT.symbol.price;
  const clk = (h, m, s) => [h, m, s].map(n => String(n).padStart(2, '0')).join(':');

  /* ---- tradable pairs (← GET /v1/market/pairs) ---- */
  CT.pairs = [
    { symbol: 'BTC/USDT', base: 'BTC', glyph: '₿', color: '#F7931A', price: btc,      change24h: 2.34,  decimals: 2 },
    { symbol: 'ETH/USDT', base: 'ETH', glyph: 'Ξ', color: '#627EEA', price: 3420.18,  change24h: -1.12, decimals: 2 },
    { symbol: 'SOL/USDT', base: 'SOL', glyph: '◎', color: '#22B07D', price: 168.42,   change24h: 4.87,  decimals: 2 },
  ];
  CT.pairBy = Object.fromEntries(CT.pairs.map(p => [p.symbol, p]));

  /* ---- portfolio / per-symbol metrics (← GET /v1/metrics) ----
     ratio fields may be null → render "Sem dados" (≠ 0) */
  CT.metricsBySymbol = {
    ALL:        { sharpe_ratio: 1.84, win_rate: 0.586, max_drawdown: -7.1,  profit_factor: 2.12, total_trades: 142, open_positions: 2, portfolio_value_usdt: 11842.6, pnl_period_usdt: 1842.6, pnl_period_pct: 18.43, exposure_pct: 14.2, has_data: true },
    'BTC/USDT': { sharpe_ratio: 1.92, win_rate: 0.61,  max_drawdown: -6.2,  profit_factor: 2.34, total_trades: 88,  open_positions: 1, portfolio_value_usdt: 7320.4,  pnl_period_usdt: 1180.2, pnl_period_pct: 19.2,  exposure_pct: 9.1,  has_data: true },
    'ETH/USDT': { sharpe_ratio: null, win_rate: 0.52,  max_drawdown: -9.4,  profit_factor: null, total_trades: 12,  open_positions: 1, portfolio_value_usdt: 3120.0,  pnl_period_usdt: 412.4,  pnl_period_pct: 13.2,  exposure_pct: 5.1,  has_data: true },
    'SOL/USDT': { sharpe_ratio: 1.41, win_rate: 0.55,  max_drawdown: -11.2, profit_factor: 1.78, total_trades: 42,  open_positions: 0, portfolio_value_usdt: 1402.2,  pnl_period_usdt: 250.0,  pnl_period_pct: 21.7,  exposure_pct: 0,    has_data: true },
  };

  const PERIOD_FACTOR = { '1d': 0.06, '7d': 0.28, '30d': 1, '90d': 2.3, all: 3.0 };
  const PERIOD_LEN    = { '1d': 8,    '7d': 18,   '30d': 45, '90d': 90,  all: 90 };

  /* metrics scaled by period; short windows → not enough sample → null ratios */
  CT.getMetrics = function (symbol, period) {
    const base = CT.metricsBySymbol[symbol] || CT.metricsBySymbol.ALL;
    const f = PERIOD_FACTOR[period] != null ? PERIOD_FACTOR[period] : 1;
    const trades = Math.max(0, Math.round(base.total_trades * f));
    const m = Object.assign({}, base, {
      total_trades: trades,
      pnl_period_usdt: +(base.pnl_period_usdt * f).toFixed(2),
      pnl_period_pct: +(base.pnl_period_pct * (f < 1 ? f / 0.5 : 1)).toFixed(2),
    });
    if (trades < 20) { m.sharpe_ratio = null; m.profit_factor = null; }
    if (trades < 6)  { m.win_rate = null; }
    return m;
  };

  /* equity series (← GET /v1/metrics/equity), scaled per symbol + period */
  CT.getEquity = function (symbol, period) {
    const len = PERIOD_LEN[period] != null ? PERIOD_LEN[period] : 90;
    const frac = (CT.metricsBySymbol[symbol] && CT.metricsBySymbol[symbol].portfolio_value_usdt || 11842.6) / 11842.6;
    const slice = CT.equity.slice(-len);
    const base = slice[0].equity;
    return slice.map((d, i) => ({ i, equity: +(d.equity * frac).toFixed(2), dd: d.dd }));
  };

  /* ---- process / observability events (← GET /v1/process/events) ----
     XES cycle log: agent_cycle_started / completed / failed */
  CT.processEvents = (function () {
    const r = CT.rng(2026);
    const order = ['strategy', 'risk', 'behavioral', 'execution', 'orchestrator'];
    const names = { strategy: 'Strategy', risk: 'Risk', behavioral: 'Behavioral', execution: 'Execution', orchestrator: 'Orchestrator' };
    const out = [];
    let cyc = 142;
    let mm = 32, hh = 14;
    for (let i = 0; i < 18; i++) {
      const failed = i === 2 || i === 9;
      const skippedExec = i === 6 || i === 13;
      const ags = order.map(a => {
        let st = 'completed';
        if (failed && a === 'execution') st = 'failed';
        else if (skippedExec && a === 'execution') st = 'skipped';
        const dur = st === 'skipped' ? 0 : Math.round((a === 'orchestrator' ? 18 : a === 'strategy' ? 140 : 70) + r() * 120);
        return { id: a, name: names[a], status: st, duration_ms: dur };
      });
      const total = ags.reduce((s, a) => s + a.duration_ms, 0);
      const signals = failed ? 0 : (r() > 0.55 ? 1 : 0);
      out.push({
        cycle: cyc,
        started_at: clk(hh, mm, Math.floor(r() * 60)),
        duration_ms: total,
        status: failed ? 'failed' : 'completed',
        agents: ags,
        signals,
        orders: failed ? 0 : (signals && r() > 0.4 ? 1 : 0),
        regime: i % 5 === 0 ? 'strong_uptrend' : 'sideways',
        error: failed ? 'ExecutionAgent: timeout ao montar ordem paper (retry esgotado)' : null,
      });
      cyc -= 1; mm -= 1; if (mm < 0) { mm += 60; hh -= 1; }
    }
    return out;
  })();

  CT.processSummary = (function () {
    const ev = CT.processEvents;
    const fails = ev.filter(e => e.status === 'failed').length;
    const avg = Math.round(ev.reduce((s, e) => s + e.duration_ms, 0) / ev.length);
    return {
      cyclesToday: 142,
      successRate: (ev.length - fails) / ev.length,
      avgDurationMs: avg,
      failures: fails,
      lastCycleAt: ev[0].started_at,
      loopRunning: true,
      intervalS: 60,
    };
  })();

  /* ---- per-agent dynamic config (← GET/PATCH /v1/agents/{id}/config) ---- */
  CT.agentParams = {
    strategy: [
      { key: 'min_confidence',  label: 'Confiança mínima do sinal', type: 'slider', value: 0.60, min: 0.30, max: 0.95, step: 0.05, fmt: 'pct',  hint: 'Abaixo disso o sinal é descartado' },
      { key: 'rsi_period',      label: 'Período do RSI',            type: 'num',    value: 14,   min: 5,    max: 50,   step: 1 },
      { key: 'regime_lookback', label: 'Lookback de regime',        type: 'num',    value: 120,  min: 30,   max: 500,  step: 10, suffix: 'candles' },
      { key: 'signal_cooldown', label: 'Cooldown entre sinais',     type: 'num',    value: 3,    min: 0,    max: 20,   step: 1,  suffix: 'ciclos' },
    ],
    risk: [
      { key: 'max_position_pct',  label: 'Tamanho máximo de posição', type: 'slider', value: 5,   min: 1,  max: 20, step: 0.5, fmt: 'pct_direct', sensitive: true },
      { key: 'min_rr',            label: 'Risk/reward mínimo',         type: 'num',    value: 2.5, min: 1,  max: 5,  step: 0.1, suffix: '×', decimals: 1, sensitive: true },
      { key: 'max_volatility_pct',label: 'Volatilidade máxima (ATR)',  type: 'slider', value: 10,  min: 2,  max: 30, step: 1,   fmt: 'pct_direct' },
      { key: 'require_stop',      label: 'Exigir stop loss',           type: 'toggle', value: true, sensitive: true },
    ],
    execution: [
      { key: 'max_slippage_bps', label: 'Slippage máximo tolerado', type: 'num',    value: 8,   min: 0, max: 50, step: 1, suffix: 'bps' },
      { key: 'retry_attempts',   label: 'Tentativas em falha',      type: 'num',    value: 3,   min: 0, max: 10, step: 1 },
      { key: 'order_type',       label: 'Tipo de ordem',            type: 'select', value: 'limit', options: [{ value: 'limit', label: 'Limit' }, { value: 'market', label: 'Market' }] },
    ],
    behavioral: [
      { key: 'revenge_size_pct',  label: 'Limiar revenge trading', type: 'slider', value: 50, min: 10, max: 200, step: 5, fmt: 'pct_direct', hint: 'Tamanho maior que isto após 2 perdas' },
      { key: 'euphoria_size_pct', label: 'Limiar euforia',          type: 'slider', value: 20, min: 5,  max: 100, step: 5, fmt: 'pct_direct' },
      { key: 'force_kelly_half',  label: 'Forçar Kelly half',       type: 'toggle', value: true, sensitive: true },
    ],
    orchestrator: [
      { key: 'cycle_interval_s', label: 'Intervalo do ciclo',     type: 'num',    value: 60,   min: 10,  max: 3600,  step: 10,  suffix: 's', sensitive: true },
      { key: 'parallel_agents',  label: 'Agentes em paralelo',    type: 'toggle', value: false },
      { key: 'max_cycle_ms',     label: 'Timeout do ciclo',       type: 'num',    value: 5000, min: 500, max: 30000, step: 500, suffix: 'ms' },
    ],
  };

  /* alerts config defaults — PATCH /v1/alerts/config é write-only (sem GET) */
  CT.alertsConfigReadback = false;

  /* ============================================================
     Global pair store — single source of truth (window.CT_PAIR)
     Value is a pair symbol OR 'ALL' (portfólio). Broadcasts ct:pair.
     ============================================================ */
  window.CT_PAIR = (function () {
    const KEY = 'ct_pair';
    let cur = 'BTC/USDT';
    try { const s = localStorage.getItem(KEY); if (s) cur = s; } catch (e) {}
    return {
      get() { return cur; },
      set(p) {
        if (p === cur) return;
        cur = p;
        try { localStorage.setItem(KEY, p); } catch (e) {}
        window.dispatchEvent(new CustomEvent('ct:pair', { detail: p }));
      },
    };
  })();
})();
