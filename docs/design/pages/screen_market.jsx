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
        ${price?.toLocaleString('en', { minimumFractionDigits: 2 })}
        <span style={{ color: 'var(--ink-4)', fontSize: 11, marginLeft: 6 }}>
          {'★'.repeat(Math.min(5, Math.round(strength ?? 0)))}
        </span>
      </span>
    </div>
  );
}

function ScreenMarket() {
  const mock = !!window.USE_MOCK_DATA;
  const [pair, setPair] = useState(CT_PAIR.get());
  const [tf, setTf] = useState('1h');
  const [pairs, setPairs] = useState(mock ? ['BTC/USDT', 'ETH/USDT', 'SOL/USDT'] : null);

  const mockData = useMemo(() => ({
    candles: CT.candles.map(c => ({ t: c.i, o: c.open, h: c.high, l: c.low, c: c.close, v: c.volume })),
    bb: CT.bb,
    indicators: {
      rsi: CT.indicators.rsi,
      macd: CT.indicators.macd,
      stoch: CT.indicators.stoch,
      bb: { up: CT.bb[CT.bb.length - 1]?.up, mid: CT.bb[CT.bb.length - 1]?.mid, low: CT.bb[CT.bb.length - 1]?.low, pct_b: CT.indicators.bollPctB },
      atr: CT.indicators.atr,
      atr_pct: CT.indicators.atrPctOfPrice,
      ema9: CT.indicators.ema9,
      ema21: CT.indicators.ema21,
      sma20: CT.indicators.sma20,
      sma50: CT.indicators.sma50,
      sma200: CT.indicators.sma200,
      obv_trend: CT.indicators.obvTrend,
      volume_ratio: CT.indicators.volumeRatio,
    },
    regime: {
      regime: CT.regime.current,
      confidence: CT.regime.confidence,
      label: CT.regime.label,
      active_strategy: CT.regime.strategy,
    },
    levels: {
      support: CT.sr.support.map(s => ({ price: s.price, strength: s.strength })),
      resistance: CT.sr.resistance.map(r => ({ price: r.price, strength: r.strength })),
      fib: CT.sr.fib.map(f => f.price),
    },
    volumeProfile: {
      poc: CT.volumeProfile.poc,
      vah: CT.volumeProfile.vah,
      val: CT.volumeProfile.val,
      lvn: CT.volumeProfile.lvn,
      bins: CT.volumeProfile.bins,
    },
    patterns: CT.patterns.map(p => ({
      name: p.name,
      direction: p.dir === 'up' ? 'bullish' : p.dir === 'down' ? 'bearish' : 'neutral',
      confidence: p.confidence,
      target: p.target,
    })),
    signal: {
      action: CT.signal.action,
      entry: CT.signal.entry,
      stop: CT.signal.stop,
      take_profit: CT.signal.takeProfit,
      position_size_pct: CT.signal.sizePct,
      rr: CT.signal.rr,
      strategy: CT.signal.strategy,
      confidence: CT.signal.confidence,
      reason: 'RSI saindo de sobrevendido + suporte forte confirmado por volume.',
    },
  }), []);

  const [candles,       setCandles]       = useState(mock ? mockData.candles : null);
  const [bb,            setBb]            = useState(mock ? mockData.bb : null);
  const [indicators,    setIndicators]    = useState(mock ? mockData.indicators : null);
  const [regime,        setRegime]        = useState(mock ? mockData.regime : null);
  const [levels,        setLevels]        = useState(mock ? mockData.levels : null);
  const [volumeProfile, setVolumeProfile] = useState(mock ? mockData.volumeProfile : null);
  const [patterns,      setPatterns]      = useState(mock ? mockData.patterns : null);
  const [signal,        setSignal]        = useState(mock ? mockData.signal : null);
  const [ticker,        setTicker]        = useState(null);
  const [loading,       setLoading]       = useState(!mock);
  const [error,         setError]         = useState(null);

  // Mercado exige um par concreto; se o escopo global for 'ALL', usa o default.
  const effPair = effectivePair(pair, pairs);

  const load = () => {
    if (mock) return;
    setLoading(true);
    Promise.all([
      CT_API.getCandles(effPair, tf, 70),
      CT_API.getIndicators(effPair),
      CT_API.getRegime(effPair),
      CT_API.getLevels(effPair),
      CT_API.getVolumeProfile(effPair),
      CT_API.getPatterns(effPair),
      CT_API.getSignal(effPair),
      CT_API.getTicker(effPair).catch(() => null),  // non-critical: never fail the load
    ])
      .then(([c, ind, reg, lvl, vp, pat, sig, tk]) => {
        setCandles(c);
        setIndicators(ind);
        setRegime(reg);
        setLevels(lvl);
        setVolumeProfile(vp);
        setPatterns(Array.isArray(pat) ? pat : []);
        setSignal(sig);
        setTicker(tk);
        setLoading(false);
      })
      .catch(e => { setError(e); setLoading(false); });
  };

  // Source the dropdown from the allowlist and let other screens (the header)
  // drive the pair too. The store is the single source of truth for `pair`.
  useEffect(() => {
    if (!mock) loadPairs().then(setPairs);
    return CT_PAIR.subscribe(setPair);
  }, []);

  useEffect(() => { load(); }, [effPair, tf]);

  if (loading) return <LoadingState label="Carregando análise de mercado…" />;
  if (error)   return <ErrorState message="Erro ao carregar mercado" onRetry={() => { setError(null); load(); }} />;

  const sym = CT.symbol;
  const lastClose = candles?.length ? candles[candles.length - 1].c : null;
  const ind = indicators;

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
          <Btn variant="ghost" size="sm" onClick={load}>
            <Icon name="refresh" size={13} />
          </Btn>
        </div>
      </div>

      {/* Price KPIs */}
      <div className="grid" style={{ gridTemplateColumns: 'repeat(5, 1fr)', marginBottom: 20 }}>
        <div className="card">
          <KPI label="Preço atual" value={lastClose} format="usd" icon="dollar" />
        </div>
        <div className="card">
          <KPI label="Variação 24h" value={ticker?.change_24h_pct ?? sym?.change24h} format="pct_direct" delta={ticker?.change_24h_pct ?? sym?.change24h} icon="trending" />
        </div>
        <div className="card">
          <KPI label="RSI" value={ind?.rsi?.toFixed(1)} sub={ind?.rsi < 30 ? 'Sobrevendido' : ind?.rsi > 70 ? 'Sobrecomprado' : 'Neutro'} />
        </div>
        <div className="card">
          <KPI label="ATR" value={ind?.atr?.toFixed(0)} sub={`${ind?.atr_pct?.toFixed(2)}% do preço`} icon="activity" />
        </div>
        <div className="card">
          <KPI label="Estratégia ativa" value={regime?.active_strategy ?? '—'} />
        </div>
      </div>

      {/* Candle chart + Signal */}
      <div className="grid" style={{ gridTemplateColumns: '1fr 300px', marginBottom: 20, alignItems: 'start' }}>
        <div className="card">
          <div className="card-head">
            <span className="card-title"><Icon name="candle" />{effPair} · {tf}</span>
          </div>
          <div className="card-pad" style={{ padding: '14px 12px' }}>
            {candles && candles.length > 0 ? (
              <CandleChart
                candles={candles}
                height={280}
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
                  <span className="stat-v">${signal.entry?.toLocaleString('en', { minimumFractionDigits: 2 })}</span>
                </div>
                <div className="stat-row">
                  <span className="stat-k">Stop</span>
                  <span className="stat-v down">${signal.stop?.toLocaleString('en', { minimumFractionDigits: 2 })}</span>
                </div>
                <div className="stat-row">
                  <span className="stat-k">Alvo</span>
                  <span className="stat-v up">${signal.take_profit?.toLocaleString('en', { minimumFractionDigits: 2 })}</span>
                </div>
                <div className="stat-row">
                  <span className="stat-k">Tamanho</span>
                  <span className="stat-v">{signal.position_size_pct?.toFixed(1)}%</span>
                </div>
                <div className="stat-row">
                  <span className="stat-k">R/R</span>
                  <span className="stat-v" style={{ color: (signal.rr ?? 0) >= 2.5 ? 'var(--up)' : 'var(--warn)' }}>
                    {signal.rr?.toFixed(1)}×
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
            </div>
          </div>
        )}
      </div>

      {/* MACD + Indicators + S/R + Volume Profile */}
      <div className="grid" style={{ gridTemplateColumns: '1fr 1fr 1fr', marginBottom: 20 }}>
        {/* Indicators */}
        <div className="card">
          <div className="card-head"><span className="card-title"><Icon name="activity" />Indicadores</span></div>
          <div className="card-pad">
            {ind ? (
              <>
                <IndicatorRow label="RSI 14" value={ind.rsi?.toFixed(1)} variant={ind.rsi < 30 ? 'up' : ind.rsi > 70 ? 'down' : ''} />
                <IndicatorRow label="MACD" value={ind.macd?.macd?.toFixed(1)} />
                <IndicatorRow label="MACD Signal" value={ind.macd?.signal?.toFixed(1)} />
                <IndicatorRow label="Stoch %K" value={ind.stoch?.k?.toFixed(1)} />
                <IndicatorRow label="BB %B" value={ind.bb?.pct_b?.toFixed(2)} />
                <IndicatorRow label="EMA 9" value={`$${Math.round(ind.ema9).toLocaleString('en')}`} />
                <IndicatorRow label="EMA 21" value={`$${Math.round(ind.ema21).toLocaleString('en')}`} />
                <IndicatorRow label="SMA 200" value={`$${Math.round(ind.sma200).toLocaleString('en')}`} />
                <IndicatorRow label="Vol ratio" value={ind.volume_ratio?.toFixed(2)} />
                <IndicatorRow label="OBV trend" value={ind.obv_trend === 1 ? 'Acumulação' : 'Distribuição'} variant={ind.obv_trend === 1 ? 'up' : 'down'} />
              </>
            ) : <EmptyState label="Sem dados" />}
          </div>
        </div>

        {/* S/R Levels + Fib */}
        <div className="card">
          <div className="card-head"><span className="card-title"><Icon name="bar" />S/R & Fibonacci</span></div>
          <div className="card-pad">
            {levels ? (
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
                          <span className="stat-v">${Math.round(price).toLocaleString('en')}</span>
                        </div>
                      );
                    })}
                  </>
                )}
              </>
            ) : <EmptyState label="Sem níveis" />}
          </div>
        </div>

        {/* Volume Profile + Patterns */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="card">
            <div className="card-head"><span className="card-title"><Icon name="bar" />Volume Profile</span></div>
            <div className="card-pad">
              {volumeProfile ? (
                <>
                  <div className="stat-row">
                    <span className="stat-k">POC</span>
                    <span className="stat-v">${Math.round(volumeProfile.poc).toLocaleString('en')}</span>
                  </div>
                  <div className="stat-row">
                    <span className="stat-k">VAH</span>
                    <span className="stat-v">${Math.round(volumeProfile.vah).toLocaleString('en')}</span>
                  </div>
                  <div className="stat-row">
                    <span className="stat-k">VAL</span>
                    <span className="stat-v">${Math.round(volumeProfile.val).toLocaleString('en')}</span>
                  </div>
                  {(volumeProfile.lvn ?? []).map((l, i) => (
                    <div key={i} className="stat-row">
                      <span className="stat-k">LVN {i + 1}</span>
                      <span className="stat-v" style={{ color: 'var(--ink-3)' }}>${Math.round(l).toLocaleString('en')}</span>
                    </div>
                  ))}
                </>
              ) : <EmptyState label="Sem dados" />}
            </div>
          </div>

          <div className="card">
            <div className="card-head"><span className="card-title"><Icon name="eye" />Padrões</span></div>
            <div className="card-pad">
              {patterns && patterns.length > 0 ? patterns.map((p, i) => (
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
                        alvo ${Math.round(p.target).toLocaleString('en')}
                      </span>
                    )}
                  </div>
                </div>
              )) : <EmptyState label="Sem padrões detectados" />}
            </div>
          </div>
        </div>
      </div>

      {/* Regime detail */}
      {regime && (
        <div className="card">
          <div className="card-head">
            <span className="card-title"><Icon name="activity" />Regime de Mercado</span>
            <Badge variant={REGIME_VARIANT[regime.regime] ?? 'neutral'}>
              {regime.label ?? REGIME_LABEL[regime.regime] ?? regime.regime}
            </Badge>
          </div>
          <div className="card-pad">
            <div className="grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)', gap: 0 }}>
              {CT.regime.options.map(opt => (
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
