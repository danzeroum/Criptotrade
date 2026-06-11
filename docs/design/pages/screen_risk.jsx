/* ============================================================
   Criptotrade — Screen: Risk Management
   ============================================================ */
const { useState, useEffect } = React;

function DrawdownRow({ label, value, limit, status, action }) {
  const variant = status === 'ok' ? 'ok' : status === 'warn' ? 'warn' : 'down';
  const pct = Math.min(100, Math.abs(value / limit) * 100);
  return (
    <div style={{ marginBottom: 18 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
        <span style={{ fontSize: 13, fontWeight: 500 }}>{label}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontFamily: 'var(--mono)', fontSize: 13 }}>
            <span className={value < 0 ? 'down' : 'up'}>{value > 0 ? '+' : ''}{value?.toFixed(1)}%</span>
            <span style={{ color: 'var(--ink-4)' }}> / </span>
            <span style={{ color: 'var(--ink-3)' }}>{limit?.toFixed(0)}%</span>
          </span>
          <Badge variant={variant}>{status}</Badge>
        </div>
      </div>
      <Meter value={pct} max={100} warn={70} crit={90} />
      {action && (
        <div style={{ fontSize: 11, color: 'var(--ink-3)', marginTop: 4 }}>Ação: {action}</div>
      )}
    </div>
  );
}

function ScreenRisk() {
  const mock = !!window.USE_MOCK_DATA;

  const mockProtections = [
    { scope: 'daily',   value: CT.drawdown.daily.value,   limit: CT.drawdown.daily.limit,   status: CT.drawdown.daily.status,   action: CT.drawdown.daily.action },
    { scope: 'weekly',  value: CT.drawdown.weekly.value,  limit: CT.drawdown.weekly.limit,  status: CT.drawdown.weekly.status,  action: CT.drawdown.weekly.action },
    { scope: 'monthly', value: CT.drawdown.monthly.value, limit: CT.drawdown.monthly.limit, status: CT.drawdown.monthly.status, action: CT.drawdown.monthly.action },
  ];
  const mockCB = {
    status:            CT.circuitBreaker.status === 'closed' ? 'armed' : 'triggered',
    triggers:          CT.circuitBreaker.triggers.map(t => t.key),
    cooldown_hours:    CT.circuitBreaker.cooldownHours,
    cooldown_remaining:CT.circuitBreaker.cooldownRemaining,
  };
  const mockKelly = {
    win_rate:         CT.kelly.winRate,
    avg_win_pct:      CT.kelly.avgWinPct,
    avg_loss_pct:     CT.kelly.avgLossPct,
    full_kelly:       CT.kelly.fullKelly,
    fraction:         CT.kelly.fraction,
    fractional_kelly: CT.kelly.fractionalKelly,
    risk_of_ruin:     CT.kelly.riskOfRuin,
    trades:           CT.kelly.trades,
  };
  const mockEquity = CT.equity.map(e => ({ t: String(e.i), equity: e.equity, drawdown: e.dd }));

  const [protections, setProtections] = useState(mock ? mockProtections : null);
  const [cb,          setCb]          = useState(mock ? mockCB : null);
  const [kelly,       setKelly]       = useState(mock ? mockKelly : null);
  const [equity,      setEquity]      = useState(mock ? mockEquity : null);
  const [loading,     setLoading]     = useState(!mock);
  const [error,       setError]       = useState(null);

  useEffect(() => {
    if (mock) return;
    setLoading(true);
    Promise.all([
      CT_API.getProtections(),
      CT_API.getCircuitBreaker(),
      CT_API.getKelly(),
      CT_API.getEquity('90d'),
    ])
      .then(([p, c, k, eq]) => {
        setProtections(Array.isArray(p) ? p : []);
        setCb(c);
        setKelly(k);
        setEquity(Array.isArray(eq) ? eq : []);
        setLoading(false);
      })
      .catch(e => { setError(e); setLoading(false); });
  }, [mock]);

  if (loading) return <LoadingState label="Carregando dados de risco…" />;
  if (error)   return <ErrorState message="Erro ao carregar risco" onRetry={() => { setError(null); setLoading(true); }} />;

  const cap = CT.capital;
  const cbArmed = cb?.status === 'armed';
  const kellyOk = kelly?.data_quality === 'ok';
  const riskOfRuinHigh = kellyOk && kelly.risk_of_ruin != null && kelly.risk_of_ruin > 5;

  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="page-title">Gestão de Risco</h1>
          <div className="page-sub">Proteções, circuit breaker, Kelly e curva de capital</div>
        </div>
        <Badge variant={CT.drawdown.overallStatus === 'ok' ? 'ok' : 'warn'}>
          {CT.drawdown.overallStatus}
        </Badge>
      </div>

      {/* Capital KPIs */}
      <div className="grid" style={{ gridTemplateColumns: 'repeat(5, 1fr)', marginBottom: 20 }}>
        <div className="card">
          <KPI label="Capital atual" value={cap?.value} format="usd" icon="dollar" />
        </div>
        <div className="card">
          <KPI label="P&L total" value={cap?.pnlPct} format="pct_direct" delta={cap?.pnlPct} icon="trending" />
        </div>
        <div className="card">
          <KPI label="Exposição" value={cap?.exposurePct} format="pct_direct" icon="activity" />
        </div>
        <div className="card">
          <KPI label="Posições abertas" value={cap?.openPositions} format="int" icon="list" />
        </div>
        <div className="card">
          <KPI
            label="Risco de ruína"
            value={kellyOk ? kelly.risk_of_ruin : null}
            format="pct_direct"
            icon="alert"
            sub={riskOfRuinHigh ? '⚠ Acima do limite 5%' : kellyOk ? 'Dentro do limite' : 'Dados insuficientes'}
          />
        </div>
      </div>

      <div className="grid" style={{ gridTemplateColumns: '1fr 1fr', marginBottom: 20 }}>
        {/* Equity Curve */}
        <div className="card">
          <div className="card-head">
            <span className="card-title"><Icon name="trending" />Curva de Capital (90d)</span>
          </div>
          <div className="card-pad">
            {equity && equity.length > 0 ? (
              <EquityChart points={equity} height={200} />
            ) : (
              <EmptyState label="Sem dados de equity" />
            )}
          </div>
        </div>

        {/* Kelly */}
        <div className="card">
          <div className="card-head">
            <span className="card-title"><Icon name="zap" />Kelly Criterion</span>
          </div>
          <div className="card-pad">
            {!kelly ? null : !kellyOk ? (
              <EmptyState label={`Dados insuficientes (${kelly.trades} trade${kelly.trades !== 1 ? 's' : ''} — mínimo ${10})`} />
            ) : (
              <>
                <div style={{ marginBottom: 14 }}>
                  <div className="stat-row">
                    <span className="stat-k">Win rate</span>
                    <span className="stat-v">{(kelly.win_rate * 100).toFixed(1)}%</span>
                  </div>
                  <div className="stat-row">
                    <span className="stat-k">Ganho médio</span>
                    <span className="stat-v up">+{kelly.avg_win_pct?.toFixed(2)}%</span>
                  </div>
                  <div className="stat-row">
                    <span className="stat-k">Perda média</span>
                    <span className="stat-v down">-{kelly.avg_loss_pct?.toFixed(2)}%</span>
                  </div>
                  <div className="stat-row">
                    <span className="stat-k">Full Kelly f*</span>
                    <span className="stat-v">{(kelly.full_kelly * 100).toFixed(1)}%</span>
                  </div>
                  <div className="stat-row">
                    <span className="stat-k">Trades amostrados</span>
                    <span className="stat-v">{kelly.trades}</span>
                  </div>
                </div>
                <div style={{
                  padding: '12px 14px', background: 'var(--surface-3)',
                  borderRadius: 'var(--r)', marginBottom: 12,
                }}>
                  <div style={{ fontSize: 11.5, color: 'var(--ink-3)', marginBottom: 4 }}>
                    Kelly Fracionado ({(kelly.fraction * 100).toFixed(0)}× redução)
                  </div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 26, fontWeight: 600, lineHeight: 1 }}>
                    {(kelly.fractional_kelly * 100).toFixed(1)}%
                  </div>
                  <div style={{ fontSize: 11.5, color: 'var(--ink-3)', marginTop: 4 }}>por trade</div>
                </div>
                {riskOfRuinHigh && (
                  <Badge variant="down">
                    <Icon name="alert" size={11} /> Risco de ruína {kelly.risk_of_ruin?.toFixed(1)}% ≥ 5%
                  </Badge>
                )}
              </>
            )}
          </div>
        </div>
      </div>

      <div className="grid" style={{ gridTemplateColumns: '1fr 300px' }}>
        {/* Drawdown protections */}
        <div className="card">
          <div className="card-head">
            <span className="card-title"><Icon name="shield" />Proteções de Drawdown</span>
          </div>
          <div className="card-pad">
            {protections ? protections.map(p => (
              <DrawdownRow
                key={p.scope}
                label={p.scope === 'daily' ? 'Diário' : p.scope === 'weekly' ? 'Semanal' : 'Mensal'}
                value={p.value}
                limit={p.limit}
                status={p.status}
                action={p.action}
              />
            )) : <EmptyState label="Sem dados de proteção" />}
          </div>
        </div>

        {/* Circuit Breaker */}
        <div className="card">
          <div className="card-head">
            <span className="card-title"><Icon name="zap" />Circuit Breaker</span>
            <Badge variant={cbArmed ? 'ok' : 'down'}>{cb?.status ?? '…'}</Badge>
          </div>
          <div className="card-pad">
            {cb ? (
              <>
                {(cb.triggers ?? []).map((t, i) => (
                  <div key={i} style={{
                    display: 'flex', alignItems: 'center', gap: 9,
                    padding: '9px 0', borderBottom: '1px solid var(--border)',
                  }}>
                    <Icon
                      name={cbArmed ? 'check' : 'alert'}
                      size={13}
                      className={cbArmed ? 'up' : 'down'}
                    />
                    <span style={{ fontSize: 12.5 }}>{t}</span>
                  </div>
                ))}
                <div style={{ marginTop: 14 }}>
                  <div className="stat-row">
                    <span className="stat-k">Cooldown</span>
                    <span className="stat-v">{cb.cooldown_hours ?? 24}h</span>
                  </div>
                  {cb.cooldown_remaining > 0 && (
                    <div style={{ marginTop: 8 }}>
                      <Badge variant="warn">
                        <Icon name="clock" size={11} />
                        {cb.cooldown_remaining}h restantes
                      </Badge>
                    </div>
                  )}
                </div>
              </>
            ) : <EmptyState label="Sem dados" />}
          </div>
        </div>
      </div>
    </div>
  );
}
window.ScreenRisk = ScreenRisk;
