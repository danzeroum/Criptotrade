/* ============================================================
   A10 — Guia de primeira configuração (checklist, não wizard de
   formulários): cada passo é AUTO-DETECTADO do estado real do
   sistema, explica o porquê e deep-linka para a tela que já
   existe. Só admin autenticado; nunca no demo; "pular por agora"
   sempre disponível; reacessível pelo menu do avatar.
   ============================================================ */
const { useState: useObState, useEffect: useObEffect, useCallback: useObCallback } = React;

const OB_STEPS = [
  {
    id: 'connect_exchange',
    title: '1 · Conectar exchange',
    icon: 'zap',
    // Nota 3 da revisão: a recomendação de testnet mora AQUI, antes do clique.
    why: 'Credenciais geridas, cifradas e testadas destravam dados reais e, mais tarde, o modo live. Comece em TESTNET — valide o fluxo completo antes de apontar para a conta real.',
    cta: 'Abrir Conexões', target: 'connections',
  },
  {
    id: 'risk_capital',
    title: '2 · Definir risco & capital',
    icon: 'shield',
    why: 'Guardrails (tamanho máximo de posição, perda diária) e capital inicial são o freio do sistema — defina-os antes do primeiro ciclo.',
    cta: 'Abrir Config', target: 'settings',
  },
  {
    id: 'strategy_agents',
    title: '3 · Escolher estratégia & agentes',
    icon: 'user',
    why: 'A estratégia segue o regime de mercado; o que você configura são os parâmetros dos agentes e o nível de autonomia (HITL).',
    cta: 'Abrir Agentes', target: 'agents',
  },
  {
    id: 'review',
    title: '4 · Revisar',
    icon: 'eye',
    why: 'Confira o resumo real do sistema — conexão, roteamento, autonomia, risco e pares — antes de rodar.',
    cta: null, target: null,
  },
  {
    id: 'start_dryrun',
    title: '5 · Iniciar em dry-run',
    icon: 'play',
    why: 'O primeiro ciclo roda com dados sintéticos e ordens simuladas — zero risco. Acompanhe na Visão Geral pelo selo de frescor.',
    cta: 'Abrir Visão Geral', target: 'overview',
  },
];

const OB_STATUS_BADGE = {
  done_auto:   { variant: 'ok', label: 'Detectado automaticamente' },
  done_manual: { variant: 'ok', label: 'Marcado por você' },
  skipped:     { variant: 'neutral', label: 'Pulado' },
  pending:     { variant: 'warn', label: 'Pendente' },
};

function ObSummary({ summary }) {
  if (!summary) return null;
  const conn = summary.connection;
  const rows = [
    ['Conexão', conn
      ? `${conn.label} · ${conn.exchange} · ${conn.scope} · ${conn.testnet ? 'testnet' : 'real'}${conn.tested_ok ? ' · teste ok' : ''}`
      : 'nenhuma (fallback por env — somente paper)'],
    ['Roteamento', `${summary.routing}${summary.dry_run == null ? '' : summary.dry_run ? ' · dry-run (sintético)' : ' · dados reais'}`],
    ['Autonomia (HITL)', `nível ${summary.autonomy_level}`],
    ['Risco', summary.risk?.max_position_size_pct != null
      ? `posição máx ${fmtNum(summary.risk.max_position_size_pct, 1)}% · perda diária máx ${fmtNum(summary.risk.max_daily_loss_pct, 1)}%`
      : '—'],
    ['Pares', summary.pairs],
    ['Capital inicial', fmtUsd(summary.initial_capital, 0)],
  ];
  return (
    <div style={{ marginTop: 8 }} data-testid="onboarding-summary">
      {rows.map(([k, v]) => (
        <div key={k} className="stat-row" style={{ padding: '6px 0' }}>
          <span className="stat-k">{k}</span>
          <span className="stat-v" style={{ fontSize: 12.5, textAlign: 'right' }}>{v}</span>
        </div>
      ))}
    </div>
  );
}

function ScreenOnboarding({ navigate, addToast }) {
  const [status, setStatus] = useObState(null);
  const [loading, setLoading] = useObState(true);
  const [error, setError] = useObState(null);

  const load = useObCallback(() => {
    setLoading(true);
    CT_API.getOnboarding()
      .then(s => { setStatus(s); setLoading(false); setError(null); })
      .catch(e => { setError(e); setLoading(false); });
  }, []);

  useObEffect(() => { load(); }, [load]);

  const patch = async (body, okMsg) => {
    try {
      const out = await CT_API.patchOnboarding(body);
      setStatus(out);
      if (okMsg) addToast?.(okMsg, 'check');
    } catch (e) { addToast?.(e?.message ?? 'Falha na ação.', 'alert'); }
  };

  if (loading) return <LoadingState label="Carregando guia…" />;
  if (error) return <ErrorState message="Erro ao carregar o guia" onRetry={load} />;
  if (!status) return <EmptyState label="Guia indisponível" />;

  const doneCount = status.steps.filter(s => s.status !== 'pending').length;
  const pct = Math.round((doneCount / status.steps.length) * 100);

  return (
    <div style={{ maxWidth: 780, margin: '0 auto' }}>
      <div className="page-head">
        <div>
          <h1 className="page-title">Guia de configuração</h1>
          <div className="page-sub">
            Do zero ao primeiro ciclo em dry-run — cada passo usa uma tela real do console
          </div>
        </div>
        {!status.completed && (
          <Btn variant="ghost" size="sm"
            onClick={() => patch({ dismiss: true }).then(() => navigate?.('overview'))}>
            Pular por agora
          </Btn>
        )}
      </div>

      {/* progress */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-pad" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ flex: 1, height: 8, background: 'var(--surface-3)',
                        borderRadius: 'var(--r-pill)', overflow: 'hidden' }}>
            <div style={{ width: `${pct}%`, height: '100%', background: 'var(--up)',
                          transition: 'width .3s' }} />
          </div>
          <span style={{ fontSize: 12.5, fontFamily: 'var(--mono)', color: 'var(--ink-2)' }}>
            {doneCount}/{status.steps.length}
          </span>
        </div>
      </div>

      {status.completed && (
        <div className="card" style={{ marginBottom: 16, border: '1px solid var(--up-line)',
                                       background: 'var(--up-bg)' }}>
          <div className="card-pad" style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <Icon name="check" size={18} style={{ color: 'var(--up)' }} />
            <p style={{ fontSize: 13, margin: 0, flex: 1 }}>
              <b>Configuração concluída.</b> O sistema está pronto — acompanhe os
              ciclos na Visão Geral.
            </p>
            <Btn variant="primary" size="sm" onClick={() => navigate?.('overview')}>
              Ir ao dashboard
            </Btn>
          </div>
        </div>
      )}

      {status.steps.map(step => {
        const meta = OB_STEPS.find(m => m.id === step.id) ?? { title: step.id };
        const badge = OB_STATUS_BADGE[step.status] ?? OB_STATUS_BADGE.pending;
        const done = step.status !== 'pending';
        return (
          <div key={step.id} className="card" style={{ marginBottom: 12,
                opacity: step.status === 'skipped' ? 0.75 : 1 }}>
            <div className="card-pad">
              <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                <Icon name={meta.icon ?? 'info'} size={16}
                  style={{ color: done ? 'var(--up)' : 'var(--ink-3)' }} />
                <span style={{ fontWeight: 600, fontSize: 14, flex: 1 }}>{meta.title}</span>
                <Badge variant={badge.variant} dot={false}>{badge.label}</Badge>
              </div>
              <p style={{ fontSize: 12.5, color: 'var(--ink-2)', lineHeight: 1.6,
                          margin: '8px 0 0 26px' }}>
                {meta.why}
                {step.detail && (
                  <span style={{ display: 'block', marginTop: 4, fontFamily: 'var(--mono)',
                                 fontSize: 11.5, color: 'var(--ink-3)' }}>
                    {step.detail}
                  </span>
                )}
              </p>
              {step.id === 'review' && <div style={{ margin: '0 0 0 26px' }}>
                <ObSummary summary={status.summary} /></div>}
              <div style={{ display: 'flex', gap: 8, margin: '10px 0 0 26px', flexWrap: 'wrap' }}>
                {meta.target && (
                  <Btn variant={done ? 'ghost' : 'primary'} size="sm"
                    onClick={() => navigate?.(meta.target)}>
                    {meta.cta} →
                  </Btn>
                )}
                {step.id === 'review' && step.status === 'pending' && (
                  <Btn variant="primary" size="sm"
                    onClick={() => patch({ step: 'review', action: 'complete' },
                      'Revisão concluída.')}>
                    Revisei — está tudo certo
                  </Btn>
                )}
                {!done && step.id !== 'review' && (
                  <Btn variant="ghost" size="sm"
                    onClick={() => patch({ step: step.id, action: 'skip' }, 'Passo pulado.')}>
                    Pular
                  </Btn>
                )}
              </div>
            </div>
          </div>
        );
      })}

      <div style={{ textAlign: 'center', margin: '16px 0' }}>
        <Btn variant="ghost" size="sm" onClick={load}>
          <Icon name="refresh" size={13} /> Re-detectar estado
        </Btn>
      </div>
    </div>
  );
}
window.ScreenOnboarding = ScreenOnboarding;
