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
            <span className={value < 0 ? 'down' : 'up'}>{value > 0 ? '+' : ''}{fmtNum(value, 1)}%</span>
            <span style={{ color: 'var(--ink-4)' }}> / </span>
            <span style={{ color: 'var(--ink-3)' }}>{fmtNum(limit, 0)}%</span>
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
  const [protections, setProtections] = useState(null);
  const [cb,          setCb]          = useState(null);
  const [kelly,       setKelly]       = useState(null);
  const [equity,      setEquity]      = useState(null);
  const [slots,       setSlots]       = useState(null);
  const [skips,       setSkips]       = useState(null);
  const [metrics,     setMetrics]     = useState(null);
  const [loading,     setLoading]     = useState(true);
  const [error,       setError]       = useState(null);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      CT_API.getProtections(),
      CT_API.getCircuitBreaker(),
      CT_API.getKelly(),
      CT_API.getEquity('90d'),
      CT_API.getSlots().catch(() => null),
      CT_API.getSkips().catch(() => []),
      CT_API.getMetrics('30d').catch(() => null),
    ])
      .then(([p, c, k, eq, sl, sk, m]) => {
        setProtections(Array.isArray(p) ? p : []);
        setCb(c);
        setKelly(k);
        setEquity(Array.isArray(eq) ? eq : []);
        setSlots(sl);
        setSkips(Array.isArray(sk) ? sk : []);
        setMetrics(m);
        setLoading(false);
      })
      .catch(e => { setError(e); setLoading(false); });
  }, []);

  const SKIP_META = {
    confidence_low:       { label: 'Confiança baixa',     cls: 'badge-warn' },
    no_slot:              { label: 'Sem slot livre',      cls: 'badge-info' },
    insufficient_capital: { label: 'Capital insuficiente', cls: 'badge-warn' },
    circuit_breaker:      { label: 'Circuit breaker',     cls: 'badge-down' },
    risk_rejected:        { label: 'Risco reprovou',      cls: 'badge-down' },
  };

  if (loading) return <LoadingState label="Carregando dados de risco…" />;
  if (error)   return <ErrorState message="Erro ao carregar risco" onRetry={() => { setError(null); setLoading(true); }} />;

  // Capital KPIs from the real portfolio metrics (antes vinham do mock global).
  const cap = metrics ? {
    value: metrics.portfolio_value_usdt,
    pnlPct: (metrics.pnl_period_pct ?? 0) * 100,
    exposurePct: (metrics.exposure_pct ?? 0) * 100,
    openPositions: metrics.open_positions,
  } : null;
  // Header badge derived from the real protections (antes derivado do mock global).
  const overallStatus = (protections || []).some(p => p.status && p.status !== 'ok') ? 'warn' : 'ok';
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
        <Badge variant={overallStatus === 'ok' ? 'ok' : 'warn'}>
          {overallStatus}
        </Badge>
      </div>

      {/* Capital KPIs */}
      <div className="grid kpi-row" style={{ marginBottom: 20 }}>
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

      {/* N3: slots + exposição por par (competição por capital) e feed de skips */}
      <div className="grid" style={{ gridTemplateColumns: '1fr 1fr', marginBottom: 20 }}>
        <div className="card">
          <div className="card-head">
            <span className="card-title"><Icon name="list" />Slots & exposição por par</span>
            {slots && <Badge variant="neutral">{slots.slots_used} / {slots.slots_max} slots</Badge>}
          </div>
          <div className="card-pad">
            {!slots || slots.slots_used === 0 ? (
              <EmptyState label="Nenhuma posição aberta — todos os slots livres" />
            ) : (
              <div className="slot-list">
                {slots.exposure.map(e => (
                  <div key={e.symbol} className="slot-row">
                    <span className="slot-sym">{e.symbol}</span>
                    <div className="slot-bar"><div className="slot-fill" style={{ width: Math.min(100, e.pct_of_capital) + '%' }} /></div>
                    <span className="slot-val">{fmtUsd(e.notional)} <span className="desk-muted">· {fmtNum(e.pct_of_capital, 1)}%</span></span>
                  </div>
                ))}
                <div className="slot-free desk-muted">Capital livre: {fmtUsd(slots.capital_free)} de {fmtUsd(slots.capital)}</div>
              </div>
            )}
          </div>
        </div>

        <div className="card">
          <div className="card-head">
            <span className="card-title"><Icon name="activity" />Decisões do ciclo</span>
            <span className="desk-muted" style={{ fontSize: 11.5 }}>por que o sinal não virou ordem</span>
          </div>
          <div className="card-pad">
            {!skips || skips.length === 0 ? (
              <EmptyState label="Nenhum sinal recusado recentemente" />
            ) : (
              <div className="skip-feed">
                {skips.map((s, i) => {
                  const m = SKIP_META[s.reason] || { label: s.reason, cls: 'badge-neutral' };
                  return (
                    <div key={i} className="skip-row">
                      <span className="slot-sym">{s.symbol}</span>
                      <span className={'badge ' + m.cls}>{m.label}</span>
                      {s.reason === 'confidence_low' && s.confidence != null && (
                        <span className="desk-muted">{Math.round(s.confidence * 100)}%</span>
                      )}
                      {s.count > 1 && <span className="skip-count desk-muted">×{s.count}</span>}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
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
                    <span className="stat-v">{fmtNum(kelly.win_rate * 100, 1)}%</span>
                  </div>
                  <div className="stat-row">
                    <span className="stat-k">Ganho médio</span>
                    <span className="stat-v up">+{fmtNum(kelly.avg_win_pct)}%</span>
                  </div>
                  <div className="stat-row">
                    <span className="stat-k">Perda média</span>
                    <span className="stat-v down">-{fmtNum(kelly.avg_loss_pct)}%</span>
                  </div>
                  <div className="stat-row">
                    <span className="stat-k">Full Kelly f*</span>
                    <span className="stat-v">{fmtNum(kelly.full_kelly * 100, 1)}%</span>
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
                    Kelly Fracionado ({fmtNum(kelly.fraction * 100, 0)}× redução)
                  </div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 26, fontWeight: 600, lineHeight: 1 }}>
                    {fmtNum(kelly.fractional_kelly * 100, 1)}%
                  </div>
                  <div style={{ fontSize: 11.5, color: 'var(--ink-3)', marginTop: 4 }}>por trade</div>
                </div>
                {riskOfRuinHigh && (
                  <Badge variant="down">
                    <Icon name="alert" size={11} /> Risco de ruína {fmtNum(kelly.risk_of_ruin, 1)}% ≥ 5%
                  </Badge>
                )}
              </>
            )}
          </div>
        </div>
      </div>

      {/* M9: class-based grid so the rail stacks below the content < 1100px. */}
      <div className="grid grid-chart-rail">
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
