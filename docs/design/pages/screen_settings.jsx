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

function ScreenSettings() {
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
  const [loading,      setLoading]      = useState(!mock);
  const [error,        setError]        = useState(null);
  const [saved,        setSaved]        = useState(null);

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
    } catch (e) { console.error(e); }
  };

  const saveRiskConfig = async (patch) => {
    if (mock) { setRiskConfig(prev => ({ ...prev, ...patch })); flash('Risco salvo'); return; }
    try {
      const updated = await CT_API.patchRiskConfig(patch);
      setRiskConfig(updated);
      flash('Risco salvo');
    } catch (e) { console.error(e); }
  };

  const saveAlertConfig = async (patch) => {
    if (mock) { setAlertConfig(prev => ({ ...prev, ...patch })); flash('Alertas salvos'); return; }
    try {
      const updated = await CT_API.patchAlertsConfig(patch);
      setAlertConfig(updated);
      flash('Alertas salvos');
    } catch (e) { console.error(e); }
  };

  if (loading) return <LoadingState label="Carregando configurações…" />;
  if (error)   return <ErrorState message="Erro ao carregar configurações" onRetry={() => { setError(null); setLoading(true); }} />;

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
          </div>
        )}

        {/* Risk config */}
        {riskConfig && (
          <div className="card">
            <SectionHead title="Gestão de Risco" icon="shield" />
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
          </div>
        )}

        {/* Behavioral alert thresholds */}
        {alertConfig && (
          <div className="card">
            <SectionHead title="Guardrails Comportamentais" icon="alert" />
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
            </div>
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
      </div>
    </div>
  );
}
window.ScreenSettings = ScreenSettings;
