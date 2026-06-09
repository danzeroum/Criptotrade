/* ============================================================
   Criptotrade — Screen: Agents
   ============================================================ */
const { useState, useEffect } = React;

const DOMAIN_VARIANT = {
  trading:       'info',
  security:      'warn',
  orchestration: 'violet',
};

const STATUS_VARIANT = {
  active:          'ok',
  idle:            'neutral',
  not_implemented: 'neutral',
  error:           'down',
};

const STATUS_LABEL = {
  active:          'Ativo',
  idle:            'Ocioso',
  not_implemented: 'Stub',
  error:           'Erro',
};

function AgentCard({ agent }) {
  const statusVariant = STATUS_VARIANT[agent.status] ?? 'neutral';
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
        <Badge variant={statusVariant}>{STATUS_LABEL[agent.status] ?? agent.status}</Badge>
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
      </div>
    </div>
  );
}

function ScreenAgents() {
  const mock = !!window.USE_MOCK_DATA;
  const [agents,  setAgents]  = useState(mock ? CT.agents : null);
  const [loading, setLoading] = useState(!mock);
  const [error,   setError]   = useState(null);

  useEffect(() => {
    if (mock) return;
    setLoading(true);
    CT_API.getAgents()
      .then(d => { setAgents(Array.isArray(d) ? d : []); setLoading(false); })
      .catch(e => { setError(e); setLoading(false); });
  }, [mock]);

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

      <div className="grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)', marginBottom: 20 }}>
        <div className="card"><KPI label="Ativos" value={active} format="int" icon="activity" /></div>
        <div className="card"><KPI label="Implementados" value={implemented} format="int" icon="check" /></div>
        <div className="card"><KPI label="Total" value={agents.length} format="int" icon="user" /></div>
      </div>

      <div className="grid" style={{ gridTemplateColumns: 'repeat(2, 1fr)', marginBottom: 20 }}>
        {agents.map(agent => (
          <AgentCard key={agent.id} agent={agent} />
        ))}
      </div>

      <div className="card">
        <div className="card-head">
          <span className="card-title"><Icon name="settings" />Parâmetros das Estratégias</span>
        </div>
        <div className="card-pad">
          <div className="grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)', gap: 24 }}>
            {Object.entries(CT.strategies ?? {}).map(([name, params]) => (
              <div key={name}>
                <div className="label-xs" style={{ marginBottom: 10 }}>{name}</div>
                {Object.entries(params).map(([k, v]) => (
                  <div key={k} className="stat-row">
                    <span className="stat-k">{k}</span>
                    <span className="stat-v">{String(v)}</span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
window.ScreenAgents = ScreenAgents;
