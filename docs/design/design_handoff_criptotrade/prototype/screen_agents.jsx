/* ============================================================
   Criptotrade — Screen: Agentes & Estratégias
   ============================================================ */
const { useState: _useA } = React;

const DOMAIN = {
  trading: { label: 'trading', color: 'var(--up)' },
  security: { label: 'security', color: 'var(--down)' },
  orchestration: { label: 'orchestration', color: 'var(--info)' },
  engineering: { label: 'engineering', color: 'var(--violet)' },
};
const AGENT_STATUS = {
  active: { label: 'ativo', kind: 'ok' }, idle: { label: 'ocioso', kind: 'neutral' },
  error: { label: 'erro', kind: 'down' }, not_implemented: { label: 'stub', kind: 'neutral' },
};

function AgentCard({ a, onConfig }) {
  const st = AGENT_STATUS[a.status]; const dom = DOMAIN[a.domain];
  const canConfig = a.implemented && CT.agentParams[a.id];
  return (
    <div className="card card-pad" style={{ opacity: a.implemented ? 1 : 0.62 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
        <div style={{ width: 34, height: 34, borderRadius: 9, background: 'var(--surface-3)', display: 'grid', placeItems: 'center', color: dom.color }}>
          <Icon name={a.id === 'strategy' ? 'target' : a.id === 'risk' ? 'shield' : a.id === 'behavioral' ? 'brain' : a.id === 'orchestrator' ? 'layers' : a.id === 'execution' ? 'zap' : 'agents'} size={18} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13.5, fontWeight: 600 }}>{a.name}</div>
          <div className="muted" style={{ fontSize: 11 }}>{a.desc}</div>
        </div>
        <Badge kind={st.kind} dot>{st.label}</Badge>
      </div>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 11.5 }}>
        <span className="chip" style={{ fontSize: 10.5, color: dom.color }}>{dom.label}</span>
        <span className="muted mono">{a.cycles} ciclos hoje</span>
        <span className="muted mono" style={{ marginLeft: 'auto' }}>{a.last || '—'}</span>
      </div>
      <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
        <Btn sm icon="settings" data-tip="Abre os parâmetros configuráveis deste agente." onClick={() => onConfig(a)} disabled={!canConfig}>Configurar</Btn>
        <span className="muted" style={{ fontSize: 10.5, marginLeft: 'auto' }}>
          {canConfig ? `${CT.agentParams[a.id].length} parâmetros` : a.implemented ? 'sem parâmetros' : 'não implementado'}
        </span>
      </div>
    </div>
  );
}

/* fmt for slider readouts */
const _agFmt = { pct: v => Math.round(v * 100) + '%', pct_direct: v => v + '%' };

function AgentConfigDrawer({ agent, toast, onClose }) {
  const params = CT.agentParams[agent.id] || [];
  const [vals, setVals] = _useA(() => Object.fromEntries(params.map(p => [p.key, p.value])));
  const [dirty, setDirty] = _useA(false);
  const dom = DOMAIN[agent.domain];
  const set = (k, v) => { setVals(o => ({ ...o, [k]: v })); setDirty(true); };
  const hasSensitive = params.some(p => p.sensitive);
  const save = () => { setDirty(false); toast(`Config de ${agent.name} salva · PATCH /v1/agents/${agent.id}/config`); onClose(); };
  return (
    <>
      <div className="drawer-scrim" onClick={onClose} />
      <div className="drawer">
        <div className="card-head" style={{ borderRadius: 0 }}>
          <div className="card-title" style={{ gap: 9 }}>
            <span style={{ width: 28, height: 28, borderRadius: 8, background: 'var(--surface-3)', display: 'grid', placeItems: 'center', color: dom.color }}>
              <Icon name={agent.id === 'strategy' ? 'target' : agent.id === 'risk' ? 'shield' : agent.id === 'behavioral' ? 'brain' : agent.id === 'orchestrator' ? 'layers' : 'zap'} size={16} />
            </span>
            Configurar agente
          </div>
          <button className="btn btn-ghost" style={{ padding: 6 }} onClick={onClose}><Icon name="x" size={18} /></button>
        </div>
        <div style={{ overflowY: 'auto', padding: 18, flex: 1 }}>
          <div style={{ marginBottom: 16 }}>
            <b style={{ fontSize: 16 }}>{agent.name}</b>
            <div className="muted" style={{ fontSize: 12, marginTop: 3, lineHeight: 1.45 }}>{agent.desc}</div>
            <div style={{ display: 'flex', gap: 7, marginTop: 8, flexWrap: 'wrap' }}>
              <span className="chip" style={{ color: dom.color }}>{dom.label}</span>
              <span className="chip mono" style={{ fontSize: 10.5 }}>{`GET·PATCH /v1/agents/${agent.id}/config`}</span>
            </div>
          </div>

          <div className="hr" style={{ margin: '0 0 16px' }} />

          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {params.map(p => {
              if (p.type === 'slider')
                return <SliderField key={p.key} label={p.label} value={vals[p.key]} onChange={v => set(p.key, v)} min={p.min} max={p.max} step={p.step} fmt={_agFmt[p.fmt] || (v => v)} hint={p.hint} />;
              if (p.type === 'num')
                return <NumField key={p.key} label={p.label} value={vals[p.key]} onChange={v => set(p.key, v)} min={p.min} max={p.max} step={p.step} suffix={p.suffix} decimals={p.decimals || 0} hint={p.hint} />;
              if (p.type === 'toggle')
                return (
                  <div key={p.key} style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                    <div style={{ flex: 1 }}>
                      <div className="field-label">{p.label}</div>
                      {p.hint && <div className="field-hint">{p.hint}</div>}
                    </div>
                    <Toggle on={vals[p.key]} onChange={v => set(p.key, v)} />
                  </div>
                );
              if (p.type === 'select')
                return (
                  <div key={p.key} className="field">
                    <span className="field-label">{p.label}</span>
                    <div className="input-wrap">
                      <select className="input" style={{ fontFamily: 'var(--sans)' }} value={vals[p.key]} onChange={e => set(p.key, e.target.value)}>
                        {p.options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                      </select>
                    </div>
                  </div>
                );
              return null;
            })}
          </div>

          {hasSensitive && (
            <div className="card card-pad" style={{ marginTop: 18, borderLeft: '3px solid var(--warn)', fontSize: 12, lineHeight: 1.45, display: 'flex', gap: 8 }}>
              <Icon name="warn" size={15} style={{ color: 'var(--warn)', flexShrink: 0 }} />
              <span>Este agente tem parâmetros sensíveis (risco/autonomia). A alteração é registrada no ledger com o operador.</span>
            </div>
          )}
        </div>
        <div style={{ borderTop: '1px solid var(--border)', padding: 14, display: 'flex', gap: 10, alignItems: 'center' }}>
          <span className="muted" style={{ fontSize: 11.5 }}>{dirty ? 'alterações não salvas' : 'sem alterações'}</span>
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
            <Btn onClick={onClose}>Cancelar</Btn>
            <Btn kind="primary" icon="check" onClick={save} disabled={!dirty}>Salvar</Btn>
          </div>
        </div>
      </div>
    </>
  );
}

function StratField({ label, value, onChange, suffix, step, min, max, decimals }) {
  return <NumField label={label} value={value} onChange={onChange} suffix={suffix} step={step} min={min} max={max} decimals={decimals} />;
}

function AgentsScreen({ toast }) {
  const [strat, setStrat] = _useA({ ...CT.strategies });
  const [tab, setTab] = _useA('grid');
  const [cfgAgent, setCfgAgent] = _useA(null);
  const setG = (k, v) => setStrat(s => ({ ...s, grid: { ...s.grid, [k]: v } }));
  const setD = (k, v) => setStrat(s => ({ ...s, dca: { ...s.dca, [k]: v } }));
  const setM = (k, v) => setStrat(s => ({ ...s, meanReversion: { ...s.meanReversion, [k]: v } }));

  return (
    <div className="content-inner screen-enter">
      <div className="page-head">
        <div>
          <div className="page-title">Agentes & Estratégias</div>
          <div className="page-sub">Pipeline: Strategy → Risk → Guardrails → HITL → Execution · {CT.agents.filter(a => a.implemented).length} agentes ativos</div>
        </div>
        <span className="chip"><Icon name="refresh" size={13} />ciclo a cada 60s</span>
      </div>

      {/* agent cards */}
      <div className="grid" style={{ gridTemplateColumns: 'repeat(3,1fr)', marginBottom: 22 }}>
        {CT.agents.map(a => <AgentCard key={a.id} a={a} onConfig={setCfgAgent} />)}
      </div>

      {/* detail panels */}
      <div className="grid" style={{ gridTemplateColumns: '1fr 1fr 1fr', gap: 16, marginBottom: 22 }}>
        {/* strategy agent */}
        <div className="card">
          <CardHead icon="target" title="Strategy Agent" right={<Badge kind="ok" dot>ativo</Badge>} />
          <div className="card-pad">
            <StatRow k="Regime detectado" v={<Badge kind="info">{CT.regime.label}</Badge>} />
            <StatRow k="Estratégia ativa" v={<span className="chip">{CT.signal.strategy}</span>} />
            <StatRow k="Confidence score" v={Math.round(CT.regime.confidence * 100) + '%'} />
            <div style={{ marginTop: 14 }}><ConfidenceBreakdown /></div>
          </div>
        </div>

        {/* risk agent */}
        <div className="card">
          <CardHead icon="shield" title="Risk Agent" right={<Badge kind="ok" dot>ativo</Badge>} />
          <div className="card-pad">
            <StatRow k="Circuit breaker" v={<Badge kind="ok" dot>fechado</Badge>} />
            <StatRow k="Proteções de capital" v={<Badge kind="warn">aviso semanal</Badge>} />
            <div className="label-xs" style={{ margin: '14px 0 8px' }}>Guardrails ativos</div>
            {CT.guardrails.map((g, i) => (
              <div key={i} className="stat-row" style={{ padding: '7px 0' }}>
                <span style={{ display: 'flex', gap: 7, alignItems: 'center', fontSize: 12 }}>
                  <Icon name={g.ok ? 'check' : 'x'} size={14} style={{ color: g.ok ? 'var(--up)' : 'var(--down)' }} />{g.key}
                </span>
                <span className="mono" style={{ fontSize: 11 }}><span className="muted">{g.limit}</span></span>
              </div>
            ))}
          </div>
        </div>

        {/* behavioral guard */}
        <div className="card">
          <CardHead icon="brain" title="Behavioral Guard" right={<Badge kind="warn" dot>1 alerta</Badge>} />
          <div className="card-pad" style={{ paddingTop: 12 }}>
            {CT.behavioral.map((b, i) => (
              <div key={i} style={{ padding: '10px 0', borderBottom: i < CT.behavioral.length - 1 ? '1px solid var(--border)' : 'none' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 3 }}>
                  <span style={{ fontSize: 12.5, fontWeight: 600 }}>{b.key}</span>
                  <Badge kind={b.status === 'ok' ? 'ok' : 'warn'} dot>{b.status === 'ok' ? 'ok' : 'detectado'}</Badge>
                </div>
                <div className="muted" style={{ fontSize: 11, lineHeight: 1.4 }}>{b.desc}</div>
                <div style={{ fontSize: 11.5, color: 'var(--ink-2)', marginTop: 5 }}>{b.detail}</div>
                {b.action && <div style={{ marginTop: 6 }}><span className="chip" style={{ color: 'var(--warn)' }}><Icon name="zap" size={12} />{b.action}</span></div>}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* strategy config */}
      <div className="card">
        <CardHead icon="settings" title="Configuração das estratégias"
          right={<div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <Seg options={[{ value: 'grid', label: 'Grid' }, { value: 'dca', label: 'DCA' }, { value: 'mr', label: 'Mean Reversion' }]} value={tab} onChange={setTab} />
            <Btn kind="primary" sm icon="check" data-tip="Salva a configuração da estratégia selecionada." onClick={() => toast('Configuração da estratégia salva')}>Salvar</Btn>
          </div>} />
        <div className="card-pad">
          {tab === 'grid' && <>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <div><b style={{ fontSize: 14 }}>Grid Trading</b> <span className="muted" style={{ fontSize: 12 }}>— ordens escalonadas em faixa</span></div>
              <Badge kind="info">ativo em: regime lateral</Badge>
            </div>
            <div className="grid" style={{ gridTemplateColumns: 'repeat(3,1fr)', gap: 18 }}>
              <StratField label="Número de níveis" value={strat.grid.levels} onChange={v => setG('levels', v)} step={1} min={2} max={30} />
              <StratField label="Espaçamento entre níveis" value={strat.grid.spacingPct} onChange={v => setG('spacingPct', v)} suffix="%" step={0.1} min={0.1} max={5} decimals={1} />
              <StratField label="Capital alocado total" value={strat.grid.allocPct} onChange={v => setG('allocPct', v)} suffix="%" step={1} min={1} max={50} />
            </div>
          </>}
          {tab === 'dca' && <>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <div><b style={{ fontSize: 14 }}>DCA Otimizado</b> <span className="muted" style={{ fontSize: 12 }}>— entradas escalonadas em pullback</span></div>
              <Badge kind="info">ativo em: lateral, alta forte</Badge>
            </div>
            <div className="grid" style={{ gridTemplateColumns: 'repeat(4,1fr)', gap: 18 }}>
              <StratField label="Número de entradas" value={strat.dca.entries} onChange={v => setD('entries', v)} step={1} min={1} max={10} />
              <StratField label="Espaçamento entre entradas" value={strat.dca.spacingPct} onChange={v => setD('spacingPct', v)} suffix="%" step={0.1} min={0.1} max={5} decimals={1} />
              <StratField label="Stop loss" value={strat.dca.stopPct} onChange={v => setD('stopPct', v)} suffix="%" step={0.5} min={1} max={20} decimals={1} />
              <StratField label="RSI oversold threshold" value={strat.dca.rsiOversold} onChange={v => setD('rsiOversold', v)} step={1} min={10} max={50} />
            </div>
          </>}
          {tab === 'mr' && <>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <div><b style={{ fontSize: 14 }}>Mean Reversion</b> <span className="muted" style={{ fontSize: 12 }}>— reversão à média</span></div>
              <Badge kind="neutral">sob demanda</Badge>
            </div>
            <div className="grid" style={{ gridTemplateColumns: 'repeat(4,1fr)', gap: 18 }}>
              <StratField label="RSI oversold" value={strat.meanReversion.rsiOversold} onChange={v => setM('rsiOversold', v)} step={1} min={10} max={45} />
              <StratField label="RSI overbought" value={strat.meanReversion.rsiOverbought} onChange={v => setM('rsiOverbought', v)} step={1} min={55} max={90} />
              <StratField label="Multiplicador ATR (stop)" value={strat.meanReversion.atrMult} onChange={v => setM('atrMult', v)} suffix="×" step={0.1} min={0.5} max={5} decimals={1} />
              <StratField label="Risk/reward mínimo" value={strat.meanReversion.minRR} onChange={v => setM('minRR', v)} suffix="×" step={0.1} min={1} max={5} decimals={1} />
            </div>
          </>}
        </div>
      </div>

      {cfgAgent && <AgentConfigDrawer key={cfgAgent.id} agent={cfgAgent} toast={toast} onClose={() => setCfgAgent(null)} />}
    </div>
  );
}

window.AgentsScreen = AgentsScreen;
