/* ============================================================
   Criptotrade — Screen: Agents
   ============================================================ */
const { useState, useEffect } = React;

const DOMAIN_VARIANT = {
  trading:       'info',
  security:      'warn',
  orchestration: 'violet',
};

const AGENT_STATUS_VARIANT = {
  active:          'ok',
  idle:            'neutral',
  not_implemented: 'neutral',
  error:           'down',
};

const AGENT_STATUS_LABEL = {
  active:          'Ativo',
  idle:            'Ocioso',
  not_implemented: 'Stub',
  error:           'Erro',
};

// One editable field per parameter; control inferred from the value's type
// (the contract carries values, not a schema).
function AgentParamField({ name, value, onChange }) {
  const label = name.replace(/_/g, ' ');
  if (typeof value === 'number') {
    return <NumField label={label} value={value} step={Number.isInteger(value) ? 1 : 0.1} onChange={(v) => onChange(name, v)} />;
  }
  if (typeof value === 'boolean') {
    return (
      <div>
        <div style={{ fontSize: 11.5, color: 'var(--ink-3)', fontWeight: 500, marginBottom: 4 }}>{label}</div>
        <Seg options={[{ value: true, label: 'Sim' }, { value: false, label: 'Não' }]} value={value} onChange={(v) => onChange(name, v)} />
      </div>
    );
  }
  if (typeof value === 'string') {
    return (
      <label style={{ display: 'block' }}>
        <span style={{ fontSize: 11.5, color: 'var(--ink-3)', fontWeight: 500 }}>{label}</span>
        <input className="input" value={value} onChange={(e) => onChange(name, e.target.value)} style={{ width: '100%', marginTop: 4 }} />
      </label>
    );
  }
  return (
    <div>
      <div style={{ fontSize: 11.5, color: 'var(--ink-3)', fontWeight: 500, marginBottom: 4 }}>{label}</div>
      <code style={{ fontSize: 11 }}>{JSON.stringify(value)}</code>
    </div>
  );
}

// Drawer to view/edit an agent's params. GET /v1/agents/{id}/config →
// form → PATCH (body = the params dict, per the route in config.py).
function AgentConfigDrawer({ agentId, onClose }) {
  const [draft, setDraft] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const load = () => {
    setLoading(true);
    setError(null);
    CT_API.getAgentConfig(agentId)
      .then(c => { setDraft({ ...(c.params || {}) }); setLoading(false); })
      .catch(e => { setError(e); setLoading(false); });
  };
  useEffect(() => { load(); }, [agentId]);

  const setParam = (k, v) => { setDraft(d => ({ ...d, [k]: v })); setSaved(false); };
  const save = () => {
    setSaving(true);
    CT_API.patchAgentConfig(agentId, draft)
      .then(c => { setDraft({ ...(c.params || {}) }); setSaving(false); setSaved(true); })
      .catch(e => { setError(e); setSaving(false); });
  };

  const keys = draft ? Object.keys(draft) : [];
  return (
    <>
      <div className="drawer-scrim" onClick={onClose} />
      <div className="drawer">
        <div className="card-head" style={{ flexShrink: 0 }}>
          <span className="card-title"><Icon name="settings" />Configurar · {agentId}</span>
          <Btn variant="ghost" size="sm" onClick={onClose}><Icon name="x" size={14} /></Btn>
        </div>
        <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
          {loading ? <LoadingState label="Carregando configuração…" />
            : error ? <ErrorState message="Erro ao carregar configuração" onRetry={load} />
            : keys.length === 0 ? <EmptyState label="Sem parâmetros configuráveis" sub="Este agente não expõe parâmetros." />
            : (
              <fieldset disabled={!CT_AUTH.can('edit_settings')}
                data-tip={CT_AUTH.can('edit_settings') ? undefined
                  : (CT_AUTH.kind() === 'demo'
                    ? 'Somente leitura no ambiente de demonstração — no produto real, este painel edita o agente'
                    : 'Seu perfil não permite editar agentes')}
                style={{ border: 'none', padding: 0, margin: 0,
                  opacity: CT_AUTH.can('edit_settings') ? 1 : .6 }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                {keys.map(k => <AgentParamField key={k} name={k} value={draft[k]} onChange={setParam} />)}
              </div>
              </fieldset>
            )}
        </div>
        {!loading && !error && keys.length > 0 && (
          <div style={{ flexShrink: 0, padding: 16, borderTop: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 10 }}>
            <Btn variant="primary" onClick={save} disabled={saving}>{saving ? 'Salvando…' : 'Salvar'}</Btn>
            {saved && <span style={{ fontSize: 12, color: 'var(--up)' }}>✓ Salvo</span>}
          </div>
        )}
      </div>
    </>
  );
}

function AgentCard({ agent, onConfigure }) {
  const statusVariant = AGENT_STATUS_VARIANT[agent.status] ?? 'neutral';
  const domainVariant = DOMAIN_VARIANT[agent.domain] ?? 'neutral';
  const lastRun = agent.last_run ?? agent.last ?? null;

  return (
    <div className="card" style={{ opacity: agent.implemented ? 1 : 0.7 }}>
      <div className="card-head">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
          <span className="card-title" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {agent.name ?? agent.id}
          </span>
          <Badge variant={domainVariant} dot={false}>{agent.domain}</Badge>
        </div>
        <Badge variant={statusVariant}>{AGENT_STATUS_LABEL[agent.status] ?? agent.status}</Badge>
      </div>
      <div className="card-pad">
        <p style={{ fontSize: 12.5, color: 'var(--ink-2)', marginBottom: 14, lineHeight: 1.55 }}>
          {agent.description}
        </p>
        <div style={{ display: 'flex', gap: 20 }}>
          <div>
            <div style={{ fontSize: 10.5, color: 'var(--ink-4)', marginBottom: 3 }}>Ciclos</div>
            <div style={{ fontFamily: 'var(--mono)', fontWeight: 500 }}>{agent.cycles ?? 0}</div>
          </div>
          {lastRun && (
            <div>
              <div style={{ fontSize: 10.5, color: 'var(--ink-4)', marginBottom: 3 }}>Último ciclo</div>
              <div style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>
                {String(lastRun).substring(0, 8)}
              </div>
            </div>
          )}
          {!agent.implemented && (
            <div style={{ marginLeft: 'auto', alignSelf: 'flex-end' }}>
              <Badge variant="neutral" dot={false}>Não implementado</Badge>
            </div>
          )}
        </div>
        <div style={{ marginTop: 14 }}>
          <Btn variant="ghost" size="sm" onClick={() => onConfigure(agent.id)}>
            <Icon name="settings" size={12} /> Configurar
          </Btn>
        </div>
      </div>
    </div>
  );
}

function ScreenAgents() {
  const [agents,  setAgents]  = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);
  const [configAgent, setConfigAgent] = useState(null);

  useEffect(() => {
    setLoading(true);
    CT_API.getAgents()
      .then(d => { setAgents(Array.isArray(d) ? d : []); setLoading(false); })
      .catch(e => { setError(e); setLoading(false); });
  }, []);

  if (loading) return <LoadingState label="Carregando agentes…" />;
  if (error)   return <ErrorState message="Erro ao carregar agentes" onRetry={() => { setError(null); setLoading(true); }} />;
  if (!agents) return <EmptyState />;

  const active      = agents.filter(a => a.status === 'active').length;
  const implemented = agents.filter(a => a.implemented).length;

  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="page-title">Agentes</h1>
          <div className="page-sub">{active} ativos · {implemented} implementados de {agents.length}</div>
        </div>
      </div>

      <div className="grid kpi-row" style={{ marginBottom: 20 }}>
        <div className="card"><KPI label="Ativos" value={active} format="int" icon="activity" /></div>
        <div className="card"><KPI label="Implementados" value={implemented} format="int" icon="check" /></div>
        <div className="card"><KPI label="Total" value={agents.length} format="int" icon="user" /></div>
      </div>

      <div className="grid kpi-row" style={{ marginBottom: 20 }}>
        {agents.map(agent => (
          <AgentCard key={agent.id} agent={agent} onConfigure={setConfigAgent} />
        ))}
      </div>

      {configAgent && (
        <AgentConfigDrawer agentId={configAgent} onClose={() => setConfigAgent(null)} />
      )}
    </div>
  );
}
window.ScreenAgents = ScreenAgents;
