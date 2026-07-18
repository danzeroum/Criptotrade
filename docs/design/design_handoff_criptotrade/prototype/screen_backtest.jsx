/* ============================================================
   Criptotrade — Screen: Validação de Estratégias
   ============================================================ */
const { useState: _useB } = React;

function MetricTile({ label, value, color, sub }) {
  return (
    <div style={{ padding: '12px 14px', borderRight: '1px solid var(--border)', flex: 1, minWidth: 0 }}>
      <div className="label-xs" style={{ fontSize: 9.5 }}>{label}</div>
      <div className="mono" style={{ fontSize: 19, fontWeight: 500, marginTop: 5, color: color || 'var(--ink)' }}>{value}</div>
      {sub && <div className="muted mono" style={{ fontSize: 10, marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

function WalkForwardChart({ folds }) {
  const W = 460, H = 170, padL = 28, padB = 26, padT = 14;
  const plotW = W - padL - 10, plotH = H - padB - padT;
  const max = Math.max(...folds.flatMap(f => [f.trainSharpe, f.testSharpe])) * 1.1;
  const gw = plotW / folds.length;
  const y = v => padT + (1 - v / max) * plotH;
  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: 'block' }} preserveAspectRatio="xMidYMid meet">
      {[0, 0.5, 1, 1.5, 2].map(t => (
        <g key={t}>
          <line x1={padL} x2={W - 10} y1={y(t)} y2={y(t)} stroke="var(--border)" strokeWidth="1" />
          <text x={padL - 5} y={y(t) + 3} fontSize="9" textAnchor="end" fill="var(--ink-3)" fontFamily="var(--mono)">{t.toFixed(1)}</text>
        </g>
      ))}
      {folds.map((f, i) => {
        const cx = padL + gw * i + gw / 2; const bw = gw * 0.3;
        return (
          <g key={i}>
            <rect x={cx - bw - 1} y={y(f.trainSharpe)} width={bw} height={(H - padB) - y(f.trainSharpe)} fill="var(--ink-3)" rx="2" opacity="0.55" />
            <rect x={cx + 1} y={y(f.testSharpe)} width={bw} height={(H - padB) - y(f.testSharpe)} fill="var(--accent)" rx="2" />
            <text x={cx} y={H - padB + 14} fontSize="9.5" textAnchor="middle" fill="var(--ink-3)">J{f.fold}</text>
          </g>
        );
      })}
    </svg>
  );
}

function BacktestScreen({ toast }) {
  const bt = CT.backtest, mc = CT.monteCarlo, wf = CT.walkForward;
  const [cfg, setCfg] = _useB({ ...CT.backtestConfig });
  const [running, setRunning] = _useB(false);
  const [pair] = useCurrentPair();
  const btPair = pair === 'ALL' ? 'BTC/USDT' : pair;
  const set = (k, v) => setCfg(c => ({ ...c, [k]: v }));
  const run = () => { setRunning(true); setTimeout(() => { setRunning(false); toast('Backtest concluído — 142 trades simulados'); }, 1400); };

  return (
    <div className="content-inner screen-enter">
      <div className="page-head">
        <div>
          <div className="page-title">Validação de Estratégias</div>
          <div className="page-sub">{btPair} · Backtest · Monte Carlo · Walk-forward · replay com slippage e comissão simulados</div>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <PairSelect />
          <Btn kind="primary" icon={running ? 'refresh' : 'play'} data-tip="Roda a simulação da estratégia sobre o histórico (backtest + Monte Carlo + walk-forward)." onClick={run} disabled={running}>{running ? 'Rodando…' : 'Rodar backtest'}</Btn>
        </div>
      </div>

      {/* backtest engine */}
      <div className="card" style={{ marginBottom: 16 }}>
        <CardHead icon="backtest" title="Backtest Engine" sub="252 candles · comissão 0.1% · slippage 5bps" right={<Badge kind="ok" dot>Sharpe {fmtNum(bt.sharpe)}</Badge>} />
        <div style={{ display: 'flex', flexWrap: 'wrap', borderBottom: '1px solid var(--border)' }}>
          <MetricTile label="Total de trades" value={bt.totalTrades} />
          <MetricTile label="Win rate" value={fmtPct(bt.winRate * 100)} color="var(--up)" />
          <MetricTile label="P&L total" value={'+' + fmtPct(bt.pnlPct)} color="var(--up)" sub={fmtUsd(bt.pnlUsd)} />
          <MetricTile label="Max drawdown" value={fmtPct(bt.maxDrawdown)} color="var(--down)" />
          <MetricTile label="Sharpe (anual.)" value={fmtNum(bt.sharpe)} />
          <MetricTile label="Profit factor" value={fmtNum(bt.profitFactor)} />
          <MetricTile label="Expectância" value={'+' + fmtNum(bt.expectancy) + '%'} color="var(--up)" sub="por trade" />
        </div>
        <div style={{ padding: '14px 14px 6px' }}>
          <EquityChart data={bt.equity} height={190} showDrawdown={true} />
        </div>
      </div>

      {/* monte carlo + walk forward */}
      <div className="grid" style={{ gridTemplateColumns: '1.4fr 1fr', gap: 16, marginBottom: 16 }}>
        <div className="card">
          <CardHead icon="dice" title="Monte Carlo Simulator" sub={mc.n.toLocaleString() + ' simulações'}
            right={<Badge kind={mc.rejected ? 'down' : 'ok'} dot>{mc.rejected ? 'rejeitada (p5 < 0)' : 'aprovada'}</Badge>} />
          <div className="card-pad" style={{ paddingTop: 8 }}>
            <MonteCarloHist mc={mc} height={170} />
            <div className="grid" style={{ gridTemplateColumns: 'repeat(4,1fr)', gap: 10, marginTop: 12 }}>
              {[
                ['Percentil 5', fmtUsd(mc.p5, 0), 'var(--down)', 'pior caso'],
                ['Mediana (p50)', fmtUsd(mc.p50, 0), 'var(--ink)', 'esperado'],
                ['Percentil 95', fmtUsd(mc.p95, 0), 'var(--up)', 'melhor caso'],
                ['% lucrativas', fmtPct(mc.profitablePct * 100, 0), 'var(--up)', 'das sims'],
              ].map(([k, v, c, s], i) => (
                <div key={i} style={{ background: 'var(--surface-2)', borderRadius: 8, padding: '9px 11px' }}>
                  <div className="label-xs" style={{ fontSize: 9 }}>{k}</div>
                  <div className="mono" style={{ fontSize: 15, fontWeight: 500, marginTop: 3, color: c }}>{v}</div>
                  <div className="muted" style={{ fontSize: 9.5, marginTop: 1 }}>{s}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="card">
          <CardHead icon="layers" title="Walk-Forward Validator" sub={wf.windows + ' janelas'}
            right={<Badge kind={wf.valid ? 'ok' : 'down'} dot>{wf.valid ? 'válido' : 'overfit'}</Badge>} />
          <div className="card-pad" style={{ paddingTop: 8 }}>
            <WalkForwardChart folds={wf.folds} />
            <div style={{ display: 'flex', gap: 14, justifyContent: 'center', margin: '8px 0 12px', fontSize: 10.5, color: 'var(--ink-3)' }}>
              <span style={{ display: 'flex', gap: 4, alignItems: 'center' }}><span style={{ width: 9, height: 9, background: 'var(--ink-3)', opacity: .55, borderRadius: 2 }} />treino</span>
              <span style={{ display: 'flex', gap: 4, alignItems: 'center' }}><span style={{ width: 9, height: 9, background: 'var(--accent)', borderRadius: 2 }} />teste</span>
            </div>
            <StatRow k="Desvio de Sharpe" v={fmtPct(wf.sharpeDeviation * 100)} vColor={wf.sharpeDeviation < wf.threshold ? 'var(--up)' : 'var(--down)'} />
            <StatRow k="Limite de rejeição" v={fmtPct(wf.threshold * 100)} />
            <div style={{ marginTop: 10, fontSize: 11.5, color: 'var(--ink-2)', display: 'flex', gap: 7, alignItems: 'center' }}>
              <Icon name="info" size={14} style={{ color: 'var(--ink-3)' }} />Rejeita se o desvio entre janelas {'>'} 30%.
            </div>
          </div>
        </div>
      </div>

      {/* config */}
      <div className="card">
        <CardHead icon="settings" title="Parâmetros de simulação" sub="editável"
          right={<Btn kind="primary" sm icon="check" data-tip="Salva os parâmetros de simulação (período, capital, custos)." onClick={() => toast('Parâmetros de simulação salvos')}>Salvar</Btn>} />
        <div className="card-pad">
          <div className="grid" style={{ gridTemplateColumns: 'repeat(5,1fr)', gap: 16 }}>
            <NumField label="Capital inicial" value={cfg.initialCapital} onChange={v => set('initialCapital', v)} step={1000} min={1000} suffix="$" />
            <NumField label="Comissão" value={cfg.commissionPct} onChange={v => set('commissionPct', v)} step={0.05} min={0} max={2} suffix="%" decimals={2} />
            <NumField label="Slippage" value={cfg.slippageBps} onChange={v => set('slippageBps', v)} step={1} min={0} max={50} suffix="bps" />
            <NumField label="Janela walk-forward" value={cfg.walkForwardWindow} onChange={v => set('walkForwardWindow', v)} step={1} min={30} suffix="candles" />
            <NumField label="Simulações Monte Carlo" value={cfg.monteCarloSims} onChange={v => set('monteCarloSims', v)} step={100} min={100} max={10000} />
          </div>
        </div>
      </div>
    </div>
  );
}

window.BacktestScreen = BacktestScreen;
