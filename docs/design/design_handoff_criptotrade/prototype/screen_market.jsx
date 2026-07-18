/* ============================================================
   Criptotrade — Screen: Dashboard de Mercado
   ============================================================ */
const { useState: _useM } = React;

function OverlayToggle({ label, on, onClick, color, tip }) {
  return (
    <button onClick={onClick} className="btn btn-sm" data-tip={tip || undefined} style={{
      borderColor: on ? color : 'var(--border-2)',
      background: on ? color : 'var(--surface)',
      color: on ? '#fff' : 'var(--ink-2)', gap: 6,
    }}>
      <span style={{ width: 8, height: 8, borderRadius: 2, background: on ? '#fff' : color }} />{label}
    </button>
  );
}

function IndCard({ label, children, value, sub, badge }) {
  return (
    <div className="card card-pad" style={{ minWidth: 0 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <span className="label-xs">{label}</span>
        {badge}
      </div>
      {value && <div className="mono" style={{ fontSize: 22, fontWeight: 500 }}>{value}</div>}
      {sub && <div className="muted mono" style={{ fontSize: 11, marginTop: 3 }}>{sub}</div>}
      {children}
    </div>
  );
}

/* horizontal volume-profile */
function VolumeProfileChart({ vp, height = 280 }) {
  const W = 260, H = height, padT = 8, padB = 8;
  const max = Math.max(...vp.bins.map(b => b.vol));
  const prices = vp.bins.map(b => b.price);
  const yMin = Math.min(...prices), yMax = Math.max(...prices);
  const y = p => padT + (yMax - p) / (yMax - yMin) * (H - padT - padB);
  const bh = (H - padT - padB) / vp.bins.length * 0.82;
  const inVA = p => p <= vp.vah && p >= vp.val;
  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: 'block' }} preserveAspectRatio="xMidYMid meet">
      {vp.bins.map((b, i) => {
        const w = b.vol / max * (W - 70);
        const isPoc = Math.abs(b.price - vp.poc) < (yMax - yMin) / vp.bins.length;
        return (
          <g key={i}>
            <rect x={0} y={y(b.price) - bh / 2} width={w} height={bh} rx="1.5"
              fill={isPoc ? 'var(--accent)' : inVA(b.price) ? 'var(--info)' : 'var(--ink-3)'}
              opacity={isPoc ? 0.9 : inVA(b.price) ? 0.5 : 0.28} />
          </g>
        );
      })}
      {[['POC', vp.poc, 'var(--accent)'], ['VAH', vp.vah, 'var(--info)'], ['VAL', vp.val, 'var(--info)']].map(([k, p, c]) => (
        <g key={k}>
          <line x1={0} x2={W - 60} y1={y(p)} y2={y(p)} stroke={c} strokeWidth="1" strokeDasharray={k === 'POC' ? '0' : '3 2'} opacity="0.8" />
          <text x={W - 56} y={y(p) + 3.5} fontSize="9.5" fill={c} fontWeight="600">{k}</text>
          <text x={W - 56} y={y(p) + 14} fontSize="8.5" fill="var(--ink-3)" fontFamily="var(--mono)">{Math.round(p / 1000)}k</text>
        </g>
      ))}
    </svg>
  );
}

function MarketScreen() {
  const [ov, setOv] = _useM({ bb: true, sr: true, fib: false, grid: false });
  const [gPair] = useCurrentPair();
  const mPair = gPair === 'ALL' ? 'BTC/USDT' : gPair;
  const t = (k) => setOv(o => ({ ...o, [k]: !o[k] }));
  const ind = CT.indicators, sig = CT.signal, reg = CT.regime, vp = CT.volumeProfile;
  const dirBadge = d => d === 'up' ? <Badge kind="ok" dot>alta</Badge> : d === 'down' ? <Badge kind="down" dot>baixa</Badge> : <Badge kind="neutral" dot>neutro</Badge>;

  return (
    <div className="content-inner screen-enter">
      <div className="page-head">
        <div>
          <div className="page-title">Dashboard de Mercado</div>
          <div className="page-sub">{mPair} · análise técnica ao vivo · regime detectado automaticamente</div>
        </div>
        <div style={{ display: 'flex', gap: 7 }}>
          <OverlayToggle label="Bollinger" on={ov.bb} onClick={() => t('bb')} color="var(--info)" tip="Bandas de Bollinger: mostram volatilidade e zonas de sobrecompra/sobrevenda ao redor da média." />
          <OverlayToggle label="S/R" on={ov.sr} onClick={() => t('sr')} color="var(--accent)" tip="Suporte e Resistência: pisos e tetos de preço onde o mercado tende a reagir." />
          <OverlayToggle label="Fibonacci" on={ov.fib} onClick={() => t('fib')} color="var(--violet)" tip="Retrações de Fibonacci: níveis prováveis de correção dentro de uma tendência." />
          <OverlayToggle label="Grid" on={ov.grid} onClick={() => t('grid')} color="var(--ink-3)" tip="Liga/desliga a grade de referência do gráfico." />
        </div>
      </div>

      {/* chart + right rail */}
      <div className="grid" style={{ gridTemplateColumns: '1fr 300px', marginBottom: 16 }}>
        <div className="card">
          <CardHead icon="market" title={mPair + ' · 1H'}
            right={<div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              <span className="chip">O <b className="mono">{Math.round(CT.candles.at(-1).open).toLocaleString()}</b></span>
              <span className="chip">H <b className="mono">{Math.round(CT.symbol.high24h).toLocaleString()}</b></span>
              <span className="chip">L <b className="mono">{Math.round(CT.symbol.low24h).toLocaleString()}</b></span>
              <span className="chip">Vol <b className="mono">{CT.symbol.volume24h}</b></span>
            </div>} />
          <div style={{ padding: '12px 14px 4px' }}>
            <CandleChart candles={CT.candles} bb={CT.bb} sr={CT.sr} fib={CT.sr.fib} overlays={ov} height={360} />
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* regime */}
          <div className="card">
            <CardHead icon="layers" title="Regime de mercado" right={<span className="mono" style={{ fontSize: 12, fontWeight: 600 }}>{Math.round(reg.confidence * 100)}%</span>} />
            <div className="card-pad" style={{ paddingTop: 12 }}>
              {reg.options.map(o => (
                <div key={o.key} style={{
                  display: 'flex', alignItems: 'center', gap: 9, padding: '8px 10px', borderRadius: 7, marginBottom: 4,
                  background: o.key === reg.current ? 'var(--info-bg)' : 'transparent',
                  border: o.key === reg.current ? '1px solid #C9D8FA' : '1px solid transparent',
                }}>
                  <span style={{ width: 8, height: 8, borderRadius: 99, background: o.key === reg.current ? 'var(--info)' : 'var(--border-2)' }} />
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontSize: 12.5, fontWeight: o.key === reg.current ? 600 : 500 }}>{o.label}</div>
                    <div className="muted" style={{ fontSize: 11 }}>{o.desc}</div>
                  </div>
                  <span className="chip" style={{ marginLeft: 'auto', fontSize: 10.5 }}>{o.strat}</span>
                </div>
              ))}
              <div className="hr" style={{ margin: '10px 0' }} />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11.5 }}>
                <span className="muted">Extremos</span>
                <span style={{ display: 'flex', gap: 6 }}>
                  <Badge kind="neutral">EUFORIA</Badge><Badge kind="neutral">PÂNICO</Badge>
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* current signal — full width band */}
      <div className="card" style={{ marginBottom: 16, background: 'var(--surface-2)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 0, flexWrap: 'wrap' }}>
          <div style={{ padding: '16px 20px', display: 'flex', alignItems: 'center', gap: 14, borderRight: '1px solid var(--border)' }}>
            <DonutProgress value={sig.confidence} size={62} stroke={7} label={Math.round(sig.confidence * 100) + '%'} color="var(--accent)" />
            <div>
              <span className="label-xs">Sinal atual</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
                <Badge kind={sig.action === 'buy' ? 'ok' : 'down'} dot>{sig.action === 'buy' ? 'COMPRA' : 'VENDA'}</Badge>
                <span className="chip">{sig.strategy}</span>
              </div>
            </div>
          </div>
          {[
            ['Entrada', fmtUsd(sig.entry)], ['Stop loss', fmtUsd(sig.stop), 'var(--down)'],
            ['Take profit', fmtUsd(sig.takeProfit), 'var(--up)'], ['Tamanho', fmtPct(sig.sizePct)],
            ['Risk/Reward', sig.rr + '×'], ['Notional', fmtUsd(sig.notional)],
          ].map(([k, v, c], i) => (
            <div key={i} style={{ padding: '16px 20px', flex: 1, borderRight: i < 5 ? '1px solid var(--border)' : 'none', minWidth: 110 }}>
              <div className="label-xs">{k}</div>
              <div className="mono" style={{ fontSize: 16, fontWeight: 500, marginTop: 5, color: c || 'var(--ink)' }}>{v}</div>
            </div>
          ))}
          <div style={{ padding: '0 18px' }}>
            <Btn kind="primary" iconRight="arrowRight" data-tip="Envia este sinal para o Console HITL, onde um humano aprova ou rejeita antes de executar." onClick={() => location.hash = ''}>Ver no HITL</Btn>
          </div>
        </div>
      </div>

      {/* indicators row */}
      <div className="grid" style={{ gridTemplateColumns: 'repeat(4,1fr)', marginBottom: 16 }}>
        <IndCard label="RSI (14)" badge={<Badge kind={ind.rsi < 30 ? 'ok' : ind.rsi > 70 ? 'down' : 'neutral'}>{ind.rsi < 30 ? 'sobrevendido' : ind.rsi > 70 ? 'sobrecomprado' : 'neutro'}</Badge>}>
          <div style={{ display: 'grid', placeItems: 'center' }}>
            <Gauge value={ind.rsi} zones={[{ from: 0, to: 30, color: 'var(--up)' }, { from: 70, to: 100, color: 'var(--down)' }]} size={150} />
          </div>
        </IndCard>
        <IndCard label="MACD" value={fmtNum(ind.macd.hist)} sub={`MACD ${fmtNum(ind.macd.macd)} · sinal ${fmtNum(ind.macd.signal)}`} badge={<Badge kind={ind.macd.hist >= 0 ? 'ok' : 'down'} dot>{ind.macd.hist >= 0 ? 'bullish' : 'bearish'}</Badge>}>
          <div style={{ marginTop: 12 }}><MACDBars data={CT.indicators.macdHist} height={70} /></div>
        </IndCard>
        <IndCard label="Estocástico" badge={<Badge kind={ind.stoch.k < 20 ? 'ok' : ind.stoch.k > 80 ? 'down' : 'neutral'}>zona 20/80</Badge>}>
          <div style={{ display: 'flex', gap: 18, alignItems: 'baseline', marginTop: 6 }}>
            <div><span className="muted" style={{ fontSize: 11 }}>%K </span><span className="mono" style={{ fontSize: 20, fontWeight: 500 }}>{fmtNum(ind.stoch.k, 1)}</span></div>
            <div><span className="muted" style={{ fontSize: 11 }}>%D </span><span className="mono" style={{ fontSize: 20, fontWeight: 500 }}>{fmtNum(ind.stoch.d, 1)}</span></div>
          </div>
          <div style={{ marginTop: 14 }}>
            <Meter value={ind.stoch.k} color="var(--accent)" height={6} />
            <div style={{ marginTop: 6 }}><Meter value={ind.stoch.d} color="var(--ink-3)" height={6} /></div>
          </div>
        </IndCard>
        <IndCard label="Volume & ATR" value={fmtNum(ind.volumeRatio, 2) + '×'} sub={`vs média 20 · ATR ${fmtUsd(ind.atr)} (${ind.atrPctOfPrice}%)`} badge={<Badge kind={ind.volumeRatio < 0.5 ? 'warn' : 'neutral'}>{ind.volumeRatio < 0.5 ? 'baixa liquidez' : 'normal'}</Badge>}>
          <div style={{ marginTop: 12 }}><MiniBars data={[0.6, 0.8, 1.2, 0.9, 0.7, 1.1, 0.84]} height={56} color="var(--accent)" /></div>
        </IndCard>
      </div>

      {/* moving averages + patterns + S/R + volume profile */}
      <div className="grid" style={{ gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
        {/* moving averages */}
        <div className="card">
          <CardHead icon="pulse" title="Médias móveis & tendência" />
          <div className="card-pad" style={{ paddingTop: 8 }}>
            <div className="grid" style={{ gridTemplateColumns: '1fr 1fr', gap: '0 24px' }}>
              <div>
                <StatRow k="EMA(9)" v={fmtUsd(ind.ema9)} />
                <StatRow k="EMA(21)" v={fmtUsd(ind.ema21)} />
                <StatRow k="Cruzamento EMA" v="alta" vColor="var(--up)" />
              </div>
              <div>
                <StatRow k="SMA(20)" v={fmtUsd(ind.sma20)} />
                <StatRow k="SMA(50)" v={fmtUsd(ind.sma50)} />
                <StatRow k="SMA(200)" v={fmtUsd(ind.sma200)} />
              </div>
            </div>
            <div className="hr" style={{ margin: '12px 0' }} />
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div><span className="label-xs">OBV (On-Balance Volume)</span><div className="muted" style={{ fontSize: 11.5, marginTop: 2 }}>Acumulação / distribuição</div></div>
              <Badge kind={ind.obvTrend < 0 ? 'down' : 'ok'} dot>{ind.obv}</Badge>
            </div>
            <div style={{ marginTop: 10 }}><Sparkline data={[5, 4, 6, 5, 3, 4, 2, 3, 1, 2]} w={520} h={42} color="var(--down)" fill /></div>
          </div>
        </div>

        {/* patterns */}
        <div className="card">
          <CardHead icon="target" title="Padrões detectados" sub={CT.patterns.length + ' ativos'} />
          <div style={{ padding: '6px 0' }}>
            {CT.patterns.map((p, i) => (
              <div key={i} style={{ padding: '11px 18px', borderBottom: i < CT.patterns.length - 1 ? '1px solid var(--border)' : 'none' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 7 }}>
                  <span style={{ fontSize: 13, fontWeight: 500 }}>{p.name}</span>
                  {dirBadge(p.dir)}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <div style={{ flex: 1 }}><Meter value={p.confidence * 100} color={p.confidence > 0.7 ? 'var(--up)' : 'var(--ink-3)'} height={5} /></div>
                  <span className="mono" style={{ fontSize: 11.5, color: 'var(--ink-2)', width: 38 }}>{Math.round(p.confidence * 100)}%</span>
                  <span className="mono" style={{ fontSize: 11.5, color: 'var(--ink-3)' }}>alvo {fmtUsd(p.target, 0)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* S/R + Fib + Volume Profile */}
      <div className="grid" style={{ gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>
        <div className="card">
          <CardHead icon="layers" title="Suporte & Resistência" />
          <div className="card-pad" style={{ paddingTop: 10 }}>
            {CT.sr.resistance.map((s, i) => (
              <div key={'r' + i} className="stat-row">
                <span style={{ display: 'flex', gap: 7, alignItems: 'center' }}><span style={{ width: 7, height: 7, borderRadius: 2, background: 'var(--down)' }} />Resistência</span>
                <span style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <span className="mono" style={{ fontSize: 12.5, fontWeight: 500 }}>{fmtUsd(s.price, 0)}</span>
                  <span className="chip" style={{ fontSize: 10 }}>força {s.strength}</span>
                </span>
              </div>
            ))}
            {CT.sr.support.map((s, i) => (
              <div key={'s' + i} className="stat-row">
                <span style={{ display: 'flex', gap: 7, alignItems: 'center' }}><span style={{ width: 7, height: 7, borderRadius: 2, background: 'var(--up)' }} />Suporte</span>
                <span style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <span className="mono" style={{ fontSize: 12.5, fontWeight: 500 }}>{fmtUsd(s.price, 0)}</span>
                  <span className="chip" style={{ fontSize: 10 }}>força {s.strength}</span>
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <CardHead icon="target" title="Níveis de Fibonacci" />
          <div className="card-pad" style={{ paddingTop: 10 }}>
            {CT.sr.fib.map((f, i) => (
              <div key={i} className="stat-row" style={{ padding: '6px 0' }}>
                <span style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <span className="mono" style={{ fontSize: 11.5, color: 'var(--violet)', width: 42, fontWeight: 600 }}>{f.level}%</span>
                  <div style={{ width: `${40 + f.level * 0.5}px`, height: 4, borderRadius: 2, background: 'var(--violet)', opacity: 0.3 }} />
                </span>
                <span className="mono" style={{ fontSize: 12, fontWeight: 500 }}>{fmtUsd(f.price, 0)}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <CardHead icon="market" title="Volume Profile" sub="POC · VAH/VAL · LVN" />
          <div className="card-pad" style={{ paddingTop: 8 }}>
            <VolumeProfileChart vp={vp} height={250} />
            <div style={{ display: 'flex', gap: 10, marginTop: 6, fontSize: 10.5, color: 'var(--ink-3)' }}>
              <span style={{ display: 'flex', gap: 4, alignItems: 'center' }}><span style={{ width: 8, height: 8, background: 'var(--accent)', borderRadius: 2 }} />POC</span>
              <span style={{ display: 'flex', gap: 4, alignItems: 'center' }}><span style={{ width: 8, height: 8, background: 'var(--info)', opacity: .5, borderRadius: 2 }} />Value Area (70%)</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

window.MarketScreen = MarketScreen;
