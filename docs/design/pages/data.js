/* ============================================================
   Criptotrade — mock data (deterministic)
   Attaches CT.* to window. Plain JS (no JSX).
   ============================================================ */
(function () {
  // ---- seeded RNG (mulberry32) ----
  function rng(seed) {
    let a = seed >>> 0;
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  // ---- OHLCV candle series (BTC/USDT-ish around 67k) ----
  function makeCandles(n, seed, base) {
    const r = rng(seed);
    const out = [];
    let price = base;
    for (let i = 0; i < n; i++) {
      const drift = Math.sin(i / 9) * 140 + Math.sin(i / 23) * 320;
      const vol = 180 + r() * 260;
      const open = price;
      const move = (r() - 0.46) * vol + drift * 0.06;
      let close = open + move;
      const high = Math.max(open, close) + r() * vol * 0.6;
      const low = Math.min(open, close) - r() * vol * 0.6;
      const volume = 40 + r() * 120 + (Math.abs(move) / vol) * 80;
      out.push({ i, open, close, high, low, volume });
      price = close;
    }
    return out;
  }

  const candles = makeCandles(70, 7, 65200);
  const last = candles[candles.length - 1];
  const price = last.close;

  // bollinger bands over candles (period 20)
  function bollinger(data, p = 20, k = 2) {
    return data.map((c, idx) => {
      if (idx < p - 1) return { i: c.i, mid: null, up: null, low: null };
      const slice = data.slice(idx - p + 1, idx + 1).map(x => x.close);
      const mean = slice.reduce((a, b) => a + b, 0) / p;
      const sd = Math.sqrt(slice.reduce((a, b) => a + (b - mean) ** 2, 0) / p);
      return { i: c.i, mid: mean, up: mean + k * sd, low: mean - k * sd };
    });
  }
  const bb = bollinger(candles);

  // RSI line
  function makeLine(n, seed, lo, hi, smooth) {
    const r = rng(seed); const out = []; let v = (lo + hi) / 2;
    for (let i = 0; i < n; i++) { v += (r() - 0.5) * (hi - lo) / smooth; v = Math.max(lo, Math.min(hi, v)); out.push(v); }
    return out;
  }

  const CT = {};
  CT.rng = rng;
  CT.makeLine = makeLine;

  CT.symbol = {
    pair: 'BTC/USDT', price: price, change24h: 2.34, changeUsd: 1532.40,
    high24h: price + 980, low24h: price - 1420, volume24h: '1.84B',
  };
  CT.candles = candles;
  CT.bb = bb;

  // ---- regime ----
  CT.regime = {
    current: 'sideways', // sideways | strong_uptrend | strong_downtrend | chaotic
    confidence: 0.71,
    label: 'Lateral', strategy: 'Grid',
    options: [
      { key: 'sideways', label: 'Lateral', strat: 'Grid', desc: 'Mercado sem tendência definida' },
      { key: 'strong_uptrend', label: 'Alta forte', strat: 'DCA', desc: 'Tendência de alta consistente' },
      { key: 'strong_downtrend', label: 'Baixa forte', strat: '— (sem long)', desc: 'Tendência de baixa' },
      { key: 'chaotic', label: 'Caótico', strat: '— (sem trade)', desc: 'Volatilidade extrema' },
    ],
    extreme: null, // 'EUFORIA' | 'PANICO' | null
  };

  // ---- indicators ----
  CT.indicators = {
    rsi: 48.6,
    rsiSeries: [42,45,51,55,49,46,44,47,52,56,53,49,47,45,48.6],
    macd: { macd: 38.2, signal: 52.7, hist: -14.5 },
    macdHist: [22,18,9,-4,-12,-19,-22,-17,-9,-3,-8,-13,-16,-14.5],
    stoch: { k: 31.4, d: 38.9 },
    bollPctB: 0.38,
    atr: 612.40,
    atrPctOfPrice: 0.92,
    ema9: price - 120, ema21: price - 60,
    sma20: price + 40, sma50: price + 380, sma200: price - 2100,
    obv: 'distribuição', obvTrend: -1,
    volumeRatio: 0.84,
  };

  // ---- support / resistance ----
  CT.sr = {
    resistance: [
      { price: price + 1850, strength: 4, touches: 4 },
      { price: price + 920, strength: 3, touches: 3 },
    ],
    support: [
      { price: price - 760, strength: 5, touches: 5 },
      { price: price - 1640, strength: 2, touches: 2 },
    ],
    fib: [
      { level: 0, price: price + 1850 },
      { level: 23.6, price: price + 1180 },
      { level: 38.2, price: price + 720 },
      { level: 50, price: price + 130 },
      { level: 61.8, price: price - 470 },
      { level: 78.6, price: price - 1180 },
      { level: 100, price: price - 1900 },
    ],
  };

  // ---- volume profile ----
  CT.volumeProfile = (function () {
    const r = rng(31); const bins = 22; const out = [];
    const lo = price - 2400, hi = price + 2200;
    for (let i = 0; i < bins; i++) {
      const p = lo + (hi - lo) * (i / (bins - 1));
      const dist = Math.exp(-Math.pow((p - (price - 200)) / 900, 2));
      out.push({ price: p, vol: dist * 100 + r() * 18 });
    }
    const maxBin = out.reduce((m, b) => (b.vol > m.vol ? b : m), out[0]);
    return {
      bins: out,
      poc: maxBin.price,
      vah: price + 540,
      val: price - 980,
      lvn: [price + 1200, price - 1850],
    };
  })();

  // ---- detected patterns ----
  CT.patterns = [
    { name: 'Retângulo (consolidação)', dir: 'neutral', confidence: 0.78, target: price + 60, note: 'Faixa lateral entre suporte e resistência' },
    { name: 'Triângulo Ascendente', dir: 'up', confidence: 0.64, target: price + 1620, note: 'Topos planos, fundos ascendentes' },
    { name: 'Double Bottom', dir: 'up', confidence: 0.52, target: price + 980, note: 'Dois fundos próximos a $' + Math.round(price - 760).toLocaleString() },
  ];

  // ---- current signal ----
  CT.signal = {
    action: 'buy', strategy: 'grid', confidence: 0.71,
    entry: price - 40, stop: price - 760, takeProfit: price + 920, sizePct: 2.4,
    rr: 2.6, notional: 1240, at: '14:32:08',
  };

  // ---- multi-timeframe confluence ----
  CT.confluence = {
    aligned: false,
    direction: null,
    timeframes: [
      { tf: '1h', trend: 'bullish', rsi: 48.6, macd_hist: -14.5, regime: 'sideways', rsi_divergence: null, macd_divergence: null },
      { tf: '4h', trend: 'bullish', rsi: 55.2, macd_hist: 8.1, regime: 'strong_uptrend', rsi_divergence: null, macd_divergence: 'bullish_divergence' },
      { tf: '1d', trend: 'bearish', rsi: 61.0, macd_hist: 3.2, regime: 'strong_uptrend', rsi_divergence: 'bearish_divergence', macd_divergence: null },
    ],
  };

  // ---- confidence breakdown (5 factors) ----
  CT.confidenceBreakdown = [
    { key: 'Alinhamento de tendência', weight: 0.25, score: 0.58 },
    { key: 'Confluência de indicadores', weight: 0.30, score: 0.74 },
    { key: 'Proximidade de S/R', weight: 0.20, score: 0.81 },
    { key: 'Confirmação de volume', weight: 0.15, score: 0.62 },
    { key: 'Divergência RSI/MACD', weight: 0.10, score: 0.88 },
  ];

  // ---- capital / risk ----
  CT.capital = {
    initial: 10000,
    value: 11842.60,
    pnlPct: 18.43,
    exposurePct: 14.2,
    openPositions: 2,
  };

  CT.drawdown = {
    daily:   { value: -1.2, limit: -3,  status: 'ok',   action: 'Pausa trading pelo dia' },
    weekly:  { value: -3.4, limit: -6,  status: 'warn', action: 'Reduz posições à metade' },
    monthly: { value: -7.1, limit: -15, status: 'ok',   action: 'Suspende e exige revisão' },
    overallStatus: 'warn', // ok | warn | paused_daily | reduced_weekly | suspended_monthly
  };

  // equity curve + drawdown series
  CT.equity = (function () {
    const r = rng(11); const out = []; let eq = 10000; let peak = 10000;
    for (let i = 0; i < 90; i++) {
      eq += (r() - 0.42) * 130 + Math.sin(i / 12) * 22;
      eq = Math.max(9200, eq);
      peak = Math.max(peak, eq);
      out.push({ i, equity: eq, dd: (eq - peak) / peak * 100 });
    }
    out[out.length - 1].equity = 11842.6;
    return out;
  })();

  CT.circuitBreaker = {
    status: 'closed', // closed | open
    triggers: [
      { key: 'Perda diária ≥ -4%', value: -1.8, limit: -4, hit: false },
      { key: '3 perdas consecutivas', value: 1, limit: 3, hit: false },
    ],
    cooldownHours: 24, cooldownRemaining: 0,
  };

  CT.kelly = {
    winRate: 0.586, avgWinPct: 2.84, avgLossPct: 1.62,
    fullKelly: 0.331, fraction: 0.25, fractionalKelly: 0.083,
    riskOfRuin: 2.4, // %
    trades: 142,
  };

  CT.riskConfig = {
    kellyFraction: 0.25,
    minPositionPct: 0.5,
    maxPositionPct: 5,
    ddDaily: 3, ddWeekly: 6, ddMonthly: 15,
  };

  // ---- guardrails (Risk Agent) ----
  CT.guardrails = [
    { key: 'Volatilidade (ATR/BB)', limit: '≤ 10%', value: '6.2%', ok: true },
    { key: 'Liquidez (volume ratio)', limit: '≥ 0.3', value: '0.84', ok: true },
    { key: 'Tamanho de posição', limit: '≤ 5%', value: '2.4%', ok: true },
    { key: 'Stop loss obrigatório', limit: 'presente', value: 'definido', ok: true },
    { key: 'Risk/reward', limit: '≥ 2.5×', value: '2.6×', ok: true },
  ];

  // ---- behavioral guard ----
  CT.behavioral = [
    { key: 'Revenge trading', desc: 'Tamanho 50%+ maior após 2 perdas', status: 'ok', detail: 'Sem padrão detectado' },
    { key: 'Euforia', desc: 'Tamanho 20%+ maior após 3 vitórias', status: 'warn', detail: 'Último trade +18% acima da média', action: 'Forçar Kelly half' },
    { key: 'Overconfidence', desc: 'Confiança acima do win rate real', status: 'ok', detail: 'Confiança 71% · win rate 59%' },
  ];

  // ---- agents ----
  CT.agents = [
    { id: 'strategy', name: 'Strategy Agent', domain: 'trading', status: 'active', implemented: true, cycles: 142, last: '14:32:08', desc: 'Detecta regime e gera sinais' },
    { id: 'risk', name: 'Risk Agent', domain: 'security', status: 'active', implemented: true, cycles: 142, last: '14:32:09', desc: 'Valida guardrails e proteções' },
    { id: 'execution', name: 'Execution Agent', domain: 'trading', status: 'idle', implemented: true, cycles: 38, last: '14:30:51', desc: 'Executa ordens (paper)' },
    { id: 'behavioral', name: 'Behavioral Guard', domain: 'security', status: 'active', implemented: true, cycles: 142, last: '14:32:09', desc: 'Detecta vieses comportamentais' },
    { id: 'orchestrator', name: 'Orchestrator', domain: 'orchestration', status: 'active', implemented: true, cycles: 142, last: '14:32:10', desc: 'Coordena o pipeline de ciclo' },
    { id: 'auditor', name: 'Auditor Agent', domain: 'security', status: 'not_implemented', implemented: false, cycles: 0, last: null, desc: 'Auditoria de conformidade' },
  ];

  // ---- strategies config ----
  CT.strategies = {
    grid: { levels: 10, spacingPct: 1.0, allocPct: 10, regime: 'sideways' },
    dca: { entries: 3, spacingPct: 1.5, stopPct: 8, rsiOversold: 35, regime: 'sideways, strong_uptrend' },
    meanReversion: { rsiOversold: 30, rsiOverbought: 70, atrMult: 2.0, minRR: 2.0 },
  };

  // ---- orders ----
  const _ords = [];
  const pairs = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT'];
  const str016 = ['grid', 'dca', 'mean_reversion'];
  const statuses = ['pending', 'pending', 'approved', 'filled', 'filled', 'filled', 'rejected', 'cancelled', 'filled', 'filled', 'filled', 'filled'];
  const ro = rng(99);
  for (let i = 0; i < 22; i++) {
    const side = ro() > 0.42 ? 'buy' : 'sell';
    const pair = pairs[Math.floor(ro() * pairs.length)];
    const px = pair === 'BTC/USDT' ? price : pair === 'ETH/USDT' ? 3420 : 168;
    const qty = +(pair === 'BTC/USDT' ? (0.01 + ro() * 0.04) : pair === 'ETH/USDT' ? (0.2 + ro() * 0.8) : (3 + ro() * 12)).toFixed(4);
    const st = i < 2 ? 'pending' : statuses[i % statuses.length];
    const conf = +(0.5 + ro() * 0.42).toFixed(2);
    const sizePct = +(0.8 + ro() * 3.6).toFixed(1);
    const notional = +(px * qty).toFixed(2);
    const hh = 14 - Math.floor(i / 3); const mm = (50 - i * 4 + 60) % 60;
    _ords.push({
      id: 'ord_' + (3480 - i),
      pair, side, quantity: qty, price: px, notional,
      status: st, strategy: str016[Math.floor(ro() * 3)], agent_id: 'strategy',
      confidence: conf, sizePct,
      stop: side === 'buy' ? +(px * 0.97).toFixed(2) : +(px * 1.03).toFixed(2),
      takeProfit: side === 'buy' ? +(px * 1.08).toFixed(2) : +(px * 0.92).toFixed(2),
      rr: +(2.4 + ro() * 0.8).toFixed(1),
      reason: side === 'buy'
        ? 'RSI saindo de sobrevendido + suporte forte testado; confluência de volume confirma entrada.'
        : 'Resistência rejeitada com divergência de MACD; realização parcial recomendada.',
      auto_approved: st === 'filled' && conf > 0.7,
      critical: i === 1,
      operator: (st === 'approved' || st === 'rejected') ? 'operador' : null,
      operatorNote: st === 'rejected' ? 'Volatilidade alta antes de evento macro.' : null,
      created_at: `2026-06-08 ${String(hh).padStart(2, '0')}:${String(mm).padStart(2, '0')}:0${i % 10}`,
    });
  }
  CT.orders = _ords;
  CT.pendingOrders = _ords.filter(o => o.status === 'pending');

  // ---- HITL config ----
  CT.hitl = {
    level: 2, threshold: 1000,
    pending: CT.pendingOrders.length, approvedToday: 7, rejectedToday: 2,
    decisionTimeout: 300,
    levels: [
      { level: 0, threshold: 0, desc: 'Manual total — toda ordem exige aprovação' },
      { level: 1, threshold: 500, desc: 'Semiautônomo baixo' },
      { level: 2, threshold: 1000, desc: 'Semiautônomo médio' },
      { level: 3, threshold: 5000, desc: 'Semiautônomo alto (críticas ainda exigem humano)' },
    ],
  };

  // ---- journal ----
  const jr = rng(55);
  const setups = ['Grid · suporte', 'DCA · pullback', 'Mean reversion · RSI<30', 'Breakout triângulo', 'Double bottom'];
  const _journal = [];
  for (let i = 0; i < 16; i++) {
    const before = 1 + Math.floor(jr() * 10);
    const followed = jr() > 0.34;
    const pnl = +(((followed ? 1 : -1) * (jr() * 4) + (before > 6 ? -0.6 : 0.4))).toFixed(2);
    const after = Math.max(1, Math.min(10, Math.round(before + pnl)));
    _journal.push({
      id: i, date: `06/${String(8 - Math.floor(i / 3)).padStart(2, '0')}`,
      setup: setups[Math.floor(jr() * setups.length)],
      before, after, stopDefined: jr() > 0.15, followed,
      pnl, note: followed ? 'Plano seguido' : 'Desviou do plano',
    });
  }
  CT.journal = _journal;
  CT.journalMetrics = {
    byEmotion: [
      { band: '1–3', label: 'Baixo', winRate: 0.71, trades: 5 },
      { band: '4–6', label: 'Neutro', winRate: 0.62, trades: 7 },
      { band: '7–10', label: 'Alto', winRate: 0.38, trades: 4 },
    ],
    planFollowedPnl: 2.14,
    planDeviatedPnl: -1.38,
    disciplineCorrelation: 0.67,
    realWinRate: 0.586,
  };
  // scatter emotion x pnl
  CT.journalScatter = _journal.map(j => ({ x: j.before, y: j.pnl, followed: j.followed }));
  // heatmap day x hour
  CT.heatmap = (function () {
    const days = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'];
    const hr = rng(77); const out = [];
    for (let d = 0; d < 7; d++) for (let h = 0; h < 12; h++) {
      out.push({ day: d, dayLabel: days[d], hour: 8 + h, winRate: hr() });
    }
    return { days, data: out };
  })();

  // ---- backtest ----
  CT.backtest = {
    totalTrades: 142, winRate: 0.586, pnlUsd: 1842.6, pnlPct: 18.43,
    maxDrawdown: -7.1, sharpe: 1.84, profitFactor: 2.12,
    avgWin: 2.84, avgLoss: -1.62, expectancy: 0.94,
    equity: CT.equity,
  };
  CT.monteCarlo = (function () {
    const r = rng(123); const sims = []; const N = 1000;
    for (let i = 0; i < N; i++) {
      let v = 0; for (let t = 0; t < 142; t++) v += (r() - 0.41) * 1.6;
      sims.push(v * 10 + 1840);
    }
    sims.sort((a, b) => a - b);
    const pct = q => sims[Math.floor(q * N)];
    // histogram
    const lo = sims[0], hi = sims[N - 1]; const bins = 28; const hist = new Array(bins).fill(0);
    sims.forEach(s => { let b = Math.floor((s - lo) / (hi - lo) * (bins - 1)); hist[b]++; });
    return {
      n: N,
      p5: pct(0.05), p50: pct(0.5), p95: pct(0.95),
      profitablePct: sims.filter(s => s > 0).length / N,
      rejected: pct(0.05) < 0,
      hist, lo, hi, bins,
    };
  })();
  CT.walkForward = {
    valid: true, windows: 6, windowSize: 252,
    sharpeDeviation: 0.18, threshold: 0.30,
    folds: [
      { fold: 1, trainSharpe: 1.92, testSharpe: 1.71 },
      { fold: 2, trainSharpe: 1.84, testSharpe: 1.62 },
      { fold: 3, trainSharpe: 2.01, testSharpe: 1.88 },
      { fold: 4, trainSharpe: 1.76, testSharpe: 1.59 },
      { fold: 5, trainSharpe: 1.95, testSharpe: 1.74 },
      { fold: 6, trainSharpe: 1.88, testSharpe: 1.81 },
    ],
  };
  CT.backtestConfig = {
    initialCapital: 10000, commissionPct: 0.1, slippageBps: 5,
    walkForwardWindow: 252, monteCarloSims: 1000,
  };

  // ---- alerts ----
  CT.alerts = [
    { id: 'a1', severity: 'medium', type: 'behavioral', message: 'Euforia detectada — tamanho 18% acima da média após 3 vitórias.', agent_id: 'behavioral', pair: 'BTC/USDT', auto_action: 'Kelly half forçado', at: '14:28:41' },
    { id: 'a2', severity: 'low', type: 'guardrail', message: 'Risk/reward 2.6× aprovado (mínimo 2.5×).', agent_id: 'risk', pair: 'BTC/USDT', auto_action: null, at: '14:32:08' },
    { id: 'a3', severity: 'high', type: 'drawdown', message: 'Drawdown semanal em -3.4% (limite -6%) — atenção.', agent_id: 'risk', pair: null, auto_action: null, at: '13:02:11' },
    { id: 'a4', severity: 'low', type: 'regime', message: 'Regime confirmado como lateral — estratégia Grid ativa.', agent_id: 'strategy', pair: 'BTC/USDT', auto_action: 'Ativar Grid', at: '12:40:55' },
    { id: 'a5', severity: 'critical', type: 'guardrail', message: 'Ordem rejeitada: stop loss ausente em ordem manual.', agent_id: 'risk', pair: 'ETH/USDT', auto_action: 'Ordem bloqueada', at: '11:18:03' },
    { id: 'a6', severity: 'low', type: 'risk', message: 'Risco de ruína recalculado: 2.4% (alerta acima de 5%).', agent_id: 'risk', pair: null, auto_action: null, at: '10:55:22' },
  ];

  CT.alertThresholds = {
    revengeSize: 50, euphoriaSize: 20, overconfidenceGap: 15, riskOfRuin: 5,
  };

  window.CT = CT;
})();
