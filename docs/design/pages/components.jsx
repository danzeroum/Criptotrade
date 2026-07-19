/* ============================================================
   Criptotrade — Base UI components
   Exposes: Icon, Card, Badge, Btn, KPI, Meter, Seg, Tabs,
            NumField, SliderField, LoadingState, EmptyState, ErrorState
   ============================================================ */

const { useState, useEffect, useRef } = React;

// ---- Formatting (M7 + A2) — single source of truth, preference-aware ----
// Charts used bare toLocaleString() (locale-dependent); screens forced 'en'.
// A2: the locale now comes from CT_PREFS ('auto' preserves the M7 en-US
// canon for numbers and pt-BR for dates), and dates honor the chosen
// timezone. NEVER format per-screen — always through these helpers (C7).
const numLocale = () => window.CT_PREFS?.numberLocale() ?? 'en';

function fmtNum(v, dp = 2) {
  if (v === null || v === undefined || Number.isNaN(+v)) return '—';
  return (+v).toLocaleString(numLocale(), { minimumFractionDigits: dp, maximumFractionDigits: dp });
}
function fmtUsd(v, dp = 2) {
  if (v === null || v === undefined || Number.isNaN(+v)) return '—';
  return `$${fmtNum(v, dp)}`;
}
function fmtPrice(v) {
  // Majors render as integers; sub-$10 coins (e.g. XRP) keep precision.
  if (v === null || v === undefined || Number.isNaN(+v)) return '—';
  return +v >= 10
    ? Math.round(+v).toLocaleString(numLocale())
    : (+v).toLocaleString(numLocale(), { maximumFractionDigits: 4 });
}
function fmtCompact(v) {
  // Dense axis labels: 3.4M / 67,667 / 12.34.
  if (v === null || v === undefined || Number.isNaN(+v)) return '–';
  const n = +v;
  if (Math.abs(n) >= 1e6) return `${fmtNum(n / 1e6, 1)}M`;
  if (Math.abs(n) >= 1e3) return Math.round(n).toLocaleString(numLocale());
  return fmtNum(n, 2);
}

// Date/time helpers (A2): locale + timezone come from CT_PREFS; extra Intl
// options may be passed for presets (e.g. chart axes).
function _dateOpts(options) {
  const tz = window.CT_PREFS?.timezone();
  return tz ? { timeZone: tz, ...options } : { ...options };
}
function fmtDateTime(ts, options = {}) {
  if (!ts) return '—';
  try {
    return new Date(ts).toLocaleString(window.CT_PREFS?.dateLocale() ?? 'pt-BR', _dateOpts(options));
  } catch (_) { return String(ts); }
}
function fmtDate(ts, options = {}) {
  if (!ts) return '—';
  try {
    return new Date(ts).toLocaleDateString(window.CT_PREFS?.dateLocale() ?? 'pt-BR', _dateOpts(options));
  } catch (_) { return String(ts); }
}
function fmtTime(ts, options = {}) {
  if (!ts) return '—';
  try {
    return new Date(ts).toLocaleTimeString(window.CT_PREFS?.dateLocale() ?? 'pt-BR', _dateOpts(options));
  } catch (_) { return String(ts); }
}
window.fmtNum = fmtNum;
window.fmtUsd = fmtUsd;
window.fmtPrice = fmtPrice;
window.fmtCompact = fmtCompact;
window.fmtDateTime = fmtDateTime;
window.fmtDate = fmtDate;
window.fmtTime = fmtTime;

// ---- Icon (inline SVG paths via name) ----
const ICONS = {
  lock:      'M19 11H5a2 2 0 00-2 2v7a2 2 0 002 2h14a2 2 0 002-2v-7a2 2 0 00-2-2zM7 11V7a5 5 0 0110 0v4',
  logout:    'M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4m7 14l5-5-5-5m5 5H9',
  alert:     'M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z',
  check:     'M20 6L9 17l-5-5',
  x:         'M18 6L6 18M6 6l12 12',
  info:      'M12 16v-4m0-4h.01M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z',
  trending:  'M23 6l-9.5 9.5-5-5L1 18',
  bar:       'M18 20V10M12 20V4M6 20v-6',
  grid:      'M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z',
  activity:  'M22 12h-4l-3 9L9 3l-3 9H2',
  settings:  'M12 15a3 3 0 100-6 3 3 0 000 6zm7.49-3.63a7.5 7.5 0 01.01.63 7.5 7.5 0 01-.01.63l1.58 1.24a.38.38 0 01.09.48l-1.5 2.59a.38.38 0 01-.46.17l-1.87-.75a7.47 7.47 0 01-1.09.63l-.28 1.99a.38.38 0 01-.37.31h-3a.38.38 0 01-.37-.31l-.28-1.99a7.47 7.47 0 01-1.09-.63l-1.87.75a.38.38 0 01-.46-.17l-1.5-2.59a.38.38 0 01.09-.48l1.58-1.24A7.48 7.48 0 014.5 12a7.48 7.48 0 01.01-.63L2.93 10.13a.38.38 0 01-.09-.48l1.5-2.59a.38.38 0 01.46-.17l1.87.75c.34-.23.71-.43 1.09-.63l.28-1.99A.38.38 0 018.41 4.7h3c.2 0 .36.14.37.31l.28 1.99c.38.2.75.4 1.09.63l1.87-.75a.38.38 0 01.46.17l1.5 2.59a.38.38 0 01-.09.48l-1.58 1.24z',
  shield:    'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z',
  clock:     'M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10zm0-7l-3-3V7',
  book:      'M4 19.5A2.5 2.5 0 016.5 17H20M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z',
  bell:      'M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 01-3.46 0',
  zap:       'M13 2L3 14h9l-1 8 10-12h-9l1-8z',
  refresh:   'M1 4v6h6M23 20v-6h-6M20.49 9A9 9 0 005.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 013.51 15',
  user:      'M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2M12 11a4 4 0 100-8 4 4 0 000 8z',
  dollar:    'M12 1v22M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6',
  eye:       'M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z M12 9a3 3 0 100 6 3 3 0 000-6z',
  play:      'M5 3l14 9-14 9V3z',
  stop:      'M18 6H6v12h12V6z',
  plus:      'M12 5v14M5 12h14',
  chevdown:  'M6 9l6 6 6-6',
  chevright: 'M9 18l6-6-6-6',
  candle:    'M9 4v2M9 18v2M15 4v2M15 18v2M7 6h4v5H7zm6 0h4v8h-4zM7 15h4v3H7zM13 18h4v-5h-4z',
  list:      'M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01',
};

function Icon({ name, size = 16, className = '' }) {
  const d = ICONS[name] || ICONS.info;
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size} height={size}
      viewBox="0 0 24 24"
      fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
      className={`ico ${className}`}
      aria-hidden="true"
    >
      <path d={d} />
    </svg>
  );
}
window.Icon = Icon;

// ---- Card ----
function Card({ title, icon, action, children, style }) {
  return (
    <div className="card" style={style}>
      {title && (
        <div className="card-head">
          <span className="card-title">
            {icon && <Icon name={icon} />}
            {title}
          </span>
          {action}
        </div>
      )}
      <div className="card-pad">{children}</div>
    </div>
  );
}
window.Card = Card;

// ---- Badge ----
function Badge({ variant = 'neutral', dot = true, children }) {
  return (
    <span className={`badge badge-${variant}`}>
      {dot && <span className="dot" />}
      {children}
    </span>
  );
}
window.Badge = Badge;

// ---- Btn ----
function Btn({ variant = '', size = '', onClick, disabled, children, style, ...rest }) {
  const cls = ['btn', variant ? `btn-${variant}` : '', size ? `btn-${size}` : ''].filter(Boolean).join(' ');
  // ...rest forwards aria-pressed / aria-label / title for accessible toggles (M8).
  return (
    <button className={cls} onClick={onClick} disabled={disabled} style={style} {...rest}>
      {children}
    </button>
  );
}
window.Btn = Btn;

// ---- KPI tile ----
function KPI({ label, value, sub, icon, delta, format = 'plain' }) {
  // A2: every branch goes through the central preference-aware helpers —
  // toFixed/toLocaleString('en') here would leak en-US past the user's format.
  const fmtVal = (v) => {
    if (v === null || v === undefined) return '—';
    if (format === 'pct') return `${fmtNum(+v * 100, 2)}%`;
    if (format === 'pct_direct') return `${fmtNum(+v, 2)}%`;
    if (format === 'usd') return fmtUsd(v);
    if (format === 'int') return fmtNum(v, 0);
    return String(v);
  };
  const deltaVariant = delta == null ? '' : delta > 0 ? 'ok' : delta < 0 ? 'down' : 'neutral';

  return (
    <div className="kpi">
      <div className="kpi-label">
        {icon && <Icon name={icon} size={14} />}
        {label}
      </div>
      <div className="kpi-value">{fmtVal(value)}</div>
      {(sub || delta != null) && (
        <div className="kpi-sub">
          {delta != null && (
            <span className={`badge badge-${deltaVariant}`} style={{ marginRight: 6 }}>
              {delta > 0 ? '+' : ''}{typeof delta === 'number' ? fmtNum(delta, 2) : delta}%
            </span>
          )}
          {sub}
        </div>
      )}
    </div>
  );
}
window.KPI = KPI;

// ---- Meter (progress bar) ----
function Meter({ value, max = 100, warn = 70, crit = 90 }) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  const color = pct >= crit ? 'var(--down)' : pct >= warn ? 'var(--warn)' : 'var(--up)';
  return (
    <div className="meter">
      <span style={{ width: `${pct}%`, background: color }} />
    </div>
  );
}
window.Meter = Meter;

// ---- Seg (segmented control) ----
function Seg({ options, value, onChange }) {
  return (
    <div className="seg">
      {options.map(o => (
        <button
          key={o.value ?? o}
          className={value === (o.value ?? o) ? 'active' : ''}
          onClick={() => onChange(o.value ?? o)}
        >
          {o.label ?? o}
        </button>
      ))}
    </div>
  );
}
window.Seg = Seg;

// ---- Tabs ----
function Tabs({ tabs, active, onChange }) {
  return (
    <div className="tabs">
      {tabs.map(t => (
        <button
          key={t.value ?? t}
          className={`tab${active === (t.value ?? t) ? ' active' : ''}`}
          onClick={() => onChange(t.value ?? t)}
        >
          {t.label ?? t}
        </button>
      ))}
    </div>
  );
}
window.Tabs = Tabs;

// ---- NumField ----
function NumField({ label, value, onChange, min, max, step = 0.1, unit = '' }) {
  return (
    <label style={{ display: 'block' }}>
      <span style={{ fontSize: 11.5, color: 'var(--ink-3)', fontWeight: 500 }}>{label}</span>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 4 }}>
        <input
          type="number"
          value={value}
          min={min} max={max} step={step}
          onChange={e => onChange(+e.target.value)}
          style={{
            flex: 1, padding: '7px 10px', borderRadius: 'var(--r-sm)',
            border: '1px solid var(--border-2)', background: 'var(--surface)',
            fontSize: 13, fontFamily: 'var(--mono)',
          }}
        />
        {unit && <span style={{ fontSize: 12, color: 'var(--ink-3)' }}>{unit}</span>}
      </div>
    </label>
  );
}
window.NumField = NumField;

// ---- SliderField ----
function SliderField({ label, value, onChange, min = 0, max = 100, step = 1, unit = '' }) {
  return (
    <label style={{ display: 'block' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ fontSize: 11.5, color: 'var(--ink-3)', fontWeight: 500 }}>{label}</span>
        <span style={{ fontSize: 11.5, fontFamily: 'var(--mono)', color: 'var(--ink-2)' }}>
          {value}{unit}
        </span>
      </div>
      <input type="range" className="range" value={value} min={min} max={max} step={step}
        onChange={e => onChange(+e.target.value)}
        aria-label={label} />
    </label>
  );
}
window.SliderField = SliderField;

// ---- Honest states ----
function LoadingState({ label = 'Carregando…' }) {
  return (
    <div style={{ padding: '48px 24px', textAlign: 'center', color: 'var(--ink-3)', fontSize: 13 }}>
      <div style={{ marginBottom: 10, fontSize: 20 }}>⋯</div>
      {label}
    </div>
  );
}
window.LoadingState = LoadingState;

function EmptyState({ label = 'Sem dados', sub = '' }) {
  return (
    <div style={{ padding: '48px 24px', textAlign: 'center' }}>
      <Icon name="list" size={32} style={{ color: 'var(--ink-4)', margin: '0 auto 12px' }} />
      <div style={{ fontSize: 13, color: 'var(--ink-2)', fontWeight: 500 }}>{label}</div>
      {sub && <div style={{ fontSize: 12, color: 'var(--ink-3)', marginTop: 4 }}>{sub}</div>}
    </div>
  );
}
window.EmptyState = EmptyState;

function ErrorState({ message = 'API offline', onRetry }) {
  return (
    <div style={{ padding: '32px 24px', textAlign: 'center' }}>
      <Icon name="alert" size={28} style={{ color: 'var(--down)', margin: '0 auto 10px' }} />
      <div style={{ fontSize: 13, color: 'var(--ink-2)', marginBottom: 12 }}>{message}</div>
      {onRetry && <Btn variant="ghost" size="sm" onClick={onRetry}>Tentar novamente</Btn>}
    </div>
  );
}
window.ErrorState = ErrorState;

// ---- Freshness badge (M3) ----
// Shows "atualizado há Xs" from a server `as_of` timestamp; turns amber and
// reads "desatualizado" once the data age passes `staleSec`. Ticks every second.
function FreshnessBadge({ asOf, staleSec = 120 }) {
  const [, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick(t => t + 1), 1000);
    return () => clearInterval(id);
  }, []);
  if (!asOf) return null;
  const ts = new Date(asOf).getTime();
  if (Number.isNaN(ts)) return null;
  const ageSec = Math.max(0, Math.floor((Date.now() - ts) / 1000));
  const stale = ageSec > staleSec;
  const rel = ageSec < 60 ? `${ageSec}s`
    : ageSec < 3600 ? `${Math.floor(ageSec / 60)}min`
    : `${Math.floor(ageSec / 3600)}h`;
  return (
    <span className={`badge badge-${stale ? 'warn' : 'neutral'}`}
      title={`Dados de ${fmtDateTime(asOf)}`}>
      <Icon name="clock" size={11} />
      {stale ? 'desatualizado há ' : 'atualizado há '}{rel}
    </span>
  );
}
window.FreshnessBadge = FreshnessBadge;

// ---- DataState (S1): one wrapper for loading / empty / error / stale ----
// Composes the honest-state components above so every data panel behaves the
// same. Reusable across screens (orders, risk, backtest…), not just Mercado.
// Pass children guarded (e.g. {data && <>…</>}) so they don't evaluate when empty.
function DataState({ loading, error, empty, stale, onRetry, emptyLabel = 'Sem dados', children }) {
  if (error) return <ErrorState message={typeof error === 'string' ? error : 'Erro ao carregar'} onRetry={onRetry} />;
  if (loading) return <LoadingState />;
  if (empty) return <EmptyState label={emptyLabel} />;
  return (
    <>
      {stale && (
        <div style={{ fontSize: 11, color: 'var(--warn)', padding: '0 0 8px' }}>
          ⚠ dados possivelmente desatualizados
        </div>
      )}
      {children}
    </>
  );
}
window.DataState = DataState;

// ---- Global pair scope (store lives on window.CT_PAIR, set in apiClient.js) ----
// 'ALL' = portfólio consolidado; senão um par concreto (ex.: 'BTC/USDT').
let _pairsPromise = null;
function loadPairs() {
  if (!_pairsPromise) {
    _pairsPromise = window.USE_MOCK_DATA
      ? Promise.resolve(['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT'])
      : CT_API.getPairs().catch(() => ['BTC/USDT']);
  }
  return _pairsPromise;
}
window.loadPairs = loadPairs;

// N1: rich pair source for the selector — operated (loop trades) vs observable
// (allowlist, analysis-only). Kept separate from loadPairs() so Mercado/Backtest
// (which want a flat list) are untouched. Mock shows both groups + enough items
// to trigger search, so the demo mirrors the multi-asset reality.
let _pairsRichPromise = null;
function loadPairsRich(force) {
  if (force) _pairsRichPromise = null;  // N8²: re-fetch after add/remove
  if (!_pairsRichPromise) {
    // e2e hook: window.MOCK_OPERATED (array of symbols) overrides the operated
    // set, so a spec can force single-pair (landing stays Visão Geral) vs multi.
    const mockOperated = (typeof window !== 'undefined' && window.MOCK_OPERATED) || null;
    _pairsRichPromise = window.USE_MOCK_DATA
      ? Promise.resolve({
          operados: (mockOperated || ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT'])
            .map((s, i) => ({ symbol: s, status: i === 4 ? 'aguardando' : 'operando',
                              paused: s === 'BNB/USDT',  // N9: one paused pair for the demo/screenshots
                              last_cycle_at: i === 4 ? null : new Date().toISOString() })),
          observaveis: ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT',
                        'ADA/USDT', 'DOGE/USDT', 'AVAX/USDT'],
        })
      : CT_API.getPairsRich().catch(() => ({
          operados: [{ symbol: 'BTC/USDT', status: 'aguardando', last_cycle_at: null }],
          observaveis: ['BTC/USDT'],
        }));
  }
  return _pairsRichPromise;
}
window.loadPairsRich = loadPairsRich;

function useCurrentPair() {
  const [pair, setPair] = useState(CT_PAIR.get());
  useEffect(() => CT_PAIR.subscribe(setPair), []);
  return [pair, (p) => CT_PAIR.set(p)];
}
window.useCurrentPair = useCurrentPair;

// Coerce the scope to a concrete pair for screens that require one (Mercado/Backtest).
function effectivePair(scope, pairs) {
  if (scope && scope !== 'ALL') return scope;
  if (pairs && pairs.includes('BTC/USDT')) return 'BTC/USDT';
  return (pairs && pairs[0]) || 'BTC/USDT';
}
window.effectivePair = effectivePair;

// Pair dropdown bound to the global store (N1). Custom popover — native <select>
// can't badge operated pairs nor offer search. Two groups (Operados badge verde ×
// Observáveis), search from >=8 items, "Portfólio (∑)" when `allowAll`. Renders
// from /v1/pairs so a SYMBOLS change reflects without touching the front.
function PairSelect({ allowAll = false }) {
  const [scope, setScope] = useCurrentPair();
  const [rich, setRich] = useState(null);
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  const [, bumpGroups] = useState(0);  // 11c: re-render when watchlists change
  const ref = useRef(null);

  useEffect(() => {
    let alive = true;
    loadPairsRich().then(r => { if (alive) setRich(r); });
    return () => { alive = false; };
  }, []);
  useEffect(() => CT_GROUPS.subscribe(() => bumpGroups(n => n + 1)), []);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('mousedown', onDoc); document.removeEventListener('keydown', onKey); };
  }, [open]);

  const operated = (rich && rich.operados) || [];
  const opSet = new Set(operated.map(o => o.symbol));
  const observable = ((rich && rich.observaveis) || []).filter(s => !opSet.has(s));
  const flat = operated.map(o => o.symbol).concat(observable);
  const showSearch = operated.length + observable.length >= 8;

  const hit = (s) => !q || s.toLowerCase().includes(q.toLowerCase());
  const opShown = operated.filter(o => hit(o.symbol));
  const obShown = observable.filter(hit);

  const label = (allowAll && scope === 'ALL') ? 'Portfólio (∑)' : effectivePair(scope, flat);
  const pick = (val) => { setScope(val); setOpen(false); setQ(''); };

  const optRow = (sym, badge) => (
    <div key={sym} role="option" aria-selected={scope === sym}
         className={'pair-opt' + (scope === sym ? ' sel' : '')}
         onClick={() => pick(sym)}>
      <span>{sym}</span>{badge}
    </div>
  );

  return (
    <div className="pairselect" ref={ref} style={{ position: 'relative' }}>
      <button type="button" className="input pair-btn" aria-haspopup="listbox"
        aria-expanded={open} aria-label="Par" onClick={() => setOpen(o => !o)}>
        <span>{label}</span><span className="pair-caret">▾</span>
      </button>
      {open && (
        <div className="pair-pop" role="listbox" aria-label="Selecionar par">
          {showSearch && (
            <input className="input pair-search" autoFocus placeholder="Buscar par…"
              value={q} onChange={(e) => setQ(e.target.value)} aria-label="Buscar par" />
          )}
          {allowAll && (!q || 'portfólio todos ∑'.includes(q.toLowerCase())) && (
            <div role="option" aria-selected={scope === 'ALL'}
                 className={'pair-opt' + (scope === 'ALL' ? ' sel' : '')}
                 onClick={() => pick('ALL')}>Portfólio (∑)</div>
          )}
          {(() => {
            // 11c: agrupa operados por watchlist quando há grupos; senão, o
            // cabeçalho fixo "Operados". Observáveis nunca entram em grupos.
            const opBadge = (o) => (
              <span className={'badge ' + (o.status === 'operando' ? 'badge-ok' : 'badge-neutral')}>
                <span className="dot"></span>{o.status}
              </span>
            );
            const groupNames = CT_GROUPS.names();
            if (groupNames.length === 0) {
              return [
                opShown.length > 0 && <div key="g-op" className="pair-group">Operados</div>,
                ...opShown.map(o => optRow(o.symbol, opBadge(o))),
              ];
            }
            const out = [];
            groupNames.forEach(g => {
              const members = opShown.filter(o => CT_GROUPS.groupOf(o.symbol) === g);
              if (members.length) {
                out.push(<div key={'g-' + g} className="pair-group">{g}</div>);
                members.forEach(o => out.push(optRow(o.symbol, opBadge(o))));
              }
            });
            const ungrouped = opShown.filter(o => !CT_GROUPS.groupOf(o.symbol));
            if (ungrouped.length) {
              out.push(<div key="g-none" className="pair-group">Operados · sem grupo</div>);
              ungrouped.forEach(o => out.push(optRow(o.symbol, opBadge(o))));
            }
            return out;
          })()}
          {obShown.length > 0 && <div className="pair-group">Observáveis</div>}
          {obShown.map(s => optRow(s, <span className="chip">análise</span>))}
          {opShown.length + obShown.length === 0 && (
            <div className="pair-empty">Nenhum par encontrado</div>
          )}
        </div>
      )}
    </div>
  );
}
window.PairSelect = PairSelect;
