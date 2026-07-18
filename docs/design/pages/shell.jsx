/* ============================================================
   Criptotrade — Shell: Sidebar + Header
   ============================================================ */
const { useState, useEffect } = React;

const NAV = [
  { id: 'overview', icon: 'dollar',   label: 'Visão Geral' },
  { id: 'hitl',     icon: 'activity', label: 'HITL Controls' },
  { id: 'orders',   icon: 'list',     label: 'Ordens' },
  { id: 'agents',   icon: 'user',     label: 'Agentes' },
  { id: 'risk',     icon: 'shield',   label: 'Risco' },
  { id: 'market',   icon: 'trending', label: 'Mercado' },
  { id: 'observability', icon: 'eye', label: 'Observabilidade' },
  { id: 'journal',  icon: 'book',     label: 'Diário' },
  { id: 'backtest', icon: 'bar',      label: 'Backtest' },
  { id: 'settings', icon: 'settings', label: 'Config' },
];

// A3: admin group at the sidebar footer, filtered by permission (nav map §02
// of the admin handoff). A Visualizador/demo never sees these items — and the
// route guard in app.jsx also blocks direct hash access.
// Ordem do mapa de nav do handoff (§02): Conta, Usuários, Trilha, Segurança.
const ADMIN_NAV = [
  // A2: self-service — qualquer sessão autenticada (não é permissão de papel).
  { id: 'account', icon: 'user', label: 'Conta & Perfil', userOnly: true },
  { id: 'users', icon: 'shield', label: 'Usuários & Permissões', perm: 'manage_users' },
  // A4: operador+ (view_audit) — o demo público nunca vê a trilha (e-mail/IP reais).
  { id: 'audit', icon: 'clock', label: 'Trilha de Auditoria', perm: 'view_audit' },
  // A7: self-service — qualquer sessão autenticada (não é permissão de papel).
  { id: 'security', icon: 'lock', label: 'Segurança & Sessões', userOnly: true },
];

function Sidebar({ active, onNavigate, pendingCount }) {
  const adminItems = ADMIN_NAV.filter(item =>
    item.perm ? CT_AUTH.can(item.perm) : (item.userOnly ? CT_AUTH.kind() === 'user' : true));
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">C</div>
        <div>
          <div className="brand-name">Cripto<b>trade</b></div>
          <div className="brand-tag">Console v1</div>
        </div>
      </div>
      <nav className="nav">
        {NAV.map(item => (
          <button
            key={item.id}
            className={`nav-item${active === item.id ? ' active' : ''}`}
            onClick={() => onNavigate(item.id)}
          >
            <Icon name={item.icon} size={17} />
            {item.label}
            {item.id === 'hitl' && pendingCount > 0 && (
              <span className="nav-badge">{pendingCount}</span>
            )}
          </button>
        ))}
        {adminItems.length > 0 && (
          <>
            <div className="nav-label">Administração</div>
            {adminItems.map(item => (
              <button
                key={item.id}
                className={`nav-item${active === item.id ? ' active' : ''}`}
                onClick={() => onNavigate(item.id)}
              >
                <Icon name={item.icon} size={17} />
                {item.label}
              </button>
            ))}
          </>
        )}
      </nav>
    </aside>
  );
}
window.Sidebar = Sidebar;

// fmtPrice now lives in components.jsx (window.fmtPrice) — single source of truth (M7).

function Header({ onToggleAlerts, alertCount, auth, onLock, onLogout, onNavigate }) {
  const mock = !!window.USE_MOCK_DATA;
  const [health, setHealth] = useState(null);
  const [hitl, setHitl] = useState(null);
  const [pair, setPair] = useState(CT_PAIR.get());
  const [ticker, setTicker] = useState(null);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    CT_API.getHealth()
      .then(d => setHealth(d))
      .catch(() => setHealth({ status: 'offline' }));
    CT_API.getHITL()
      .then(d => setHitl(d))
      .catch(() => {});
    return CT_PAIR.subscribe(setPair);  // reflect the pair chosen on the Market screen
  }, []);

  const isAll = pair === 'ALL';

  useEffect(() => {
    if (mock || isAll) { setTicker(null); return; }
    let alive = true;
    CT_API.getTicker(pair)
      .then(t => { if (alive) setTicker(t); })
      .catch(() => { if (alive) setTicker(null); });
    return () => { alive = false; };
  }, [pair, mock, isAll]);

  const price = ticker?.last ?? CT.symbol?.price ?? 65200;
  const change = ticker?.change_24h_pct ?? CT.symbol?.change24h ?? 0;

  return (
    <header className="header">
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flex: 1 }}>
        <span style={{ fontFamily: 'var(--mono)', fontWeight: 600 }}>{isAll ? 'Portfólio' : pair}</span>
        {!isAll && (
          <>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 15, fontWeight: 500 }}>
              ${fmtPrice(price)}
            </span>
            <Badge variant={change >= 0 ? 'ok' : 'down'}>
              {change >= 0 ? '+' : ''}{fmtNum(change)}%
            </Badge>
          </>
        )}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        {hitl && (
          <Badge variant="neutral" dot={false}>
            <Icon name="shield" size={11} /> L{hitl.current_level ?? 2}
          </Badge>
        )}
        <Badge variant={health?.status === 'healthy' ? 'ok' : 'down'} dot={false}>
          {health?.status === 'healthy' ? 'Online' : health ? 'Offline' : '…'}
        </Badge>
        <Btn
          variant="ghost"
          size="sm"
          onClick={onToggleAlerts}
          style={{ position: 'relative', padding: '6px 8px' }}
        >
          <Icon name="bell" size={16} />
          {alertCount > 0 && (
            <span style={{
              position: 'absolute', top: 4, right: 4,
              width: 7, height: 7, borderRadius: '50%',
              background: 'var(--down)', border: '1.5px solid var(--surface)',
            }} />
          )}
        </Btn>

        {/* A1: user menu. Hidden when auth is disabled; "Entrar" in demo mode
            (lets the owner elevate to a real session on the public instance). */}
        {auth && auth.kind === 'user' && (
          <div style={{ position: 'relative' }}>
            <button className="user-chip" onClick={() => setMenuOpen(v => !v)}
              aria-haspopup="menu" aria-expanded={menuOpen} data-testid="user-menu"
              style={auth.user?.avatar_color && window.AVATAR_COLOR_VARS?.[auth.user.avatar_color]
                ? { background: window.AVATAR_COLOR_VARS[auth.user.avatar_color], color: '#fff' }
                : undefined}>
              {(auth.user?.name ?? auth.user?.email ?? '?').slice(0, 2).toUpperCase()}
            </button>
            {menuOpen && (
              <div className="user-menu" role="menu">
                <div style={{ padding: '10px 12px', borderBottom: '1px solid var(--border)' }}>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>{auth.user?.name ?? auth.user?.email}</div>
                  <div style={{ fontSize: 11.5, color: 'var(--ink-3)' }}>
                    {auth.user?.email} · {auth.user?.role}
                  </div>
                </div>
                {/* A2 (aceite): o menu do avatar abre Conta · Segurança · Sair. */}
                <button className="user-menu-item" role="menuitem"
                  onClick={() => { setMenuOpen(false); onNavigate?.('account'); }}>
                  <Icon name="user" size={13} /> Conta
                </button>
                <button className="user-menu-item" role="menuitem"
                  onClick={() => { setMenuOpen(false); onNavigate?.('security'); }}>
                  <Icon name="shield" size={13} /> Segurança
                </button>
                <button className="user-menu-item" role="menuitem"
                  onClick={() => { setMenuOpen(false); onLock?.(); }}>
                  <Icon name="lock" size={13} /> Bloquear tela
                </button>
                <button className="user-menu-item" role="menuitem"
                  onClick={() => { setMenuOpen(false); onLogout?.(); }}>
                  <Icon name="logout" size={13} /> Sair
                </button>
              </div>
            )}
          </div>
        )}
        {auth && auth.kind === 'demo' && (
          <Btn variant="ghost" size="sm" onClick={() => { CT_AUTH.apply({ mode: 'required', authenticated: false }); }}
            data-tip="Entrar com uma conta real (o modo demonstração continua público)">
            Entrar
          </Btn>
        )}
      </div>
    </header>
  );
}
window.Header = Header;
