/* ============================================================
   Criptotrade — App root: routing, alerts drawer, toasts
   ============================================================ */
const { useState, useEffect, useCallback, useRef } = React;

// ---- Screen registry ----
const SCREENS = {
  hitl:     ScreenHITL,
  orders:   ScreenOrders,
  agents:   ScreenAgents,
  risk:     ScreenRisk,
  market:   ScreenMarket,
  journal:  ScreenJournal,
  backtest: ScreenBacktest,
  settings: ScreenSettings,
};

// ---- Error boundary ----
class ErrorBoundary extends React.Component {
  constructor(props) { super(props); this.state = { error: null }; }
  static getDerivedStateFromError(e) { return { error: e }; }
  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 32, textAlign: 'center' }}>
          <Icon name="alert" size={32} style={{ color: 'var(--down)', margin: '0 auto 12px' }} />
          <div style={{ fontSize: 14, color: 'var(--ink-2)', marginBottom: 8 }}>
            Erro inesperado nesta tela
          </div>
          <div style={{ fontSize: 12, fontFamily: 'var(--mono)', color: 'var(--ink-3)', marginBottom: 16 }}>
            {this.state.error?.message ?? String(this.state.error)}
          </div>
          <Btn variant="ghost" size="sm" onClick={() => this.setState({ error: null })}>
            <Icon name="refresh" size={13} /> Tentar novamente
          </Btn>
        </div>
      );
    }
    return this.props.children;
  }
}

// ---- Alert Drawer ----
function AlertDrawer({ onClose }) {
  const [alerts, setAlerts] = useState(CT.alerts ?? []);
  const esRef = useRef(null);

  useEffect(() => {
    CT_API.getAlertHistory(50)
      .then(d => { if (Array.isArray(d)) setAlerts(d); })
      .catch(() => {});

    const es = CT_API.subscribeAlerts(
      (alert) => setAlerts(prev => [alert, ...prev].slice(0, 100)),
      () => {},
    );
    esRef.current = es;
    return () => es?.close?.();
  }, []);

  const SEVERITY_VARIANT = {
    critical: 'down',
    high:     'down',
    medium:   'warn',
    low:      'neutral',
  };

  return (
    <>
      <div className="drawer-scrim" onClick={onClose} />
      <div className="drawer">
        <div className="card-head" style={{ flexShrink: 0 }}>
          <span className="card-title">
            <Icon name="bell" />Alertas
            {alerts.length > 0 && (
              <span style={{ marginLeft: 6 }}>
                <Badge variant="neutral" dot={false}>{alerts.length}</Badge>
              </span>
            )}
          </span>
          <Btn variant="ghost" size="sm" onClick={onClose}><Icon name="x" size={14} /></Btn>
        </div>
        <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
          {alerts.length === 0 ? (
            <EmptyState label="Nenhum alerta" sub="Alertas em tempo real aparecerão aqui" />
          ) : alerts.map((a, i) => (
            <div
              key={a.id ?? i}
              style={{
                padding: '12px 0',
                borderBottom: i < alerts.length - 1 ? '1px solid var(--border)' : 'none',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, marginBottom: 4 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 7, flexWrap: 'wrap' }}>
                  <Badge variant={SEVERITY_VARIANT[a.severity] ?? 'neutral'}>
                    {a.severity}
                  </Badge>
                  {a.pair && (
                    <span style={{ fontSize: 11.5, fontFamily: 'var(--mono)', color: 'var(--ink-3)' }}>
                      {a.pair}
                    </span>
                  )}
                </div>
                <span style={{ fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--ink-4)', whiteSpace: 'nowrap' }}>
                  {a.at ?? a.timestamp ?? ''}
                </span>
              </div>
              <p style={{ fontSize: 13, color: 'var(--ink)', lineHeight: 1.5, margin: 0 }}>{a.message}</p>
              {a.auto_action && (
                <div style={{ fontSize: 11.5, color: 'var(--ink-3)', marginTop: 4 }}>
                  Ação: {a.auto_action}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

// ---- Toast ----
function ToastContainer({ toasts }) {
  if (!toasts.length) return null;
  return (
    <div className="toast-wrap">
      {toasts.map(t => (
        <div key={t.id} className="toast">
          <Icon name={t.icon ?? 'bell'} size={15} />
          {t.message}
        </div>
      ))}
    </div>
  );
}

// ---- App ----
function App() {
  const getInitialScreen = () => {
    const hash = window.location.hash.replace('#', '');
    return SCREENS[hash] ? hash : 'hitl';
  };

  const [screen,       setScreen]       = useState(getInitialScreen);
  const [pendingCount, setPendingCount] = useState(CT.pendingOrders?.length ?? 0);
  const [showAlerts,   setShowAlerts]   = useState(false);
  const [showTweaks,   setShowTweaks]   = useState(false);
  const [alertCount,   setAlertCount]   = useState(CT.alerts?.length ?? 0);
  const [toasts,       setToasts]       = useState([]);
  const toastId = useRef(0);

  const addToast = useCallback((message, icon = 'bell') => {
    const id = ++toastId.current;
    setToasts(prev => [...prev, { id, message, icon }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 4000);
  }, []);

  const navigate = useCallback((id) => {
    setScreen(id);
    window.location.hash = id;
  }, []);

  useEffect(() => {
    const onHash = () => {
      const hash = window.location.hash.replace('#', '');
      if (SCREENS[hash]) setScreen(hash);
    };
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  // Poll pending orders count for sidebar badge
  useEffect(() => {
    const tick = () => {
      CT_API.getOrders('?status=pending')
        .then(d => setPendingCount(Array.isArray(d) ? d.length : 0))
        .catch(() => {});
    };
    tick();
    const timer = setInterval(tick, 15000);
    return () => clearInterval(timer);
  }, []);

  // SSE for alerts — add toast on critical
  useEffect(() => {
    const es = CT_API.subscribeAlerts((alert) => {
      setAlertCount(n => n + 1);
      if (alert.severity === 'critical' || alert.severity === 'high') {
        addToast(alert.message, 'alert');
      }
    }, () => {});
    return () => es?.close?.();
  }, [addToast]);

  const ActiveScreen = SCREENS[screen] ?? ScreenHITL;

  return (
    <div className="app">
      <Sidebar active={screen} onNavigate={navigate} pendingCount={pendingCount} />
      <div className="main">
        <Header
          onToggleAlerts={() => setShowAlerts(v => !v)}
          alertCount={alertCount}
        />
        <div className="content">
          <div className="content-inner screen-enter">
            <ErrorBoundary key={screen}>
              <ActiveScreen />
            </ErrorBoundary>
          </div>
        </div>
      </div>

      {showAlerts && <AlertDrawer onClose={() => { setShowAlerts(false); setAlertCount(0); }} />}
      {showTweaks && <TweaksPanel onClose={() => setShowTweaks(false)} />}

      <ToastContainer toasts={toasts} />

      {/* Tweaks trigger — corner button */}
      <button
        onClick={() => setShowTweaks(v => !v)}
        title="Design tweaks"
        style={{
          position: 'fixed', bottom: 20, right: 20, zIndex: 30,
          width: 36, height: 36, borderRadius: '50%',
          background: 'var(--surface)', border: '1px solid var(--border)',
          boxShadow: 'var(--sh)', display: 'grid', placeItems: 'center',
          cursor: 'pointer', color: 'var(--ink-3)',
        }}
      >
        <Icon name="settings" size={15} />
      </button>
    </div>
  );
}

// ---- Mount ----
const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
