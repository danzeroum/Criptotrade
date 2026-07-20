/* ============================================================
   Criptotrade — Screen: Backtest
   ============================================================ */
const { useState, useEffect, useRef } = React;

const STRATEGIES = ['grid', 'dca', 'mean_reversion'];
const PAIRS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT'];

function MetricCard({ label, value, sub, format, delta }) {
  return (
    <div className="card">
      <KPI label={label} value={value} sub={sub} format={format} delta={delta} />
    </div>
  );
}

function FoldTable({ folds }) {
  if (!folds || folds.length === 0) return <EmptyState label="Sem folds" />;
  return (
    <table className="tbl">
      <thead>
        <tr>
          <th>Fold</th>
          <th className="th-num">Sharpe treino</th>
          <th className="th-num">Sharpe teste</th>
          <th className="th-num">Δ</th>
        </tr>
      </thead>
      <tbody>
        {folds.map((f, i) => {
          const delta = (f.test_sharpe ?? f.testSharpe) - (f.train_sharpe ?? f.trainSharpe);
          return (
            <tr key={i}>
              <td style={{ fontFamily: 'var(--mono)' }}>#{f.fold ?? i + 1}</td>
              <td className="num">{fmtNum(f.train_sharpe ?? f.trainSharpe)}</td>
              <td className="num">{fmtNum(f.test_sharpe ?? f.testSharpe)}</td>
              <td className="num" style={{ color: delta >= 0 ? 'var(--up)' : 'var(--down)' }}>
                {delta > 0 ? '+' : ''}{fmtNum(delta)}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function ScreenBacktest({ addToast }) {
  const defaultConfig = {
    pair: effectivePair(CT_PAIR.get(), null),  // herda o par do seletor global
    strategy: STRATEGIES[0],
    start_date: '2025-01-01',
    end_date: '2025-12-31',
    initial_capital: 10000,
    commission_pct: 0.1,
    slippage_bps: 5,
  };

  const [config,    setConfig]    = useState(defaultConfig);
  const [result,    setResult]    = useState(null);
  const [mc,        setMC]        = useState(null);
  const [wf,        setWF]        = useState(null);
  const [jobId,     setJobId]     = useState(null);
  const [jobStatus, setJobStatus] = useState(null);
  const [running,   setRunning]   = useState(false);
  const [tab,       setTab]       = useState('result');
  const [pairs,     setPairs]     = useState(null);
  const pollRef = useRef(null);

  useEffect(() => { loadPairs().then(setPairs); }, []);

  const updateConfig = (k, v) => setConfig(prev => ({ ...prev, [k]: v }));

  const runBacktest = async () => {
    setRunning(true);
    setResult(null);
    setMC(null);
    setWF(null);
    try {
      const job = await CT_API.runBacktest(config);
      setJobId(job.job_id);
      setJobStatus('running');

      const [mcData, wfData] = await Promise.all([
        CT_API.runMonteCarlo({ n: 1000, pnl_pcts: [] }),
        CT_API.runWalkForward(config),
      ]).catch(() => [null, null]);
      setMC(mcData);
      setWF(wfData);

      pollRef.current = setInterval(async () => {
        try {
          const s = await CT_API.getBacktestJob(job.job_id);
          setJobStatus(s.status);
          if (s.status === 'done') {
            clearInterval(pollRef.current);
            setResult(s.result);
            setRunning(false);
          } else if (s.status === 'error') {
            clearInterval(pollRef.current);
            setRunning(false);
            addToast?.('O backtest falhou durante a execução', 'alert');
          }
        } catch (e) {
          clearInterval(pollRef.current);
          setRunning(false);
          addToast?.('Erro ao consultar o status do backtest', 'alert');
        }
      }, 1500);
    } catch (e) {
      setRunning(false);
      console.error('run backtest', e);
      addToast?.('Erro ao iniciar o backtest', 'alert');
    }
  };

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="page-title">Backtest</h1>
          <div className="page-sub">Simulação histórica, Monte Carlo e Walk-Forward</div>
        </div>
      </div>

      {/* Config form */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-head">
          <span className="card-title"><Icon name="settings" />Configuração</span>
          <Btn variant="primary" size="sm" onClick={runBacktest} disabled={running}>
            {running ? '⋯ Rodando…' : <><Icon name="play" size={13} /> Rodar</>}
          </Btn>
        </div>
        <div className="card-pad">
          <div className="grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
            <div className="field">
              <div className="field-label">Par</div>
              <select
                className="input"
                value={config.pair}
                onChange={e => { updateConfig('pair', e.target.value); CT_PAIR.set(e.target.value); }}
              >
                {(pairs ?? PAIRS).map(p => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
            <div className="field">
              <div className="field-label">Estratégia</div>
              <select
                className="input"
                value={config.strategy}
                onChange={e => updateConfig('strategy', e.target.value)}
              >
                {STRATEGIES.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div className="field">
              <div className="field-label">Data início</div>
              <input
                type="date"
                className="input"
                value={config.start_date}
                onChange={e => updateConfig('start_date', e.target.value)}
              />
            </div>
            <div className="field">
              <div className="field-label">Data fim</div>
              <input
                type="date"
                className="input"
                value={config.end_date}
                onChange={e => updateConfig('end_date', e.target.value)}
              />
            </div>
            <div>
              <NumField
                label="Capital inicial ($)"
                value={config.initial_capital}
                onChange={v => updateConfig('initial_capital', v)}
                min={100}
                step={100}
                unit="$"
              />
            </div>
            <div>
              <NumField
                label="Comissão (%)"
                value={config.commission_pct}
                onChange={v => updateConfig('commission_pct', v)}
                min={0}
                max={5}
                step={0.01}
                unit="%"
              />
            </div>
            <div>
              <NumField
                label="Slippage (bps)"
                value={config.slippage_bps}
                onChange={v => updateConfig('slippage_bps', v)}
                min={0}
                max={50}
                step={1}
                unit="bps"
              />
            </div>
          </div>
        </div>
      </div>

      {running && (
        <div style={{ marginBottom: 20 }}>
          <LoadingState label={`Backtest em andamento… (${jobStatus ?? 'iniciando'})`} />
        </div>
      )}

      {(result || mc || wf) && (
        <>
          <div style={{ marginBottom: 14 }}>
            <Tabs
              tabs={[
                { value: 'result',     label: 'Resultado' },
                { value: 'montecarlo', label: 'Monte Carlo' },
                { value: 'walkforward', label: 'Walk-Forward' },
              ]}
              active={tab}
              onChange={setTab}
            />
          </div>

          {tab === 'result' && result && (
            <>
              <div className="grid kpi-row" style={{ marginBottom: 20 }}>
                <MetricCard label="Trades" value={result.total_trades} format="int" />
                <MetricCard label="Win rate" value={result.win_rate * 100} format="pct_direct" />
                <MetricCard label="P&L %" value={result.pnl_pct} format="pct_direct" delta={result.pnl_pct} />
                <MetricCard label="P&L $" value={result.pnl_usdt} format="usd" />
                <MetricCard label="Sharpe" value={fmtNum(result.sharpe)} />
                <MetricCard label="Max drawdown" value={result.max_drawdown} format="pct_direct" delta={result.max_drawdown} />
                <MetricCard label="Profit factor" value={fmtNum(result.profit_factor)} />
                <MetricCard label="Expectancy" value={fmtNum(result.expectancy)} sub="% por trade" />
              </div>
              {result.equity && result.equity.length > 0 && (
                <div className="card">
                  <div className="card-head"><span className="card-title"><Icon name="trending" />Curva de Capital</span></div>
                  <div className="card-pad">
                    <EquityChart points={result.equity} height={220} />
                  </div>
                </div>
              )}
            </>
          )}

          {tab === 'montecarlo' && mc && (
            <div className="grid" style={{ gridTemplateColumns: '280px 1fr' }}>
              <div className="card">
                <div className="card-head"><span className="card-title"><Icon name="activity" />Monte Carlo</span></div>
                <div className="card-pad">
                  <div className="stat-row"><span className="stat-k">Simulações</span><span className="stat-v">{mc.n != null ? fmtNum(mc.n, 0) : '—'}</span></div>
                  <div className="stat-row"><span className="stat-k">P5 (pior)</span><span className="stat-v down">{fmtUsd(mc.p5, 0)}</span></div>
                  <div className="stat-row"><span className="stat-k">P50 (mediana)</span><span className="stat-v">{fmtUsd(mc.p50, 0)}</span></div>
                  <div className="stat-row"><span className="stat-k">P95 (melhor)</span><span className="stat-v up">{fmtUsd(mc.p95, 0)}</span></div>
                  <div className="stat-row">
                    <span className="stat-k">% lucrativas</span>
                    <span className="stat-v">{fmtNum((mc.profitable_pct ?? mc.profitablePct) * 100, 1)}%</span>
                  </div>
                  <div style={{ marginTop: 12 }}>
                    <Badge variant={mc.rejected ? 'down' : 'ok'}>
                      {mc.rejected ? '✗ Estratégia rejeitada' : '✓ Estratégia aprovada'}
                    </Badge>
                  </div>
                </div>
              </div>
              <div className="card">
                <div className="card-head"><span className="card-title">Histograma de resultados</span></div>
                <div className="card-pad">
                  <MonteCarloChart mc={mc} height={220} />
                </div>
              </div>
            </div>
          )}

          {tab === 'walkforward' && wf && (
            <div className="grid" style={{ gridTemplateColumns: '240px 1fr' }}>
              <div className="card">
                <div className="card-head"><span className="card-title"><Icon name="activity" />Walk-Forward</span></div>
                <div className="card-pad">
                  <div style={{ marginBottom: 14 }}>
                    <Badge variant={wf.valid ? 'ok' : 'down'}>
                      {wf.valid ? '✓ Validado' : '✗ Reprovado'}
                    </Badge>
                  </div>
                  <div className="stat-row">
                    <span className="stat-k">Janelas</span>
                    <span className="stat-v">{wf.windows}</span>
                  </div>
                  <div className="stat-row">
                    <span className="stat-k">Desvio Sharpe</span>
                    <span className="stat-v">{fmtNum(wf.sharpe_deviation ?? wf.sharpeDeviation, 3)}</span>
                  </div>
                </div>
              </div>
              <div className="card">
                <div className="card-head"><span className="card-title">Folds treino vs. teste</span></div>
                <div className="card-pad">
                  <FoldTable folds={wf.folds} />
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {!result && !running && (
        <div style={{ padding: '60px 0', textAlign: 'center', color: 'var(--ink-3)' }}>
          <Icon name="play" size={32} style={{ margin: '0 auto 12px', display: 'block', opacity: 0.3 }} />
          <div style={{ fontSize: 14 }}>Configure os parâmetros e clique em Rodar para iniciar o backtest</div>
        </div>
      )}
    </div>
  );
}
window.ScreenBacktest = ScreenBacktest;
