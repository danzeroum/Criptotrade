/* ============================================================
   Criptotrade — Screen: Market Analysis
   ============================================================ */
const { useState, useEffect, useMemo } = React;

const REGIME_VARIANT = {
  sideways:          'neutral',
  strong_uptrend:    'ok',
  strong_downtrend:  'down',
  chaotic:           'warn',
  unknown:           'neutral',
};

const REGIME_LABEL = {
  sideways:         'Lateral',
  strong_uptrend:   'Alta forte',
  strong_downtrend: 'Baixa forte',
  chaotic:          'Caótico',
  unknown:          'Desconhecido',
};

function IndicatorRow({ label, value, unit, variant }) {
  return (
    <div className="stat-row">
      <span className="stat-k">{label}</span>
      <span className={`stat-v${variant ? ' ' + variant : ''}`}>
        {value}{unit}
      </span>
    </div>
  );
}

function SRLevelRow({ label, price, strength, color }) {
  return (
    <div className="stat-row">
      <span className="stat-k">{label}</span>
      <span className="stat-v" style={{ color, fontFamily: 'var(--mono)' }}>
        {fmtUsd(price)}
        <span style={{ color: 'var(--ink-4)', fontSize: 11, marginLeft: 6 }}>
          {'★'.repeat(Math.min(5, Math.round(strength ?? 0)))}
        </span>
      </span>
    </div>
  );
}

// Static regime legend — the set of regimes is a fixed enum (antes vinha do mock global).
const REGIME_OPTIONS = [
  { key: 'strong_uptrend', label: 'Alta forte', desc: 'Tendência de alta consistente', strat: 'Trend-following' },
  { key: 'strong_downtrend', label: 'Baixa forte', desc: 'Tendência de baixa consistente', strat: 'Trend-following (venda)' },
  { key: 'sideways', label: 'Lateral', desc: 'Sem tendência; oscila numa faixa', strat: 'Mean-reversion / Grid' },
  { key: 'chaotic', label: 'Caótico', desc: 'Volatilidade alta sem direção', strat: 'Aguardar (stand-aside)' },
];

function ScreenMarket({ navigate, addToast } = {}) {
  const [pair, setPair] = useState(CT_PAIR.get());
  const [tf, setTf] = useState('1h');
  const [pairs, setPairs] = useState(null);

  const [candles,       setCandles]       = useState(null);
  const [bb,            setBb]            = useState(null);
  const [indicators,    setIndicators]    = useState(null);
  const [regime,        setRegime]        = useState(null);
  const [levels,        setLevels]        = useState(null);
  const [volumeProfile, setVolumeProfile] = useState(null);
  const [patterns,      setPatterns]      = useState(null);
  const [signal,        setSignal]        = useState(null);
  const [confluence,    setConfluence]    = useState(null);  // M12
  const [ticker,        setTicker]        = useState(null);
  const [loading,       setLoading]       = useState(true);
  const [error,         setError]         = useState(null);
  const [auto,          setAuto]          = useState(false);   // M3: auto-refresh
  const [showFactors,   setShowFactors]   = useState(false);   // M6: confidence breakdown
  const [showBB,        setShowBB]        = useState(true);    // M4: Bollinger overlay
  const [ordering,      setOrdering]      = useState(false);   // M13: paper-order confirm

  // Mercado exige um par concreto; se o escopo global for 'ALL', usa o default.
  const effPair = effectivePair(pair, pairs);

  const load = () => {
    setLoading(true);
    Promise.all([
      CT_API.getCandles(effPair, tf, 70),
      CT_API.getIndicators(effPair),
      CT_API.getRegime(effPair),
      CT_API.getLevels(effPair),
      CT_API.getVolumeProfile(effPair),
      CT_API.getPatterns(effPair),
      CT_API.getSignal(effPair),
      CT_API.getTicker(effPair).catch(() => null),       // non-critical: never fail the load
      CT_API.getConfluence(effPair).catch(() => null),   // non-critical: MTF strip (M12)
    ])
      .then(([c, ind, reg, lvl, vp, pat, sig, tk, conf]) => {
        setCandles(c);
        setIndicators(ind);
        setRegime(reg);
        setLevels(lvl);
        setVolumeProfile(vp);
        setPatterns(Array.isArray(pat) ? pat : []);
        setSignal(sig);
        setTicker(tk);
        setConfluence(conf);
        setLoading(false);
      })
      .catch(e => { setError(e); setLoading(false); });
  };

  // Source the dropdown from the allowlist and let other screens (the header)
  // drive the pair too. The store is the single source of truth for `pair`.
  useEffect(() => {
    loadPairs().then(setPairs);
    return CT_PAIR.subscribe(setPair);
  }, []);

  useEffect(() => { load(); }, [effPair, tf]);

  // M3: auto-refresh on an interval, without flashing the full-screen spinner.
  useEffect(() => {
    if (!auto) return;
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, [auto, effPair, tf]);

  // M4: Bollinger series derived client-side from the fetched candles.
  const bbSeries = useMemo(() => (candles ? computeBB(candles) : []), [candles]);

  // M13: fire stored price alerts when the live ticker crosses them (client-side MVP).
  useEffect(() => {
    if (ticker?.last == null) return;
    let list;
    try { list = JSON.parse(localStorage.getItem('ct.alerts') || '[]'); } catch (_) { return; }
    if (!Array.isArray(list) || !list.length) return;
    const price = ticker.last;
    const remaining = [];
    let fired = false;
    for (const a of list) {
      if (a.pair !== effPair) { remaining.push(a); continue; }
      const crossed = a.side === 'sell' ? price >= a.target : price <= a.target;
      if (crossed) { addToast?.(`Alerta: ${a.pair} cruzou ${fmtUsd(a.target)}.`, 'bell'); fired = true; }
      else remaining.push(a);
    }
    if (fired) { try { localStorage.setItem('ct.alerts', JSON.stringify(remaining)); } catch (_) { /* ignore */ } }
  }, [ticker, effPair]);

  // Full-screen spinner only on the first load; refreshes keep the cards visible.
  if (loading && !candles) return <LoadingState label="Carregando análise de mercado…" />;
  if (error)   return <ErrorState message="Erro ao carregar mercado" onRetry={() => { setError(null); load(); }} />;

  const lastClose = candles?.length ? candles[candles.length - 1].c : null;
  const ind = indicators;

  // M13: paper-order submission (prefilled from the signal) + price-alert creation.
  const submitOrder = () => {
    setOrdering(false);
    if (!signal || signal.action === 'hold' || signal.stop == null) return;
    const notional = (signal.position_size_pct ?? 2) / 100 * 10000;
    const body = {
      pair: effPair,
      side: signal.action,
      quantity: Math.max(0.0001, +(notional / (signal.entry || 1)).toFixed(6)),
      price: signal.entry,
      strategy: signal.strategy || 'manual',
      agent_id: 'manual-ui',
      confidence: signal.confidence ?? 0.5,
      reason: (signal.reason && signal.reason.length >= 10)
        ? signal.reason
        : 'Ordem simulada a partir do sinal de Mercado (paper).',
      position_size_pct: signal.position_size_pct ?? 2.0,
      stop_loss: signal.stop,
      ...(signal.take_profit != null ? { take_profit: signal.take_profit } : {}),
    };
    CT_API.createOrder(body)
      .then(() => addToast?.('Ordem paper enviada ao HITL.', 'check'))
      .catch((e) => addToast?.(`Falha ao enviar ordem: ${e?.message || 'erro'}`, 'alert'));
  };

  const createAlert = () => {
    const target = signal?.entry ?? ticker?.last ?? lastClose;
    if (target == null) return;
    try {
      const list = JSON.parse(localStorage.getItem('ct.alerts') || '[]');
      list.push({ pair: effPair, target, side: signal?.action || 'buy', createdAt: Date.now() });
      localStorage.setItem('ct.alerts', JSON.stringify(list));
    } catch (_) { /* private mode: ignore */ }
    addToast?.(`Alerta criado para ${effPair} em ${fmtUsd(target)}.`, 'bell');
  };

  const patternVariant = (d) => d === 'bullish' ? 'ok' : d === 'bearish' ? 'down' : 'neutral';
  const patternLabel = (d) => d === 'bullish' ? '↑' : d === 'bearish' ? '↓' : '→';

  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="page-title">Mercado</h1>
          <div className="page-sub">Análise técnica, regime e sinais de entrada</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {regime && (
            <Badge variant={REGIME_VARIANT[regime.regime] ?? 'neutral'}>
              {regime.label ?? REGIME_LABEL[regime.regime] ?? regime.regime}
              {' · '}{Math.round((regime.confidence ?? 0) * 100)}%
            </Badge>
          )}
          <PairSelect />
          <Seg
            options={[
              { value: '15m', label: '15m' },
              { value: '1h',  label: '1h' },
              { value: '4h',  label: '4h' },
              { value: '1d',  label: '1D' },
            ]}
            value={tf}
            onChange={setTf}
          />
          <Btn variant={auto ? '' : 'ghost'} size="sm" onClick={() => setAuto(a => !a)}
            aria-pressed={auto} aria-label="Atualização automática">
            {auto ? 'Auto · on' : 'Auto'}
          </Btn>
          <Btn variant="ghost" size="sm" onClick={load}>
            <Icon name="refresh" size={13} />
          </Btn>
        </div>
      </div>

      {/* Price KPIs */}
      <div className="grid grid-kpi5" style={{ marginBottom: 20 }}>
        <div className="card">
          <KPI label="Preço atual" value={lastClose} format="usd" icon="dollar" />
        </div>
        <div className="card">
          <KPI label="Variação 24h" value={ticker?.change_24h_pct} format="pct_direct" delta={ticker?.change_24h_pct} icon="trending" />
        </div>
        <div className="card">
          <KPI label="RSI" value={ind?.rsi != null ? fmtNum(ind.rsi, 1) : null} sub={ind?.rsi < 30 ? 'Sobrevendido' : ind?.rsi > 70 ? 'Sobrecomprado' : 'Neutro'} />
        </div>
        <div className="card">
          <KPI label="ATR" value={ind?.atr != null ? fmtNum(ind.atr, 0) : null} sub={`${fmtNum(ind?.atr_pct)}% do preço`} icon="activity" />
        </div>
        <div className="card">
          <KPI label="Estratégia ativa" value={regime?.active_strategy ?? '—'} />
        </div>
      </div>

      {/* Candle chart + Signal */}
      <div className="grid grid-chart-rail" style={{ marginBottom: 20 }}>
        <div className="card">
          <div className="card-head">
            <span className="card-title"><Icon name="candle" />{effPair} · {tf}</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <FreshnessBadge asOf={ticker?.as_of ?? signal?.as_of ?? indicators?.as_of ?? regime?.as_of} />
              <Btn variant={showBB ? '' : 'ghost'} size="sm" onClick={() => setShowBB(v => !v)}
                aria-pressed={showBB} aria-label="Alternar Bandas de Bollinger">
                BB
              </Btn>
            </div>
          </div>
          {/* C6: O/H/L/Vol of the latest candle; wraps freely on narrow widths.
              C7 guard: same pt-BR helpers as the rest of the screen (no raw
              toLocaleString), tabular figures for alignment. */}
          {candles && candles.length > 0 && (() => {
            const lc = candles[candles.length - 1];
            return (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6,
                padding: '10px 18px 0', fontVariantNumeric: 'tabular-nums' }}>
                <span className="chip">O <b>{fmtUsd(lc.o)}</b></span>
                <span className="chip">H <b>{fmtUsd(lc.h)}</b></span>
                <span className="chip">L <b>{fmtUsd(lc.lo ?? lc.l)}</b></span>
                <span className="chip">C <b>{fmtUsd(lc.c)}</b></span>
                <span className="chip">Vol <b>{fmtNum(lc.v, 0)}</b></span>
              </div>
            );
          })()}
          <div className="card-pad" style={{ padding: '14px 12px' }}>
            {candles && candles.length > 0 ? (
              <CandleChart
                candles={candles}
                bb={showBB ? bbSeries : []}
                height={280}
                tf={tf}
                pair={effPair}
              />
            ) : (
              <EmptyState label="Sem candles" />
            )}
          </div>
        </div>

        {/* Signal box */}
        {signal && (
          <div className="card">
            <div className="card-head">
              <span className="card-title"><Icon name="zap" />Sinal</span>
              <Badge variant={signal.action === 'buy' ? 'ok' : signal.action === 'sell' ? 'down' : 'neutral'}>
                {signal.action?.toUpperCase()}
              </Badge>
            </div>
            <div className="card-pad">
              <div style={{ marginBottom: 14 }}>
                <div className="stat-row">
                  <span className="stat-k">Entrada</span>
                  <span className="stat-v">{fmtUsd(signal.entry)}</span>
                </div>
                <div className="stat-row">
                  <span className="stat-k">Stop</span>
                  <span className="stat-v down">{fmtUsd(signal.stop)}</span>
                </div>
                <div className="stat-row">
                  <span className="stat-k">Alvo</span>
                  <span className="stat-v up">{fmtUsd(signal.take_profit)}</span>
                </div>
                <div className="stat-row">
                  <span className="stat-k">Tamanho</span>
                  <span className="stat-v">{signal.position_size_pct != null ? `${fmtNum(signal.position_size_pct, 1)}%` : '—'}</span>
                </div>
                <div className="stat-row">
                  <span className="stat-k">R/R</span>
                  <span className="stat-v" style={{ color: (signal.rr ?? 0) >= 2.5 ? 'var(--up)' : 'var(--warn)' }}>
                    {signal.rr != null ? `${fmtNum(signal.rr, 1)}×` : '—'}
                  </span>
                </div>
                <div className="stat-row">
                  <span className="stat-k">Confiança</span>
                  <span className="stat-v">{Math.round((signal.confidence ?? 0) * 100)}%</span>
                </div>
              </div>
              {signal.reason && (
                <p style={{ fontSize: 12, color: 'var(--ink-2)', lineHeight: 1.55 }}>{signal.reason}</p>
              )}
              {Array.isArray(signal.confidence_factors) && signal.confidence_factors.length > 0 && (
                <div style={{ marginTop: 12, borderTop: '1px solid var(--border)', paddingTop: 10 }}>
                  <button
                    onClick={() => setShowFactors(v => !v)}
                    aria-expanded={showFactors}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 4, width: '100%',
                      background: 'none', border: 'none', padding: '2px 0', cursor: 'pointer',
                      color: 'var(--ink-2)', fontSize: 11.5, fontWeight: 600,
                    }}
                  >
                    <Icon name={showFactors ? 'chevdown' : 'chevright'} size={12} />
                    Como calculamos a confiança
                  </button>
                  {showFactors && (
                    <div style={{ marginTop: 8 }}>
                      {signal.confidence_factors.map((f, i) => (
                        <div key={i} style={{ marginBottom: 9 }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11.5, marginBottom: 3 }}>
                            <span>{f.name}</span>
                            <span style={{ color: 'var(--ink-3)', fontFamily: 'var(--mono)' }}>
                              peso {Math.round((f.weight ?? 0) * 100)}%
                            </span>
                          </div>
                          <Meter value={(f.score ?? 0) * 100} max={100} warn={101} crit={101} />
                          {f.note && (
                            <div style={{ fontSize: 11, color: 'var(--ink-3)', marginTop: 2 }}>{f.note}</div>
                          )}
                        </div>
                      ))}
                      {signal.valid_until && (
                        <div style={{ fontSize: 11, color: 'var(--ink-3)', marginTop: 4 }}>
                          válido até {fmtTime(signal.valid_until)}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 14 }}>
                <Btn variant="primary" size="sm" onClick={() => {
                  // M2: carry the signal context so HITL highlights this pair's orders.
                  try { sessionStorage.setItem('ct.hitl.focus', effPair); } catch (_) { /* private mode */ }
                  navigate?.('hitl');
                }}>Ver no HITL</Btn>
                {signal.action !== 'hold' && signal.stop != null && (
                  ordering ? (
                    <>
                      <Btn variant="up" size="sm" onClick={submitOrder}>Confirmar paper</Btn>
                      <Btn variant="ghost" size="sm" onClick={() => setOrdering(false)}>Cancelar</Btn>
                    </>
                  ) : (
                    <Btn variant="ghost" size="sm" onClick={() => setOrdering(true)}>Simular ordem</Btn>
                  )
                )}
                <Btn variant="ghost" size="sm" onClick={createAlert}>Criar alerta</Btn>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Multi-timeframe confluence (M12) */}
      {confluence && Array.isArray(confluence.timeframes) && confluence.timeframes.length > 0 && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-head">
            <span className="card-title"><Icon name="activity" />Confluência multi-timeframe</span>
            <Badge variant={confluence.aligned ? (confluence.direction === 'bullish' ? 'ok' : 'down') : 'neutral'}>
              {confluence.aligned ? `Alinhado · ${confluence.direction === 'bullish' ? 'alta' : 'baixa'}` : 'Misto'}
            </Badge>
          </div>
          <div className="card-pad">
            <div className="grid grid-3" style={{ gap: 12 }}>
              {confluence.timeframes.map((s, i) => {
                const trendVariant = s.trend === 'bullish' ? 'ok' : s.trend === 'bearish' ? 'down' : 'neutral';
                const div = s.rsi_divergence || s.macd_divergence;
                return (
                  <div key={i} style={{ border: '1px solid var(--border)', borderRadius: 'var(--r-sm)', padding: '10px 12px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                      <span style={{ fontFamily: 'var(--mono)', fontWeight: 600 }}>{s.tf}</span>
                      <Badge variant={trendVariant}>
                        {s.trend === 'unknown' ? '—' : s.trend === 'bullish' ? '▲ alta' : '▼ baixa'}
                      </Badge>
                    </div>
                    <div className="stat-row"><span className="stat-k">RSI</span><span className="stat-v">{s.rsi != null ? fmtNum(s.rsi, 1) : '—'}</span></div>
                    <div className="stat-row"><span className="stat-k">Regime</span><span className="stat-v">{REGIME_LABEL[s.regime] ?? s.regime}</span></div>
                    {div && (
                      <div style={{ marginTop: 6 }}>
                        <Badge variant={/bullish/.test(div) ? 'ok' : 'down'}>
                          Divergência {/bullish/.test(div) ? '▲' : '▼'}
                        </Badge>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* MACD + Indicators + S/R + Volume Profile */}
      <div className="grid grid-3" style={{ marginBottom: 20 }}>
        {/* Indicators */}
        <div className="card">
          <div className="card-head"><span className="card-title"><Icon name="activity" />Indicadores</span></div>
          <div className="card-pad">
            <DataState empty={!ind} emptyLabel="Sem dados">{ind && (
              <>
                <IndicatorRow label="RSI 14" value={`${ind.rsi < 30 ? '▲ ' : ind.rsi > 70 ? '▼ ' : ''}${fmtNum(ind.rsi, 1)}`} variant={ind.rsi < 30 ? 'up' : ind.rsi > 70 ? 'down' : ''} />
                <IndicatorRow label="MACD" value={`${(ind.macd?.hist ?? 0) >= 0 ? '▲' : '▼'} ${fmtNum(ind.macd?.macd, 1)}`} variant={(ind.macd?.hist ?? 0) >= 0 ? 'up' : 'down'} />
                <IndicatorRow label="MACD Signal" value={fmtNum(ind.macd?.signal, 1)} />
                <IndicatorRow label="Stoch %K" value={fmtNum(ind.stoch?.k, 1)} />
                <IndicatorRow label="BB %B" value={fmtNum(ind.bb?.pct_b)} />
                <IndicatorRow label="EMA 9" value={fmtUsd(ind.ema9, 0)} />
                <IndicatorRow label="EMA 21" value={fmtUsd(ind.ema21, 0)} />
                <IndicatorRow label="SMA 200" value={fmtUsd(ind.sma200, 0)} />
                <IndicatorRow label="Vol ratio" value={fmtNum(ind.volume_ratio)} />
                <IndicatorRow label="OBV trend" value={ind.obv_trend === 1 ? 'Acumulação' : 'Distribuição'} variant={ind.obv_trend === 1 ? 'up' : 'down'} />
              </>
            )}</DataState>
          </div>
        </div>

        {/* S/R Levels + Fib */}
        <div className="card">
          <div className="card-head"><span className="card-title"><Icon name="bar" />S/R & Fibonacci</span></div>
          <div className="card-pad">
            <DataState empty={!levels} emptyLabel="Sem níveis">{levels && (
              <>
                <div className="label-xs" style={{ marginBottom: 8 }}>Resistência</div>
                {(levels.resistance ?? []).map((r, i) => (
                  <SRLevelRow key={i} label={`R${i + 1}`} price={r.price} strength={r.strength} color="var(--down)" />
                ))}
                <div className="label-xs" style={{ margin: '14px 0 8px' }}>Suporte</div>
                {(levels.support ?? []).map((s, i) => (
                  <SRLevelRow key={i} label={`S${i + 1}`} price={s.price} strength={s.strength} color="var(--up)" />
                ))}
                {(levels?.fib ?? []).length > 0 && (
                  <>
                    <div className="label-xs" style={{ margin: '14px 0 8px' }}>Fibonacci</div>
                    {[0, 23.6, 38.2, 50, 61.8, 78.6, 100].map((pct, i) => {
                      const price = (levels.fib ?? [])[i];
                      if (price == null) return null;
                      return (
                        <div key={i} className="stat-row">
                          <span className="stat-k" style={{ fontFamily: 'var(--mono)', fontSize: 11.5 }}>{pct}%</span>
                          <span className="stat-v">{fmtUsd(price, 0)}</span>
                        </div>
                      );
                    })}
                  </>
                )}
              </>
            )}</DataState>
          </div>
        </div>

        {/* Volume Profile + Patterns */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="card">
            <div className="card-head"><span className="card-title"><Icon name="bar" />Volume Profile</span></div>
            <div className="card-pad">
              <DataState empty={!volumeProfile} emptyLabel="Sem dados">{volumeProfile && (
                <>
                  <div className="stat-row">
                    <span className="stat-k">POC</span>
                    <span className="stat-v">{fmtUsd(volumeProfile.poc, 0)}</span>
                  </div>
                  <div className="stat-row">
                    <span className="stat-k">VAH</span>
                    <span className="stat-v">{fmtUsd(volumeProfile.vah, 0)}</span>
                  </div>
                  <div className="stat-row">
                    <span className="stat-k">VAL</span>
                    <span className="stat-v">{fmtUsd(volumeProfile.val, 0)}</span>
                  </div>
                  {(volumeProfile.lvn ?? []).map((l, i) => (
                    <div key={i} className="stat-row">
                      <span className="stat-k">LVN {i + 1}</span>
                      <span className="stat-v" style={{ color: 'var(--ink-3)' }}>{fmtUsd(l, 0)}</span>
                    </div>
                  ))}
                </>
              )}</DataState>
            </div>
          </div>

          <div className="card">
            <div className="card-head"><span className="card-title"><Icon name="eye" />Padrões</span></div>
            <div className="card-pad">
              <DataState empty={!(patterns && patterns.length)} emptyLabel="Sem padrões detectados">{(patterns || []).map((p, i) => (
                <div key={i} style={{
                  display: 'flex', flexDirection: 'column', gap: 4,
                  padding: '10px 0', borderBottom: i < patterns.length - 1 ? '1px solid var(--border)' : 'none',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: 12.5, fontWeight: 500 }}>{p.name}</span>
                    <Badge variant={patternVariant(p.direction)}>{patternLabel(p.direction)}</Badge>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ fontSize: 11.5, color: 'var(--ink-3)' }}>
                      Conf. {Math.round((p.confidence ?? 0) * 100)}%
                    </span>
                    {p.target && (
                      <span style={{ fontSize: 11.5, fontFamily: 'var(--mono)', color: 'var(--up)' }}>
                        alvo {fmtUsd(p.target, 0)}
                      </span>
                    )}
                  </div>
                </div>
              ))}</DataState>
            </div>
          </div>
        </div>
      </div>

      {/* Regime detail */}
      {regime && (
        <div className="card">
          <div className="card-head">
            <span className="card-title"><Icon name="activity" />Regime de Mercado</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              {regime.extreme && (
                <Badge variant={/EUFORIA/i.test(regime.extreme) ? 'warn' : 'down'}>
                  {regime.extreme}
                </Badge>
              )}
              <Badge variant={REGIME_VARIANT[regime.regime] ?? 'neutral'}>
                {regime.label ?? REGIME_LABEL[regime.regime] ?? regime.regime}
              </Badge>
            </div>
          </div>
          <div className="card-pad">
            {(regime.bars_in_regime != null || regime.last_transition) && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 18, marginBottom: 14, fontSize: 12, color: 'var(--ink-2)' }}>
                {regime.bars_in_regime != null && (
                  <span>No regime há <b style={{ color: 'var(--ink)' }}>{regime.bars_in_regime}</b> candles</span>
                )}
                {regime.since && (
                  <span>desde <b style={{ color: 'var(--ink)' }}>{fmtDateTime(regime.since)}</b></span>
                )}
                {regime.last_transition && (
                  <span>última transição <b style={{ color: 'var(--ink)', fontFamily: 'var(--mono)' }}>{regime.last_transition}</b></span>
                )}
              </div>
            )}
            <div className="grid grid-regime4" style={{ gap: 0 }}>
              {REGIME_OPTIONS.map(opt => (
                <div
                  key={opt.key}
                  style={{
                    padding: '10px 12px',
                    background: regime.regime === opt.key ? 'var(--surface-3)' : 'transparent',
                    borderRadius: 'var(--r-sm)', margin: 4,
                  }}
                >
                  <Badge variant={REGIME_VARIANT[opt.key] ?? 'neutral'} dot={false}>{opt.label}</Badge>
                  <div style={{ fontSize: 11.5, color: 'var(--ink-3)', marginTop: 6 }}>{opt.desc}</div>
                  <div style={{ fontSize: 11.5, fontWeight: 500, marginTop: 4 }}>
                    <Icon name="activity" size={11} /> {opt.strat}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
window.ScreenMarket = ScreenMarket;
