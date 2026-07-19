/* ============================================================
   Criptotrade — App root: routing, alerts drawer, toasts
   ============================================================ */
const { useState, useEffect, useCallback, useRef } = React;

// ---- Screen registry ----
const SCREENS = {
  desk:          ScreenDesk,
  overview:      ScreenOverview,
  hitl:          ScreenHITL,
  orders:        ScreenOrders,
  agents:        ScreenAgents,
  risk:          ScreenRisk,
  market:        ScreenMarket,
  observability: ScreenObservability,
  journal:       ScreenJournal,
  backtest:      ScreenBacktest,
  settings:      ScreenSettings,
  users:         ScreenUsers,
  audit:         ScreenAudit,
  security:      ScreenSecurity,
  account:       ScreenAccount,
  notifications: ScreenNotifications,
  connections:   ScreenConnections,
  onboarding:    ScreenOnboarding,
};

// ---- Error boundaries (A9) ----
// Short, support-friendly error id, logged alongside the stack so the operator
// can quote it and the log line can be found.
const newErrorId = () =>
  Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 8);

class ErrorBoundary extends React.Component {
  constructor(props) { super(props); this.state = { error: null, errorId: null }; }
  static getDerivedStateFromError(e) { return { error: e, errorId: newErrorId() }; }
  componentDidCatch(e) { console.error(`[ct:${this.state.errorId}]`, e); }
  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 32, textAlign: 'center' }}>
          <Icon name="alert" size={32} style={{ color: 'var(--down)', margin: '0 auto 12px' }} />
          <div style={{ fontSize: 14, color: 'var(--ink-2)', marginBottom: 8 }}>
            Erro inesperado nesta tela
          </div>
          <div style={{ fontSize: 12, fontFamily: 'var(--mono)', color: 'var(--ink-3)', marginBottom: 6 }}>
            {this.state.error?.message ?? String(this.state.error)}
          </div>
          <div style={{ fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--ink-4)', marginBottom: 16 }}>
            erro {this.state.errorId}
          </div>
          <Btn variant="ghost" size="sm" onClick={() => this.setState({ error: null, errorId: null })}>
            <Icon name="refresh" size={13} /> Tentar novamente
          </Btn>
        </div>
      );
    }
    return this.props.children;
  }
}

// Top-level boundary: an exception OUTSIDE a screen (shell, drawers, auth) no
// longer kills the app — it lands on the fatal page with the error id (A9).
class GlobalBoundary extends React.Component {
  constructor(props) { super(props); this.state = { error: null, errorId: null }; }
  static getDerivedStateFromError(e) { return { error: e, errorId: newErrorId() }; }
  componentDidCatch(e) { console.error(`[ct:${this.state.errorId}]`, e); }
  render() {
    if (this.state.error) {
      return <FatalErrorScreen errorId={this.state.errorId}
        message={this.state.error?.message ?? String(this.state.error)} />;
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
    if (!hash || SCREENS[hash]) return hash || 'overview';
    if (hash.startsWith('reset/')) return 'overview';  // pre-auth deep link (A1)
    return 'notfound';
  };

  const [screen,       setScreen]       = useState(getInitialScreen);
  const [pendingCount, setPendingCount] = useState(CT.pendingOrders?.length ?? 0);
  const [showAlerts,   setShowAlerts]   = useState(false);
  const [showTweaks,   setShowTweaks]   = useState(false);
  const [alertCount,   setAlertCount]   = useState(CT.alerts?.length ?? 0);
  const [toasts,       setToasts]       = useState([]);
  // A1 auth gate: 'loading' → probe /v1/auth/me; 'login' → auth screens instead
  // of the shell; 'ready' → shell (kind 'off'/'user'/'demo'). Locked = overlay.
  const [auth,   setAuth]   = useState(() => CT_AUTH.state());
  const [booted, setBooted] = useState(false);
  const [locked, setLocked] = useState(false);
  const toastId = useRef(0);

  useEffect(() => {
    // Subscribe BEFORE loading: the mock branch of load() emits synchronously,
    // so a late subscription would miss the initial state.
    const unsub = CT_AUTH.subscribe(setAuth);
    CT_AUTH.load().then((s) => { setAuth(s); setBooted(true); });
    return unsub;
  }, []);

  // A2: preference changes re-render the whole tree — the central formatting
  // helpers read CT_PREFS at call time, so a render pass is all it takes.
  const [, setPrefsRev] = useState(0);
  useEffect(() => CT_PREFS.subscribe(() => setPrefsRev(n => n + 1)), []);

  // A10: first admin login with an incomplete guide opens it — ONCE per boot,
  // never hijacking an explicit deep link. Mock default is "completed" so the
  // e2e suite boots unchanged; MOCK_ONBOARDING='pending' opts in.
  const initialHashRef = useRef(window.location.hash.replace('#', ''));
  useEffect(() => {
    if (!booted || auth.kind !== 'user' || auth.user?.role !== 'admin') return;
    const initial = initialHashRef.current;
    if (initial && initial !== 'overview') return;
    const open = (st) => {
      if (st && !st.completed && !st.dismissed) navigate('onboarding');
    };
    if (window.USE_MOCK_DATA) {
      if (window.MOCK_ONBOARDING === 'pending') open({ completed: false, dismissed: false });
      return;
    }
    CT_API.getOnboarding().then(open).catch(() => {});
  }, [booted, auth.kind]);

  // N2 (Fase 9): Mesa Multi-Ativo is the landing when the loop trades >1 pair
  // (par único mantém Visão Geral). Never hijacks an explicit deep link and
  // defers to the onboarding redirect for a first-run admin. Mirrors the effect
  // above; runs once per boot.
  const deskLandingRef = useRef(false);
  useEffect(() => {
    if (!booted || deskLandingRef.current) return;
    // Only a bare boot (empty hash) is a candidate — an explicit #overview (or any
    // deep link) is respected, never hijacked.
    if (initialHashRef.current) return;
    const onboardingWins = window.USE_MOCK_DATA
      ? (window.MOCK_ONBOARDING === 'pending' && auth.kind === 'user' && auth.user?.role === 'admin')
      : false;  // real onboarding runs in its own effect; the hash guard below yields
    if (onboardingWins) return;
    deskLandingRef.current = true;
    loadPairsRich().then((r) => {
      const operados = (r && r.operados) || [];
      const h = window.location.hash;
      if (operados.length > 1 && (!h || h === '#overview')) navigate('desk');
    }).catch(() => {});
  }, [booted, auth.kind]);

  // Inactivity lock (A1) — ONLY for real user sessions: the public demo has no
  // password to unlock with, so it never arms the timer (kiosk-safe).
  useEffect(() => {
    if (auth.kind !== 'user') return;
    let timer;
    const arm = () => {
      clearTimeout(timer);
      timer = setTimeout(() => setLocked(true), 15 * 60 * 1000);
    };
    const events = ['mousemove', 'keydown', 'click', 'visibilitychange'];
    events.forEach(e => window.addEventListener(e, arm, { passive: true }));
    arm();
    const onExpired = () => setLocked(true);
    window.addEventListener('ct:auth-expired', onExpired);
    return () => {
      clearTimeout(timer);
      events.forEach(e => window.removeEventListener(e, arm));
      window.removeEventListener('ct:auth-expired', onExpired);
    };
  }, [auth.kind]);

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
      else if (hash && !hash.startsWith('reset/')) setScreen('notfound');
    };
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  // Both live-data effects are gated on the auth boot so nothing hits the API
  // (and 401s) before the session state is known.
  const authReady = booted && auth.kind !== 'anonymous';

  // Poll pending orders count for sidebar badge
  useEffect(() => {
    if (!authReady) return;
    const tick = () => {
      CT_API.getOrders(200, 0, '&status=pending')
        .then(d => setPendingCount(Array.isArray(d) ? d.length : 0))
        .catch(() => {});
    };
    tick();
    const timer = setInterval(tick, 15000);
    return () => clearInterval(timer);
  }, [authReady]);

  // SSE for alerts — add toast on critical
  useEffect(() => {
    if (!authReady) return;
    const es = CT_API.subscribeAlerts((alert) => {
      setAlertCount(n => n + 1);
      if (alert.severity === 'critical' || alert.severity === 'high') {
        addToast(alert.message, 'alert');
      }
    }, () => {});
    return () => es?.close?.();
  }, [addToast, authReady]);

  // A9/A3: screens that demand a permission — navigating without it renders
  // the Forbidden page (coherent with the backend's 403 envelope), not a blank.
  const ROUTE_PERMS = {
    users: 'manage_users', audit: 'view_audit', notifications: 'edit_settings',
    connections: 'manage_keys', onboarding: 'manage_keys',
  };
  // A7: self-service screens need a real authenticated session (kind 'user'),
  // which is a different gate than a role permission. A10 rides both gates:
  // admin USER only (hidden under AUTH_MODE=off too).
  const USER_ONLY_ROUTES = ['security', 'account', 'onboarding'];
  const deniedPerm = ROUTE_PERMS[screen] && !CT_AUTH.can(ROUTE_PERMS[screen])
    ? ROUTE_PERMS[screen] : null;
  const denied = deniedPerm
    || (USER_ONLY_ROUTES.includes(screen) && auth.kind !== 'user');
  const ActiveScreen = screen === 'notfound'
    ? NotFoundScreen
    : (denied ? null : (SCREENS[screen] ?? ScreenOverview));

  // ---- A1 gate: probe → login → shell ----
  if (!booted) {
    return <div style={{ display: 'grid', placeItems: 'center', height: '100vh' }}>
      <LoadingState label="Carregando…" />
    </div>;
  }
  if (auth.mode === 'unreachable') {
    return <MaintenanceRetry />;
  }
  if (auth.kind === 'anonymous') {
    const resetMatch = window.location.hash.match(/^#reset\/(.+)$/);
    return <LoginScreen resetToken={resetMatch?.[1]}
      onAuthed={() => CT_AUTH.load()} />;
  }

  return (
    <div className="app">
      <Sidebar active={screen} onNavigate={navigate} pendingCount={pendingCount} />
      <div className="main">
        <Header
          onToggleAlerts={() => setShowAlerts(v => !v)}
          alertCount={alertCount}
          auth={auth}
          onLock={() => setLocked(true)}
          onLogout={() => CT_AUTH.logout()}
          onNavigate={navigate}
        />
        {auth.kind === 'demo' && <DemoBanner />}
        <div className="content">
          <div className="content-inner screen-enter">
            <ErrorBoundary key={screen}>
              {denied
                ? <ForbiddenScreen navigate={navigate} requiredPermission={deniedPerm}
                    role={auth.user?.role ?? (auth.kind === 'demo' ? 'visualizador' : undefined)} />
                : <ActiveScreen navigate={navigate} addToast={addToast} />}
            </ErrorBoundary>
          </div>
        </div>
      </div>

      {showAlerts && <AlertDrawer onClose={() => { setShowAlerts(false); setAlertCount(0); }} />}
      {showTweaks && <TweaksPanel onClose={() => setShowTweaks(false)} />}
      {locked && auth.kind === 'user' && (
        <LockScreen user={auth.user}
          onUnlocked={() => { setLocked(false); CT_AUTH.load(); }}
          onLogout={() => { setLocked(false); CT_AUTH.logout(); }} />
      )}

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

// A9: maintenance with an automatic 10s reconnect loop (re-probes /me).
function MaintenanceRetry() {
  useEffect(() => {
    const id = setInterval(() => { CT_AUTH.load(); }, 10_000);
    return () => clearInterval(id);
  }, []);
  return <MaintenanceScreen onRetry={() => CT_AUTH.load()} />;
}

// ---- Mount ----
const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<GlobalBoundary><App /></GlobalBoundary>);
