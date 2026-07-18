/* ============================================================
   Criptotrade — Screen: Risco & Capital (HERO)
   ============================================================ */
const { useState: _useStateRisk } = React;

function ProtectionCard({ title, d }) {
  const pct = Math.min(100, Math.abs(d.value) / Math.abs(d.limit) * 100);
  const kind = d.status === 'ok' ? 'ok' : d.status === 'warn' ? 'warn' : 'down';
  const barColor = d.status === 'ok' ? 'var(--up)' : d.status === 'warn' ? 'var(--warn)' : 'var(--down)';
  return (
    <div className="card card-pad">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <span className="label-xs">{title}</span>
        <Badge kind={kind} dot>{d.status === 'ok' ? 'OK' : d.status === 'warn' ? 'Aviso' : 'Pausado'}</Badge>
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
        <span className="mono" style={{ fontSize: 26, fontWeight: 500, color: barColor }}>{fmtPct(d.value)}</span>
        <span className="muted mono" style={{ fontSize: 12 }}>/ limite {fmtPct(d.limit)}</span>
      </div>
      <div style={{ margin: '12px 0 8px' }}><Meter value={pct} color={barColor} height={6} /></div>
      <div style={{ fontSize: 11.5, color: 'var(--ink-3)', display: 'flex', gap: 6, alignItems: 'center' }}>
        <Icon name="info" size={13} /> {d.action}
      </div>
    </div>
  );
}

function RiskScreen({ toast }) {
  const C = CT.capital, dd = CT.drawdown, cb = CT.circuitBreaker, k = CT.kelly;
  const [cfg, setCfg] = _useStateRisk({ ...CT.riskConfig });
  const set = (key, v) => setCfg(c => ({ ...c, [key]: v }));
  const ror = k.riskOfRuin;
  const rorHigh = ror > 5;

  return (
    <div className="content-inner screen-enter">
      <div className="page-head">
        <div>
          <div className="page-title">Risco & Capital</div>
          <div className="page-sub">Proteções automáticas, dimensionamento Kelly e circuit breaker — capital base {fmtUsd(C.initial, 0)}</div>
        </div>
        <Badge kind={dd.overallStatus === 'ok' ? 'ok' : 'warn'} dot>
          Status global: {dd.overallStatus === 'ok' ? 'OK' : 'Aviso · drawdown semanal'}
        </Badge>
      </div>

      {/* KPI row */}
      <div className="grid" style={{ gridTemplateColumns: 'repeat(4,1fr)', marginBottom: 16 }}>
        <KPI label="Valor do portfólio" icon="dollar" value={fmtUsd(C.value)} sub={`Inicial ${fmtUsd(C.initial, 0)}`} />
        <KPI label="P&L total" icon="trendUp" value={fmtPct(C.pnlPct)} accent="var(--up)" sub={`+${fmtUsd(C.value - C.initial)}`} />
        <KPI label="Exposição" icon="layers" value={fmtPct(C.exposurePct)} sub={`${C.openPositions} posições abertas`} />
        <KPI label="Risco de Ruína" icon="shield" value={fmtPct(ror)} accent={rorHigh ? 'var(--down)' : 'var(--up)'} sub={rorHigh ? 'ACIMA do limite 5%' : 'dentro do limite (< 5%)'} />
      </div>

      {/* Capital protections */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '4px 0 12px' }}>
        <Icon name="shield" size={15} style={{ color: 'var(--ink-3)' }} />
        <h3 style={{ fontSize: 14 }}>Proteções de Capital</h3>
        <span className="muted" style={{ fontSize: 12 }}>— pausas automáticas por drawdown</span>
      </div>
      <div className="grid" style={{ gridTemplateColumns: 'repeat(3,1fr)', marginBottom: 22 }}>
        <ProtectionCard title="Drawdown Diário" d={dd.daily} />
        <ProtectionCard title="Drawdown Semanal" d={dd.weekly} />
        <ProtectionCard title="Drawdown Mensal" d={dd.monthly} />
      </div>

      {/* Circuit breaker + equity */}
      <div className="grid" style={{ gridTemplateColumns: '340px 1fr', marginBottom: 22 }}>
        <div className="card">
          <CardHead icon="lock" title="Circuit Breaker" right={<Badge kind={cb.status === 'closed' ? 'ok' : 'down'} dot>{cb.status === 'closed' ? 'Fechado' : 'Aberto'}</Badge>} />
          <div className="card-pad">
            <div style={{ fontSize: 12, color: 'var(--ink-2)', marginBottom: 14 }}>
              {cb.status === 'closed' ? 'Operando normalmente. Disparos abrem o breaker e ativam cooldown de ' + cb.cooldownHours + 'h.' : 'Bloqueado — cooldown em andamento.'}
            </div>
            {cb.triggers.map((t, i) => {
              const pct = Math.min(100, Math.abs(t.value) / Math.abs(t.limit) * 100);
              const isCount = t.key.toLowerCase().includes('consecut');
              return (
                <div key={i} style={{ marginBottom: 14 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5, marginBottom: 6 }}>
                    <span style={{ color: 'var(--ink-2)' }}>{t.key}</span>
                    <span className="mono" style={{ fontWeight: 600 }}>{isCount ? `${t.value} / ${t.limit}` : fmtPct(t.value)}</span>
                  </div>
                  <Meter value={pct} color={t.hit ? 'var(--down)' : pct > 70 ? 'var(--warn)' : 'var(--ink)'} height={6} />
                </div>
              );
            })}
            <div className="hr" style={{ margin: '14px 0' }} />
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12.5 }}>
              <Icon name="clock" size={15} style={{ color: 'var(--ink-3)' }} />
              <span style={{ color: 'var(--ink-2)' }}>Cooldown</span>
              <span className="mono" style={{ marginLeft: 'auto', fontWeight: 600 }}>{cb.cooldownRemaining > 0 ? cb.cooldownRemaining + 'h restantes' : 'inativo'}</span>
            </div>
          </div>
        </div>

        <div className="card">
          <CardHead icon="pulse" title="Curva de capital & drawdown" sub="90 dias" right={<span className="mono" style={{ fontSize: 12, fontWeight: 600, color: 'var(--up)' }}>{fmtUsd(C.value)}</span>} />
          <div style={{ padding: '14px 14px 6px' }}>
            <EquityChart data={CT.equity} height={210} />
          </div>
        </div>
      </div>

      {/* Kelly */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '4px 0 12px' }}>
        <Icon name="target" size={15} style={{ color: 'var(--ink-3)' }} />
        <h3 style={{ fontSize: 14 }}>Kelly Criterion</h3>
        <span className="muted" style={{ fontSize: 12 }}>— dimensionamento ótimo de posição ({k.trades} trades)</span>
      </div>
      <div className="grid" style={{ gridTemplateColumns: '1fr 1fr 1fr', marginBottom: 22 }}>
        <div className="card card-pad">
          <span className="label-xs">Estatísticas históricas</span>
          <div style={{ marginTop: 8 }}>
            <StatRow k="Win rate" v={fmtPct(k.winRate * 100)} vColor="var(--up)" />
            <StatRow k="Média de ganhos" v={'+' + fmtPct(k.avgWinPct)} vColor="var(--up)" />
            <StatRow k="Média de perdas" v={fmtPct(-k.avgLossPct)} vColor="var(--down)" />
            <StatRow k="Payoff ratio" v={fmtNum(k.avgWinPct / k.avgLossPct) + '×'} />
          </div>
        </div>
        <div className="card card-pad">
          <span className="label-xs">Fração ótima</span>
          <div style={{ marginTop: 8 }}>
            <StatRow k="f* (Kelly completo)" v={fmtPct(k.fullKelly * 100)} />
            <StatRow k="Multiplicador" v={fmtNum(k.fraction, 2) + '×'} />
            <StatRow k="f* fracionado (produção)" v={fmtPct(k.fractionalKelly * 100)} vColor="var(--ink)" vClass="tnum" />
            <StatRow k="Risco de ruína" v={fmtPct(ror)} vColor={rorHigh ? 'var(--down)' : 'var(--up)'} />
          </div>
        </div>
        <div className="card card-pad">
          <span className="label-xs">Taxa de crescimento g(f)</span>
          <div style={{ marginTop: 10 }}>
            <KellyCurve fullKelly={k.fullKelly} fraction={k.fractionalKelly} height={150} />
          </div>
          <div style={{ fontSize: 11, color: 'var(--ink-3)', marginTop: 4 }}>
            Usamos <b className="mono">0.25×</b> do Kelly completo — sacrifica crescimento por estabilidade.
          </div>
        </div>
      </div>

      {/* Editable config */}
      <div className="card">
        <CardHead icon="settings" title="Parâmetros de risco" sub="editável"
          right={<Btn kind="primary" sm icon="check" data-tip="Salva os parâmetros de risco (limites de posição, stop, risk-reward)." onClick={() => toast('Parâmetros de risco salvos')}>Salvar</Btn>} />
        <div className="card-pad">
          <div className="grid" style={{ gridTemplateColumns: 'repeat(3,1fr)', gap: 24, marginBottom: 22 }}>
            <SliderField label="Fração Kelly" value={cfg.kellyFraction} onChange={v => set('kellyFraction', v)} min={0.1} max={1} step={0.05} fmt={v => fmtNum(v, 2) + '×'} hint="Padrão 0.25× — quanto do Kelly completo aplicar" />
            <SliderField label="Tamanho mínimo de posição" value={cfg.minPositionPct} onChange={v => set('minPositionPct', v)} min={0.1} max={2} step={0.1} fmt={v => fmtPct(v)} hint="Padrão 0.5% do portfólio" />
            <SliderField label="Tamanho máximo de posição" value={cfg.maxPositionPct} onChange={v => set('maxPositionPct', v)} min={1} max={10} step={0.5} fmt={v => fmtPct(v)} hint="Padrão 5% — teto do guardrail" />
          </div>
          <div className="hr" style={{ marginBottom: 18 }} />
          <span className="label-xs" style={{ display: 'block', marginBottom: 14 }}>Limites de drawdown</span>
          <div className="grid" style={{ gridTemplateColumns: 'repeat(3,1fr)', gap: 18 }}>
            <NumField label="Diário — pausa o dia" value={cfg.ddDaily} onChange={v => set('ddDaily', v)} step={0.5} min={1} max={10} suffix="%" decimals={1} />
            <NumField label="Semanal — reduz à metade" value={cfg.ddWeekly} onChange={v => set('ddWeekly', v)} step={0.5} min={2} max={20} suffix="%" decimals={1} />
            <NumField label="Mensal — suspende e revisa" value={cfg.ddMonthly} onChange={v => set('ddMonthly', v)} step={1} min={5} max={40} suffix="%" decimals={0} />
          </div>
        </div>
      </div>
    </div>
  );
}

window.RiskScreen = RiskScreen;
