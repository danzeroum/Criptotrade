/* ============================================================
   Criptotrade — Shell: Sidebar + Header
   ============================================================ */
const { useState, useEffect } = React;

const NAV = [
  { id: 'hitl',     icon: 'activity', label: 'HITL Controls' },
  { id: 'orders',   icon: 'list',     label: 'Ordens' },
  { id: 'agents',   icon: 'user',     label: 'Agentes' },
  { id: 'risk',     icon: 'shield',   label: 'Risco' },
  { id: 'market',   icon: 'trending', label: 'Mercado' },
  { id: 'journal',  icon: 'book',     label: 'Diário' },
  { id: 'backtest', icon: 'bar',      label: 'Backtest' },
  { id: 'settings', icon: 'settings', label: 'Config' },
];

function Sidebar({ active, onNavigate, pendingCount }) {
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
      </nav>
    </aside>
  );
}
window.Sidebar = Sidebar;

function Header({ onToggleAlerts, alertCount }) {
  const [health, setHealth] = useState(null);
  const [hitl, setHitl] = useState(null);

  useEffect(() => {
    CT_API.getHealth()
      .then(d => setHealth(d))
      .catch(() => setHealth({ status: 'offline' }));
    CT_API.getHITL()
      .then(d => setHitl(d))
      .catch(() => {});
  }, []);

  const sym = CT.symbol;
  const change = sym?.change24h ?? 0;

  return (
    <header className="header">
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flex: 1 }}>
        <span style={{ fontFamily: 'var(--mono)', fontWeight: 600 }}>{sym?.pair ?? 'BTC/USDT'}</span>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 15, fontWeight: 500 }}>
          ${Math.round(sym?.price ?? 65200).toLocaleString('en')}
        </span>
        <Badge variant={change >= 0 ? 'ok' : 'down'}>
          {change >= 0 ? '+' : ''}{change.toFixed(2)}%
        </Badge>
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
      </div>
    </header>
  );
}
window.Header = Header;
