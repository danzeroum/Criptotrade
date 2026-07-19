/* ============================================================
   Criptotrade — Screen: Settings
   ============================================================ */
const { useState, useEffect } = React;

function SectionHead({ title, icon }) {
  return (
    <div className="card-head" style={{ marginBottom: 0 }}>
      <span className="card-title"><Icon name={icon} />{title}</span>
    </div>
  );
}

// 11c — Watchlists/grupos: organização da visão (localStorage, NÃO afeta o loop).
// Um grupo por par operado; grupos vazios persistem; excluir um grupo devolve seus
// pares a "sem grupo" (nunca exclui pares). Fonte da verdade dos membros = os pares
// operados atuais (órfãos do localStorage são ignorados na leitura, GC na escrita).
function PairGroupsManager({ operated, canEdit, addToast }) {
  const [groups, setGroups] = useState(CT_GROUPS.names());
  const [, bump] = useState(0);  // re-render on membership changes
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState('');
  const [editing, setEditing] = useState(null);
  const [editVal, setEditVal] = useState('');

  useEffect(() => CT_GROUPS.subscribe(() => { setGroups(CT_GROUPS.names()); bump(n => n + 1); }), []);
  useEffect(() => { CT_GROUPS.gc(operated); }, [operated.join(',')]);

  const create = () => {
    const n = newName.trim();
    if (!n) return;
    if (!CT_GROUPS.create(n)) { addToast?.('Grupo já existe.', 'alert'); return; }
    setNewName(''); setCreating(false);
  };
  const commitRename = () => {
    if (editing && editVal.trim() && editVal.trim() !== editing && !CT_GROUPS.rename(editing, editVal.trim())) {
      addToast?.('Nome de grupo inválido ou já existe.', 'alert');
    }
    setEditing(null); setEditVal('');
  };

  return (
    <div className="pg" style={{ marginBottom: 14 }}>
      <div className="stat-k" style={{ marginBottom: 6 }}>
        Grupos <span className="desk-muted" style={{ fontWeight: 400 }}>— organização da visão (não afeta o loop)</span>
      </div>
      <div className="desk-group-filter" style={{ marginBottom: 10 }}>
        {groups.map(g => (
          editing === g
            ? <input key={g} className="input pg-rename" autoFocus value={editVal}
                aria-label={`Renomear ${g}`}
                onChange={e => setEditVal(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') commitRename(); if (e.key === 'Escape') { setEditing(null); setEditVal(''); } }}
                onBlur={commitRename} />
            : <span key={g} className="group-chip">
                {g}
                {canEdit && (
                  <button className="pg-chip-btn" aria-label={`Renomear ${g}`}
                    onClick={() => { setEditing(g); setEditVal(g); }}>✎</button>
                )}
                {canEdit && (
                  <button className="pg-chip-btn" aria-label={`Excluir grupo ${g}`}
                    onClick={() => CT_GROUPS.remove(g)}>×</button>
                )}
              </span>
        ))}
        {canEdit && (creating
          ? <input className="input pg-rename" autoFocus placeholder="Nome do grupo" value={newName}
              aria-label="Nome do novo grupo"
              onChange={e => setNewName(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') create(); if (e.key === 'Escape') { setCreating(false); setNewName(''); } }}
              onBlur={create} />
          : <button className="group-chip pg-add" onClick={() => setCreating(true)}>+ Novo grupo</button>)}
      </div>
      {groups.length > 0 && (
        <div className="pg-assign">
          {operated.map(sym => (
            <div key={sym} className="pg-assign-row">
              <span className="pg-assign-sym">{sym}</span>
              <select className="input pg-select" value={CT_GROUPS.groupOf(sym) || ''}
                disabled={!canEdit} aria-label={`Grupo de ${sym}`}
                onChange={e => CT_GROUPS.assign(sym, e.target.value || null)}>
                <option value="">sem grupo</option>
                {groups.map(g => <option key={g} value={g}>{g}</option>)}
              </select>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ScreenSettings({ addToast }) {
  const mock = !!window.USE_MOCK_DATA;

  const mockConfig = {
    exchange: 'binance',
    dry_run: true,
    initial_capital: 10000,
    orchestrator_interval_seconds: 60,
    autonomy_level: CT.hitl.level,
    app_env: 'development',
  };
  const mockRiskConfig = {
    max_position_size_pct: CT.riskConfig.maxPositionPct,
    stop_loss_default_pct: 3,
    take_profit_default_pct: 6,
    max_daily_loss_pct: CT.riskConfig.ddDaily,
    max_weekly_loss_pct: CT.riskConfig.ddWeekly,
    max_monthly_loss_pct: CT.riskConfig.ddMonthly,
    kelly_fraction: CT.riskConfig.kellyFraction,
    circuit_breaker_enabled: true,
  };
  const mockAlerts = {
    revenge_size_multiplier: CT.alertThresholds.revengeSize / 100 + 1,
    euphoria_size_multiplier: CT.alertThresholds.euphoriaSize / 100 + 1,
    overconfidence_margin: CT.alertThresholds.overconfidenceGap / 100,
    risk_of_ruin_alert_pct: CT.alertThresholds.riskOfRuin,
  };

  const [sysConfig,    setSysConfig]    = useState(mock ? mockConfig : null);
  const [riskConfig,   setRiskConfig]   = useState(mock ? mockRiskConfig : null);
  const [alertConfig,  setAlertConfig]  = useState(mock ? mockAlerts : null);
  const [agents,       setAgents]       = useState(null);
  const [pairsRich,    setPairsRich]    = useState(null);  // N8¹/N8²: operated/observable
  const [pairsDirty,   setPairsDirty]   = useState(false); // N8²: pending-restart flag
  const [addPairSel,   setAddPairSel]   = useState('');
  const [loading,      setLoading]      = useState(!mock);
  const [error,        setError]        = useState(null);
  const [saved,        setSaved]        = useState(null);

  // N8¹: pares operados, da fonte dinâmica /v1/pairs (N1). N8²: editável abaixo.
  const reloadPairs = () => loadPairsRich(true).then(setPairsRich).catch(() => {});
  useEffect(() => { loadPairsRich().then(setPairsRich).catch(() => {}); }, []);

  // N8²: add/remove operated pair — aplica no PRÓXIMO restart do orchestrator.
  const addPair = async (symbol) => {
    if (!symbol) return;
    if (mock) {
      setPairsRich(p => ({ ...p, operados: [...(p.operados || []), { symbol, status: 'aguardando' }] }));
      setPairsDirty(true); setAddPairSel(''); addToast?.('Par adicionado (pendente de restart).', 'check'); return;
    }
    try { await CT_API.addOperatedPair(symbol); setPairsDirty(true); setAddPairSel(''); await reloadPairs(); addToast?.('Par adicionado — reinicie o orchestrator para aplicar.', 'check'); }
    catch (e) { addToast?.(e?.message ?? 'Falha ao adicionar par.', 'alert'); }
  };
  const removePair = async (symbol) => {
    if (mock) {
      setPairsRich(p => ({ ...p, operados: (p.operados || []).filter(o => o.symbol !== symbol) }));
      setPairsDirty(true); addToast?.('Par removido (pendente de restart).', 'check'); return;
    }
    try { await CT_API.removeOperatedPair(symbol); setPairsDirty(true); await reloadPairs(); addToast?.('Par removido — reinicie o orchestrator para aplicar.', 'check'); }
    catch (e) { addToast?.(e?.message ?? 'Falha ao remover par.', 'alert'); }
  };
  // N9: pausar/retomar — aplica SEM restart (lido por ciclo). NÃO seta pairsDirty.
  const pausePair = async (symbol, paused) => {
    if (mock) {
      setPairsRich(p => ({ ...p, operados: (p.operados || []).map(o => o.symbol === symbol ? { ...o, paused } : o) }));
      addToast?.(paused ? 'Par pausado.' : 'Par retomado.', 'check'); return;
    }
    try { await CT_API.setPairPaused(symbol, paused); await reloadPairs();
          addToast?.(paused ? 'Par pausado — sem novas ordens; posições seguem geridas.' : 'Par retomado.', 'check'); }
    catch (e) { addToast?.(e?.message ?? 'Falha ao pausar par.', 'alert'); }
  };

  useEffect(() => {
    if (mock) {
      CT_API.getAgents().then(setAgents).catch(() => setAgents(CT.agents));
      return;
    }
    setLoading(true);
    Promise.all([
      CT_API.getConfig(),
      CT_API.getRiskConfig(),
      CT_API.getAgents(),
    ])
      .then(([cfg, rc, ag]) => {
        setSysConfig(cfg);
        setRiskConfig(rc);
        setAgents(Array.isArray(ag) ? ag : []);
        setLoading(false);
      })
      .catch(e => { setError(e); setLoading(false); });
  }, [mock]);

  const flash = (msg) => {
    setSaved(msg);
    setTimeout(() => setSaved(null), 2500);
  };

  const saveSysConfig = async (patch) => {
    if (mock) { setSysConfig(prev => ({ ...prev, ...patch })); flash('Config salva'); return; }
    try {
      const updated = await CT_API.patchConfig(patch);
      setSysConfig(updated);
      flash('Config salva');
    } catch (e) { console.error(e); addToast?.('Erro ao salvar configuração', 'alert'); }
  };

  const saveRiskConfig = async (patch) => {
    if (mock) { setRiskConfig(prev => ({ ...prev, ...patch })); flash('Risco salvo'); return; }
    try {
      const updated = await CT_API.patchRiskConfig(patch);
      setRiskConfig(updated);
      flash('Risco salvo');
    } catch (e) { console.error(e); addToast?.('Erro ao salvar parâmetros de risco', 'alert'); }
  };

  const saveAlertConfig = async (patch) => {
    if (mock) { setAlertConfig(prev => ({ ...prev, ...patch })); flash('Alertas salvos'); return; }
    try {
      const updated = await CT_API.patchAlertsConfig(patch);
      setAlertConfig(updated);
      flash('Alertas salvos');
    } catch (e) { console.error(e); addToast?.('Erro ao salvar alertas', 'alert'); }
  };

  if (loading) return <LoadingState label="Carregando configurações…" />;
  if (error)   return <ErrorState message="Erro ao carregar configurações" onRetry={() => { setError(null); setLoading(true); }} />;

  // A3 gating: fieldset[disabled] turns each edit card read-only. Demo shows
  // the discovery tooltip (approved correction); a Visualizador gets the lock hint.
  const canEdit = CT_AUTH.can('edit_settings');
  const canRisk = CT_AUTH.can('change_risk');
  const demoView = CT_AUTH.kind() === 'demo';
  const gateTip = (allowed) => allowed ? undefined : (demoView
    ? 'Somente leitura no ambiente de demonstração — no produto real, este painel edita a configuração'
    : 'Seu perfil não permite editar esta configuração');

  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="page-title">Configurações</h1>
          <div className="page-sub">Sistema, risco, alertas e parâmetros dos agentes</div>
        </div>
        {saved && (
          <Badge variant="ok"><Icon name="check" size={11} /> {saved}</Badge>
        )}
      </div>

      <div className="grid" style={{ gridTemplateColumns: '1fr 1fr', gap: 20, alignItems: 'start' }}>
        {/* System config */}
        {sysConfig && (
          <div className="card">
            <SectionHead title="Sistema" icon="settings" />
            <fieldset disabled={!canEdit} data-tip={gateTip(canEdit)} style={{ border: "none", padding: 0, margin: 0, opacity: canEdit ? 1 : .6 }}>
            <div className="card-pad">
              <div style={{ marginBottom: 16 }}>
                <div className="stat-row">
                  <span className="stat-k">Exchange</span>
                  <span className="stat-v">{sysConfig.exchange}</span>
                </div>
                <div className="stat-row">
                  <span className="stat-k">Ambiente</span>
                  <span className="stat-v">{sysConfig.app_env}</span>
                </div>
                <div className="stat-row">
                  <span className="stat-k">Modo paper</span>
                  <span className="stat-v">
                    <Badge variant={sysConfig.dry_run ? 'warn' : 'ok'}>
                      {sysConfig.dry_run ? 'Paper trading' : 'Live trading'}
                    </Badge>
                  </span>
                </div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                <NumField
                  label="Capital inicial ($)"
                  value={sysConfig.initial_capital}
                  onChange={v => saveSysConfig({ initial_capital: v })}
                  min={100}
                  step={100}
                  unit="$"
                />
                <NumField
                  label="Intervalo do orquestrador (s)"
                  value={sysConfig.orchestrator_interval_seconds}
                  onChange={v => saveSysConfig({ orchestrator_interval_seconds: v })}
                  min={10}
                  max={300}
                  step={10}
                  unit="s"
                />
              </div>
            </div>
            </fieldset>
          </div>
        )}

        {/* Risk config */}
        {riskConfig && (
          <div className="card">
            <SectionHead title="Gestão de Risco" icon="shield" />
            <fieldset disabled={!canRisk} data-tip={gateTip(canRisk)} style={{ border: "none", padding: 0, margin: 0, opacity: canRisk ? 1 : .6 }}>
            <div className="card-pad">
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                <SliderField
                  label="Tamanho máximo de posição"
                  value={riskConfig.max_position_size_pct}
                  onChange={v => saveRiskConfig({ max_position_size_pct: v })}
                  min={0.5} max={10} step={0.5}
                  unit="%"
                />
                <SliderField
                  label="Stop loss padrão"
                  value={riskConfig.stop_loss_default_pct}
                  onChange={v => saveRiskConfig({ stop_loss_default_pct: v })}
                  min={0.5} max={10} step={0.5}
                  unit="%"
                />
                <SliderField
                  label="Drawdown máximo diário"
                  value={riskConfig.max_daily_loss_pct}
                  onChange={v => saveRiskConfig({ max_daily_loss_pct: v })}
                  min={1} max={10} step={0.5}
                  unit="%"
                />
                <SliderField
                  label="Drawdown máximo semanal"
                  value={riskConfig.max_weekly_loss_pct}
                  onChange={v => saveRiskConfig({ max_weekly_loss_pct: v })}
                  min={2} max={20} step={1}
                  unit="%"
                />
                <SliderField
                  label="Drawdown máximo mensal"
                  value={riskConfig.max_monthly_loss_pct}
                  onChange={v => saveRiskConfig({ max_monthly_loss_pct: v })}
                  min={5} max={30} step={1}
                  unit="%"
                />
                <SliderField
                  label="Fração Kelly"
                  value={riskConfig.kelly_fraction}
                  onChange={v => saveRiskConfig({ kelly_fraction: v })}
                  min={0.1} max={1} step={0.05}
                />
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: 13 }}>Circuit breaker</span>
                  <button
                    className={`toggle${riskConfig.circuit_breaker_enabled ? ' on' : ''}`}
                    onClick={() => saveRiskConfig({ circuit_breaker_enabled: !riskConfig.circuit_breaker_enabled })}
                    type="button"
                  />
                </div>
              </div>
            </div>
            </fieldset>
          </div>
        )}

        {/* Behavioral alert thresholds */}
        {alertConfig && (
          <div className="card">
            <SectionHead title="Guardrails Comportamentais" icon="alert" />
            <fieldset disabled={!canEdit} data-tip={gateTip(canEdit)} style={{ border: "none", padding: 0, margin: 0, opacity: canEdit ? 1 : .6 }}>
            <div className="card-pad">
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                <SliderField
                  label="Multiplicador revenge trading"
                  value={parseFloat(((alertConfig.revenge_size_multiplier - 1) * 100).toFixed(0))}
                  onChange={v => saveAlertConfig({ revenge_size_multiplier: 1 + v / 100 })}
                  min={10} max={100} step={5}
                  unit="%"
                />
                <SliderField
                  label="Multiplicador euforia"
                  value={parseFloat(((alertConfig.euphoria_size_multiplier - 1) * 100).toFixed(0))}
                  onChange={v => saveAlertConfig({ euphoria_size_multiplier: 1 + v / 100 })}
                  min={5} max={80} step={5}
                  unit="%"
                />
                <SliderField
                  label="Gap overconfidence"
                  value={parseFloat((alertConfig.overconfidence_margin * 100).toFixed(0))}
                  onChange={v => saveAlertConfig({ overconfidence_margin: v / 100 })}
                  min={5} max={40} step={5}
                  unit="%"
                />
                <SliderField
                  label="Alerta risco de ruína"
                  value={alertConfig.risk_of_ruin_alert_pct}
                  onChange={v => saveAlertConfig({ risk_of_ruin_alert_pct: v })}
                  min={1} max={15} step={0.5}
                  unit="%"
                />
              </div>
              {/* A6: entrega externa (e-mail/Telegram/Slack/webhook) mora em
                  Notificações & Canais — link da seção, conforme o card. */}
              {CT_AUTH.can('edit_settings') && (
                <div style={{ marginTop: 12, fontSize: 12.5, display: 'flex',
                              gap: 16, flexWrap: 'wrap' }}>
                  <a href="#notifications" style={{ color: 'var(--info)' }}>
                    Canais de entrega (e-mail, Telegram, Slack, webhook) →
                  </a>
                  {/* A10: reacesso ao guia (só admin autenticado). */}
                  {CT_AUTH.state()?.user?.role === 'admin' && (
                    <a href="#onboarding" style={{ color: 'var(--info)' }}>
                      Guia de configuração →
                    </a>
                  )}
                </div>
              )}
            </div>
            </fieldset>
          </div>
        )}

        {/* Agents */}
        {agents && agents.filter(a => a.implemented).length > 0 && (
          <div className="card">
            <SectionHead title="Parâmetros dos Agentes" icon="user" />
            <div className="card-pad">
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {agents.filter(a => a.implemented).map(agent => (
                  <div
                    key={agent.id}
                    style={{
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      padding: '10px 12px', background: 'var(--surface-3)', borderRadius: 'var(--r-sm)',
                    }}
                  >
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 500 }}>{agent.name ?? agent.id}</div>
                      <div style={{ fontSize: 11.5, color: 'var(--ink-3)', marginTop: 2 }}>{agent.domain}</div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <Badge variant="ok" dot={false}>Ativo</Badge>
                      <span style={{ fontSize: 11.5, fontFamily: 'var(--mono)', color: 'var(--ink-3)' }}>
                        {agent.cycles ?? 0} ciclos
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* N8²: gestão de pares operados (DB > env). add/remove aplicam no
            PRÓXIMO restart do orchestrator (banner honesto); pausar (N9) é
            por-ciclo. Fonte: /v1/pairs (nunca hardcoded). */}
        {pairsRich && (() => {
          const operatedSet = new Set((pairsRich.operados || []).map(o => o.symbol));
          const addable = (pairsRich.observaveis || []).filter(s => !operatedSet.has(s));
          return (
          <div className="card">
            <SectionHead title="Pares operados" icon="grid" />
            <div className="card-pad">
              {pairsDirty && (
                <div className="pending-restart">
                  <Icon name="clock" size={13} />
                  Alterações pendentes — reinicie o orchestrator para aplicá-las.
                </div>
              )}
              <div style={{ marginBottom: 14 }}>
                <div className="stat-k" style={{ marginBottom: 6 }}>Operados pelo loop</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {(pairsRich.operados || []).map(o => (
                    <span key={o.symbol} className={'pair-tag' + (o.status === 'operando' && !o.paused ? ' on' : '') + (o.paused ? ' paused' : '')}>
                      {o.symbol}
                      {o.paused && (
                        <span className="pair-paused-badge"
                          title="Pausado — sem novas ordens; posições abertas seguem geridas (stop/TP ativos)">PAUSADO</span>
                      )}
                      {canEdit && (
                        <button className="pair-tag-btn"
                          title={o.paused ? 'Retomar par (aplica no próximo ciclo)' : 'Pausar par — sem novas ordens, sem restart'}
                          aria-label={`${o.paused ? 'Retomar' : 'Pausar'} ${o.symbol}`}
                          onClick={() => pausePair(o.symbol, !o.paused)}>{o.paused ? '▶' : '❙❙'}</button>
                      )}
                      {canEdit && (
                        <button className="pair-tag-x" aria-label={`Remover ${o.symbol}`}
                          onClick={() => removePair(o.symbol)}>×</button>
                      )}
                    </span>
                  ))}
                  {(pairsRich.operados || []).length === 0 && <span className="desk-muted">Nenhum</span>}
                </div>
              </div>
              {canEdit && addable.length > 0 && (
                <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 14 }}>
                  <select className="input" value={addPairSel} onChange={e => setAddPairSel(e.target.value)}
                    aria-label="Adicionar par" style={{ width: 'auto', minWidth: 150 }}>
                    <option value="">Adicionar par…</option>
                    {addable.map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                  <Btn variant="primary" size="sm" onClick={() => addPair(addPairSel)}>Adicionar</Btn>
                </div>
              )}
              <div style={{ marginBottom: 14 }}>
                <div className="stat-k" style={{ marginBottom: 6 }}>Observáveis (allowlist <code>MARKET_PAIRS</code>)</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {(pairsRich.observaveis || []).map(s => <span key={s} className="chip">{s}</span>)}
                </div>
              </div>
              <PairGroupsManager
                operated={(pairsRich.operados || []).map(o => o.symbol)}
                canEdit={canEdit} addToast={addToast} />
              <div style={{ fontSize: 12.5, color: 'var(--ink-2)', lineHeight: 1.6,
                            background: 'var(--surface-3)', borderRadius: 'var(--r-sm)', padding: '10px 12px' }}>
                Só pares da allowlist (<code>MARKET_PAIRS</code>) podem ser operados.
                Adicionar/remover aplica no <b>próximo restart</b> do orchestrator.
                Pausar um par aplica <b>sem restart</b> (lido por ciclo): interrompe novas
                ordens; posições abertas seguem geridas (stop/TP ativos).
              </div>
            </div>
          </div>
          );
        })()}
      </div>
    </div>
  );
}
window.ScreenSettings = ScreenSettings;
