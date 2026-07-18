/* ============================================================
   Criptotrade — App root (routing + toast)
   ============================================================ */
const { useState, useEffect, useCallback } = React;

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "accent": "#14181C",
  "density": "regular",
  "market": "classic"
}/*EDITMODE-END*/;

const MARKET_PALETTES = {
  classic: { up: '#0E9D6E', upBg: '#E7F6EF', upLine: '#B7E6D2', down: '#DC2B2B', downBg: '#FCEAEA', downLine: '#F3C9C9' },
  cb:      { up: '#1273A8', upBg: '#E4F0F7', upLine: '#BBD9EC', down: '#E07B00', downBg: '#FBEFDC', downLine: '#F0D5A8' },
};

function Placeholder({ title, icon, note }) {
  return (
    <div className="content-inner screen-enter">
      <div className="page-head"><div><div className="page-title">{title}</div><div className="page-sub">Em construção</div></div></div>
      <div className="card card-pad" style={{ display: 'grid', placeItems: 'center', minHeight: 360, textAlign: 'center', gap: 12 }}>
        <div style={{ width: 52, height: 52, borderRadius: 13, background: 'var(--surface-3)', display: 'grid', placeItems: 'center', color: 'var(--ink-3)' }}>
          <Icon name={icon} size={26} />
        </div>
        <div style={{ maxWidth: 380 }}>
          <div style={{ fontWeight: 600, marginBottom: 5 }}>{title}</div>
          <div className="muted" style={{ fontSize: 13, lineHeight: 1.5 }}>{note}</div>
        </div>
      </div>
    </div>
  );
}

function AlertsDrawer({ open, onClose }) {
  if (!open) return null;
  const ICON = { low: 'var(--up)', medium: 'var(--warn)', high: '#E8920C', critical: 'var(--down)' };
  const KIND = { low: 'ok', medium: 'warn', high: 'warn', critical: 'down' };
  return (
    <>
      <div className="drawer-scrim" onClick={onClose} />
      <div className="drawer">
        <div className="card-head" style={{ borderRadius: 0 }}>
          <div className="card-title"><Icon name="bell" size={16} className="ico" />Alertas</div>
          <button className="btn btn-ghost" style={{ padding: 6 }} onClick={onClose}><Icon name="x" size={18} /></button>
        </div>
        <div style={{ overflowY: 'auto', padding: 14 }}>
          {CT.alerts.map(a => (
            <div key={a.id} className="card card-pad" style={{ marginBottom: 10, borderLeft: `3px solid ${ICON[a.severity]}` }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                <Badge kind={KIND[a.severity]} dot>{a.type}</Badge>
                <span className="mono muted" style={{ fontSize: 11 }}>{a.at}</span>
              </div>
              <div style={{ fontSize: 13, lineHeight: 1.45 }}>{a.message}</div>
              {a.auto_action && <div style={{ marginTop: 8 }}><span className="chip"><Icon name="zap" size={12} />{a.auto_action}</span></div>}
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

function App() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [active, setActive] = useState('overview');
  const [bellOpen, setBellOpen] = useState(false);
  const [toasts, setToasts] = useState([]);
  const [pendingCount, setPendingCount] = useState(CT.pendingOrders.length);

  // apply tweaks → CSS variables
  useEffect(() => {
    const r = document.documentElement;
    r.style.setProperty('--accent', t.accent);
    const p = MARKET_PALETTES[t.market] || MARKET_PALETTES.classic;
    r.style.setProperty('--up', p.up); r.style.setProperty('--up-bg', p.upBg); r.style.setProperty('--up-line', p.upLine);
    r.style.setProperty('--down', p.down); r.style.setProperty('--down-bg', p.downBg); r.style.setProperty('--down-line', p.downLine);
  }, [t.accent, t.market]);

  const toast = useCallback((msg) => {
    const id = Math.random();
    setToasts(t => [...t, { id, msg }]);
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 2600);
  }, []);

  useEffect(() => { document.querySelector('.content')?.scrollTo(0, 0); }, [active]);

  const screens = {
    overview: window.OverviewScreen ? <OverviewScreen toast={toast} /> : <Placeholder title="Visão Geral" icon="grid" note="Headline de performance do portfólio." />,
    risk: <RiskScreen toast={toast} />,
    market: window.MarketScreen ? <MarketScreen toast={toast} /> : <Placeholder title="Dashboard de Mercado" icon="market" note="Candles, indicadores, padrões e zonas de suporte/resistência." />,
    hitl: window.HitlScreen ? <HitlScreen toast={toast} setPendingCount={setPendingCount} /> : <Placeholder title="Console HITL" icon="hitl" note="Aprovar e rejeitar ordens pendentes." />,
    orders: window.OrdersScreen ? <OrdersScreen toast={toast} /> : <Placeholder title="Ordens" icon="orders" note="Lifecycle completo das ordens." />,
    agents: window.AgentsScreen ? <AgentsScreen toast={toast} /> : <Placeholder title="Agentes & Estratégias" icon="agents" note="Status dos agentes e configuração de estratégias." />,
    journal: window.JournalScreen ? <JournalScreen toast={toast} /> : <Placeholder title="Diário Comportamental" icon="journal" note="Registro emocional e métricas de disciplina." />,
    backtest: window.BacktestScreen ? <BacktestScreen toast={toast} /> : <Placeholder title="Validação de Estratégias" icon="backtest" note="Backtest, Monte Carlo e walk-forward." />,
    settings: window.SettingsScreen ? <SettingsScreen toast={toast} /> : <Placeholder title="Configurações" icon="settings" note="Todos os parâmetros editáveis." />,
    observability: window.ObservabilityScreen ? <ObservabilityScreen toast={toast} /> : <Placeholder title="Observabilidade" icon="pulse" note="Event log de ciclos do orquestrador." />,
  };

  return (
    <div className="app" data-density={t.density}>
      <Sidebar active={active} onNav={setActive} pendingCount={pendingCount} />
      <div className="main">
        <Header regime={CT.regime} circuitBreaker={CT.circuitBreaker} hitl={CT.hitl} alertsCount={CT.alerts.length} onBell={() => setBellOpen(true)} />
        <div className="content">{screens[active]}</div>
      </div>
      {window.ExplainButton && <ExplainButton active={active} />}
      <AlertsDrawer open={bellOpen} onClose={() => setBellOpen(false)} />
      <div className="toast-wrap">
        {toasts.map(t => (
          <div key={t.id} className="toast"><Icon name="check" size={16} className="ico" />{t.msg}</div>
        ))}
      </div>
      <TweaksPanel title="Tweaks">
        <TweakSection label="Marca" />
        <TweakColor label="Acento" value={t.accent}
          options={['#14181C', '#283A8C', '#0F5C57', '#7A2230']}
          onChange={v => setTweak('accent', v)} />
        <TweakSection label="Layout" />
        <TweakRadio label="Densidade" value={t.density}
          options={['compact', 'regular']}
          onChange={v => setTweak('density', v)} />
        <TweakSection label="Dados de mercado" />
        <TweakRadio label="Buy / Sell" value={t.market}
          options={[{ value: 'classic', label: 'Clássico' }, { value: 'cb', label: 'Daltônico' }]}
          onChange={v => setTweak('market', v)} />
      </TweaksPanel>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
