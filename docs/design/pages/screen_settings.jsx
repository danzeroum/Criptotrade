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

// M1: rótulos legíveis dos parâmetros para o resumo before→after da confirmação.
const CONFIG_FIELD_LABELS = {
  initial_capital: 'Capital inicial ($)',
  orchestrator_interval_seconds: 'Intervalo do orquestrador (s)',
  max_position_size_pct: 'Tamanho máximo de posição (%)',
  stop_loss_default_pct: 'Stop loss padrão (%)',
  max_daily_loss_pct: 'Drawdown máximo diário (%)',
  max_weekly_loss_pct: 'Drawdown máximo semanal (%)',
  max_monthly_loss_pct: 'Drawdown máximo mensal (%)',
  kelly_fraction: 'Fração Kelly',
  circuit_breaker_enabled: 'Circuit breaker',
  revenge_size_multiplier: 'Multiplicador revenge trading',
  euphoria_size_multiplier: 'Multiplicador euforia',
  overconfidence_margin: 'Gap overconfidence',
  risk_of_ruin_alert_pct: 'Alerta risco de ruína',
};
const fmtCfgVal = (v) => (typeof v === 'boolean' ? (v ? 'ativado' : 'desativado') : String(v));

// M1: confirmação explícita antes de gravar config — resumo before→after (mesmo
// padrão do aviso do A5). Só depois de confirmar é que o PATCH é enviado (risco
// exige confirm=true no backend; sys/alertas não têm o gate mas ganham o mesmo
// fluxo, eliminando o PATCH-a-cada-onChange).
function ConfigConfirmModal({ title, changes, onConfirm, onClose }) {
  return (
    <div className="lock-overlay" role="dialog" aria-label={title} onClick={onClose}>
      <div className="lock-card" onClick={e => e.stopPropagation()} style={{ maxWidth: 480 }}>
        <h3 style={{ marginTop: 0 }}>{title}</h3>
        <p style={{ fontSize: 13, color: 'var(--ink-2)' }}>Confira as alterações antes de aplicar:</p>
        <table className="tbl" data-testid="config-confirm-diff" style={{ marginBottom: 14 }}>
          <thead><tr><th>Parâmetro</th><th>Antes</th><th>Depois</th></tr></thead>
          <tbody>
            {changes.map(c => (
              <tr key={c.key}>
                <td>{c.label}</td>
                <td style={{ color: 'var(--ink-3)' }}>{fmtCfgVal(c.before)}</td>
                <td style={{ fontWeight: 600 }}>{fmtCfgVal(c.after)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <Btn variant="ghost" size="sm" onClick={onClose}>Cancelar</Btn>
          <Btn variant="primary" size="sm" onClick={onConfirm}>Confirmar e salvar</Btn>
        </div>
      </div>
    </div>
  );
}

function ScreenSettings({ addToast }) {
  const [sysConfig,    setSysConfig]    = useState(null);
  const [riskConfig,   setRiskConfig]   = useState(null);
  const [alertConfig,  setAlertConfig]  = useState(null);
  const [agents,       setAgents]       = useState(null);
  const [pairsRich,    setPairsRich]    = useState(null);  // N8¹/N8²: operated/observable
  const [pairsDirty,   setPairsDirty]   = useState(false); // N8²: pending-restart flag
  const [addPairSel,   setAddPairSel]   = useState('');
  const [loading,      setLoading]      = useState(true);
  const [error,        setError]        = useState(null);
  const [saved,        setSaved]        = useState(null);
  // M1: edições acumulam num draft por card; "Salvar" abre a confirmação (before→
  // after) e SÓ ENTÃO dispara o PATCH — nada de PATCH a cada onChange de slider.
  const [sysDraft,     setSysDraft]     = useState(null);
  const [riskDraft,    setRiskDraft]    = useState(null);
  const [alertDraft,   setAlertDraft]   = useState(null);
  const [pendingSave,  setPendingSave]  = useState(null);

  // N8¹: pares operados, da fonte dinâmica /v1/pairs (N1). N8²: editável abaixo.
  const reloadPairs = () => loadPairsRich(true).then(setPairsRich).catch(() => {});
  useEffect(() => { loadPairsRich().then(setPairsRich).catch(() => {}); }, []);

  // N8²: add/remove operated pair — aplica no PRÓXIMO restart do orchestrator.
  const addPair = async (symbol) => {
    if (!symbol) return;
    try { await CT_API.addOperatedPair(symbol); setPairsDirty(true); setAddPairSel(''); await reloadPairs(); addToast?.('Par adicionado — reinicie o orchestrator para aplicar.', 'check'); }
    catch (e) { addToast?.(e?.message ?? 'Falha ao adicionar par.', 'alert'); }
  };
  const removePair = async (symbol) => {
    try { await CT_API.removeOperatedPair(symbol); setPairsDirty(true); await reloadPairs(); addToast?.('Par removido — reinicie o orchestrator para aplicar.', 'check'); }
    catch (e) { addToast?.(e?.message ?? 'Falha ao remover par.', 'alert'); }
  };
  // N9: pausar/retomar — aplica SEM restart (lido por ciclo). NÃO seta pairsDirty.
  const pausePair = async (symbol, paused) => {
    try { await CT_API.setPairPaused(symbol, paused); await reloadPairs();
          addToast?.(paused ? 'Par pausado — sem novas ordens; posições seguem geridas.' : 'Par retomado.', 'check'); }
    catch (e) { addToast?.(e?.message ?? 'Falha ao pausar par.', 'alert'); }
  };

  useEffect(() => {
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
  }, []);

  const flash = (msg) => {
    setSaved(msg);
    setTimeout(() => setSaved(null), 2500);
  };

  // M1: os drafts espelham a config salva (no load e após cada save bem-sucedido).
  useEffect(() => { setSysDraft(sysConfig ? { ...sysConfig } : null); }, [sysConfig]);
  useEffect(() => { setRiskDraft(riskConfig ? { ...riskConfig } : null); }, [riskConfig]);
  useEffect(() => { setAlertDraft(alertConfig ? { ...alertConfig } : null); }, [alertConfig]);

  const changedKeys = (draft, cfg) =>
    (draft && cfg) ? Object.keys(draft).filter(k => draft[k] !== cfg[k]) : [];

  // "Salvar" de cada card abre a confirmação com o resumo before→after; o apply()
  // (que contém o PATCH real) só roda ao confirmar.
  const requestSave = (title, keys, cfg, draft, apply) => {
    if (!keys.length) return;
    const changes = keys.map(k => ({
      key: k, label: CONFIG_FIELD_LABELS[k] ?? k, before: cfg[k], after: draft[k],
    }));
    setPendingSave({ title, changes, apply });
  };
  const confirmSave = async () => {
    const p = pendingSave;
    setPendingSave(null);
    if (!p) return;
    try { await p.apply(); }
    catch (e) { console.error(e); addToast?.(e?.message ?? 'Erro ao salvar configuração', 'alert'); }
  };

  const saveSys = () => {
    const keys = changedKeys(sysDraft, sysConfig);
    requestSave('Salvar configuração do sistema', keys, sysConfig, sysDraft, async () => {
      const patch = Object.fromEntries(keys.map(k => [k, sysDraft[k]]));
      setSysConfig(await CT_API.patchConfig(patch));
      flash('Config salva');
    });
  };
  const saveRisk = () => {
    const keys = changedKeys(riskDraft, riskConfig);
    requestSave('Salvar parâmetros de risco', keys, riskConfig, riskDraft, async () => {
      // A5: o backend exige confirm=true (400 confirmation_required sem ele).
      const patch = { ...Object.fromEntries(keys.map(k => [k, riskDraft[k]])), confirm: true };
      setRiskConfig(await CT_API.patchRiskConfig(patch));
      flash('Risco salvo');
    });
  };
  const saveAlert = () => {
    const keys = changedKeys(alertDraft, alertConfig);
    requestSave('Salvar guardrails comportamentais', keys, alertConfig, alertDraft, async () => {
      const patch = Object.fromEntries(keys.map(k => [k, alertDraft[k]]));
      setAlertConfig(await CT_API.patchAlertsConfig(patch));
      flash('Alertas salvos');
    });
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
                  value={(sysDraft ?? sysConfig).initial_capital}
                  onChange={v => setSysDraft(d => ({ ...(d ?? sysConfig), initial_capital: v }))}
                  min={100}
                  step={100}
                  unit="$"
                />
                <NumField
                  label="Intervalo do orquestrador (s)"
                  value={(sysDraft ?? sysConfig).orchestrator_interval_seconds}
                  onChange={v => setSysDraft(d => ({ ...(d ?? sysConfig), orchestrator_interval_seconds: v }))}
                  min={10}
                  max={300}
                  step={10}
                  unit="s"
                />
              </div>
              <div style={{ marginTop: 14, display: 'flex', justifyContent: 'flex-end' }}>
                <Btn variant="primary" size="sm" disabled={!changedKeys(sysDraft, sysConfig).length}
                  onClick={saveSys}>Salvar</Btn>
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
                  value={(riskDraft ?? riskConfig).max_position_size_pct}
                  onChange={v => setRiskDraft(d => ({ ...(d ?? riskConfig), max_position_size_pct: v }))}
                  min={0.5} max={10} step={0.5}
                  unit="%"
                />
                <SliderField
                  label="Stop loss padrão"
                  value={(riskDraft ?? riskConfig).stop_loss_default_pct}
                  onChange={v => setRiskDraft(d => ({ ...(d ?? riskConfig), stop_loss_default_pct: v }))}
                  min={0.5} max={10} step={0.5}
                  unit="%"
                />
                <SliderField
                  label="Drawdown máximo diário"
                  value={(riskDraft ?? riskConfig).max_daily_loss_pct}
                  onChange={v => setRiskDraft(d => ({ ...(d ?? riskConfig), max_daily_loss_pct: v }))}
                  min={1} max={10} step={0.5}
                  unit="%"
                />
                <SliderField
                  label="Drawdown máximo semanal"
                  value={(riskDraft ?? riskConfig).max_weekly_loss_pct}
                  onChange={v => setRiskDraft(d => ({ ...(d ?? riskConfig), max_weekly_loss_pct: v }))}
                  min={2} max={20} step={1}
                  unit="%"
                />
                <SliderField
                  label="Drawdown máximo mensal"
                  value={(riskDraft ?? riskConfig).max_monthly_loss_pct}
                  onChange={v => setRiskDraft(d => ({ ...(d ?? riskConfig), max_monthly_loss_pct: v }))}
                  min={5} max={30} step={1}
                  unit="%"
                />
                <SliderField
                  label="Fração Kelly"
                  value={(riskDraft ?? riskConfig).kelly_fraction}
                  onChange={v => setRiskDraft(d => ({ ...(d ?? riskConfig), kelly_fraction: v }))}
                  min={0.1} max={1} step={0.05}
                />
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: 13 }}>Circuit breaker</span>
                  <button
                    className={`toggle${(riskDraft ?? riskConfig).circuit_breaker_enabled ? ' on' : ''}`}
                    onClick={() => setRiskDraft(d => ({ ...(d ?? riskConfig), circuit_breaker_enabled: !(d ?? riskConfig).circuit_breaker_enabled }))}
                    type="button"
                  />
                </div>
              </div>
              <div style={{ marginTop: 14, display: 'flex', justifyContent: 'flex-end' }}>
                <Btn variant="primary" size="sm" disabled={!canRisk || !changedKeys(riskDraft, riskConfig).length}
                  onClick={saveRisk}>Salvar risco</Btn>
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
                  value={parseFloat((((alertDraft ?? alertConfig).revenge_size_multiplier - 1) * 100).toFixed(0))}
                  onChange={v => setAlertDraft(d => ({ ...(d ?? alertConfig), revenge_size_multiplier: 1 + v / 100 }))}
                  min={10} max={100} step={5}
                  unit="%"
                />
                <SliderField
                  label="Multiplicador euforia"
                  value={parseFloat((((alertDraft ?? alertConfig).euphoria_size_multiplier - 1) * 100).toFixed(0))}
                  onChange={v => setAlertDraft(d => ({ ...(d ?? alertConfig), euphoria_size_multiplier: 1 + v / 100 }))}
                  min={5} max={80} step={5}
                  unit="%"
                />
                <SliderField
                  label="Gap overconfidence"
                  value={parseFloat(((alertDraft ?? alertConfig).overconfidence_margin * 100).toFixed(0))}
                  onChange={v => setAlertDraft(d => ({ ...(d ?? alertConfig), overconfidence_margin: v / 100 }))}
                  min={5} max={40} step={5}
                  unit="%"
                />
                <SliderField
                  label="Alerta risco de ruína"
                  value={(alertDraft ?? alertConfig).risk_of_ruin_alert_pct}
                  onChange={v => setAlertDraft(d => ({ ...(d ?? alertConfig), risk_of_ruin_alert_pct: v }))}
                  min={1} max={15} step={0.5}
                  unit="%"
                />
              </div>
              <div style={{ marginTop: 14, display: 'flex', justifyContent: 'flex-end' }}>
                <Btn variant="primary" size="sm" disabled={!changedKeys(alertDraft, alertConfig).length}
                  onClick={saveAlert}>Salvar</Btn>
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

      {pendingSave && (
        <ConfigConfirmModal
          title={pendingSave.title}
          changes={pendingSave.changes}
          onConfirm={confirmSave}
          onClose={() => setPendingSave(null)}
        />
      )}
    </div>
  );
}
window.ScreenSettings = ScreenSettings;
