/* ============================================================
   Criptotrade — shared UI components + icon set
   Exports to window. Load after React/Babel.
   ============================================================ */

/* ---------- Icons (24x24 stroke) ---------- */
const ICON_PATHS = {
  risk: '<path d="M12 3l7 3v5c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6l7-3z"/><path d="M9.2 12l1.9 1.9L15 9.8"/>',
  market: '<path d="M3 3v18h18"/><rect x="6" y="9" width="3" height="7"/><rect x="11" y="5" width="3" height="11"/><rect x="16" y="11" width="3" height="5"/>',
  hitl: '<path d="M9 12l2 2 4-4"/><circle cx="12" cy="12" r="9"/>',
  orders: '<path d="M8 6h12M8 12h12M8 18h12"/><path d="M3.5 6h.01M3.5 12h.01M3.5 18h.01"/>',
  agents: '<rect x="5" y="7" width="14" height="11" rx="2"/><path d="M9 3v4M15 3v4M9 13h.01M15 13h.01M9 7V5M2 11v3M22 11v3"/>',
  journal: '<path d="M5 4h12a2 2 0 0 1 2 2v14l-3-2-3 2-3-2-3 2V6a2 2 0 0 1 2-2z" transform="translate(0,0)"/><path d="M8 8h8M8 12h6"/>',
  backtest: '<path d="M9 3h6M10 3v5l-5 9a2 2 0 0 0 1.8 3h10.4a2 2 0 0 0 1.8-3l-5-9V3"/><path d="M7.5 15h9"/>',
  settings: '<path d="M4 6h10M4 12h6M4 18h12"/><circle cx="17" cy="6" r="2"/><circle cx="13" cy="12" r="2"/><circle cx="19" cy="18" r="2"/>',
  bell: '<path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M10.3 21a2 2 0 0 0 3.4 0"/>',
  chevron: '<path d="M9 6l6 6-6 6"/>',
  chevronDown: '<path d="M6 9l6 6 6-6"/>',
  check: '<path d="M5 12l5 5L20 6"/>',
  x: '<path d="M6 6l12 12M18 6L6 18"/>',
  up: '<path d="M12 19V5M6 11l6-6 6 6"/>',
  down: '<path d="M12 5v14M6 13l6 6 6-6"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
  warn: '<path d="M12 4l9 16H3z"/><path d="M12 10v4M12 17h.01"/>',
  lock: '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
  zap: '<path d="M13 3L4 14h7l-1 7 9-11h-7z"/>',
  trendUp: '<path d="M3 17l6-6 4 4 7-7"/><path d="M17 8h4v4"/>',
  trendDown: '<path d="M3 7l6 6 4-4 7 7"/><path d="M17 16h4v-4"/>',
  dollar: '<path d="M12 2v20M17 6.5c0-2-2-3.5-5-3.5s-5 1.3-5 3.5S9 10 12 10s5 1 5 3.5-2 3.5-5 3.5-5-1.5-5-3.5"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  play: '<path d="M7 4l13 8-13 8z"/>',
  refresh: '<path d="M3 12a9 9 0 0 1 15-6.7L21 8M21 3v5h-5M21 12a9 9 0 0 1-15 6.7L3 16M3 21v-5h5"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4-4"/>',
  pulse: '<path d="M3 12h4l2-6 4 14 2-8h6"/>',
  layers: '<path d="M12 3l9 5-9 5-9-5 9-5z"/><path d="M3 13l9 5 9-5"/>',
  shield: '<path d="M12 3l7 3v5c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6l7-3z"/>',
  brain: '<path d="M9 4a3 3 0 0 0-3 3 3 3 0 0 0-1 5.8A3 3 0 0 0 8 18a3 3 0 0 0 4 1 3 3 0 0 0 4-1 3 3 0 0 0 3-5.2A3 3 0 0 0 18 7a3 3 0 0 0-3-3 3 3 0 0 0-3 1 3 3 0 0 0-3-1z"/>',
  target: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4"/><circle cx="12" cy="12" r="1"/>',
  flame: '<path d="M12 3s5 4 5 9a5 5 0 0 1-10 0c0-1.5.5-2.5 1-3 .3 1 1 1.5 1.5 1.5C9 9 12 7 12 3z"/>',
  grid: '<rect x="4" y="4" width="7" height="7" rx="1"/><rect x="13" y="4" width="7" height="7" rx="1"/><rect x="4" y="13" width="7" height="7" rx="1"/><rect x="13" y="13" width="7" height="7" rx="1"/>',
  filter: '<path d="M3 5h18l-7 8v6l-4-2v-4z"/>',
  dice: '<rect x="4" y="4" width="16" height="16" rx="3"/><path d="M9 9h.01M15 9h.01M9 15h.01M15 15h.01M12 12h.01"/>',
  history: '<path d="M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5"/><path d="M12 8v4l3 2"/>',
  arrowRight: '<path d="M5 12h14M13 6l6 6-6 6"/>',
};

function Icon({ name, size = 18, className = '', style = {}, strokeWidth = 1.7 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round"
      className={className} style={style}
      dangerouslySetInnerHTML={{ __html: ICON_PATHS[name] || '' }} />
  );
}

/* ---------- Card ---------- */
function Card({ children, className = '', style, pad }) {
  return <div className={'card ' + className} style={style}>{pad ? <div className="card-pad">{children}</div> : children}</div>;
}
function CardHead({ icon, title, sub, right }) {
  return (
    <div className="card-head">
      <div className="card-title">{icon && <Icon name={icon} size={16} className="ico" />}{title}</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        {sub && <span className="card-sub">{sub}</span>}
        {right}
      </div>
    </div>
  );
}

/* ---------- Badge ---------- */
function Badge({ kind = 'neutral', children, dot }) {
  return <span className={'badge badge-' + kind}>{dot && <span className="dot" />}{children}</span>;
}

/* ---------- Button ---------- */
function Btn({ kind = '', icon, iconRight, children, sm, ...rest }) {
  const cls = ['btn', kind && 'btn-' + kind, sm && 'btn-sm'].filter(Boolean).join(' ');
  return (
    <button className={cls} {...rest}>
      {icon && <Icon name={icon} size={sm ? 14 : 15} className="ico" />}
      {children}
      {iconRight && <Icon name={iconRight} size={sm ? 14 : 15} className="ico" />}
    </button>
  );
}

/* ---------- Toggle ---------- */
function Toggle({ on, onChange }) {
  return <button className={'toggle' + (on ? ' on' : '')} onClick={() => onChange(!on)} aria-pressed={on} />;
}

/* ---------- KPI tile ---------- */
function KPI({ label, value, sub, icon, accent, children }) {
  return (
    <div className="card kpi">
      <div className="kpi-label">{icon && <Icon name={icon} size={13} />}{label}</div>
      <div className="kpi-value" style={accent ? { color: accent } : null}>{value}</div>
      {sub && <div className="kpi-sub">{sub}</div>}
      {children}
    </div>
  );
}

/* ---------- StatRow ---------- */
function StatRow({ k, v, vColor, vClass }) {
  return (
    <div className="stat-row">
      <span className="stat-k">{k}</span>
      <span className={'stat-v ' + (vClass || '')} style={vColor ? { color: vColor } : null}>{v}</span>
    </div>
  );
}

/* ---------- Meter ---------- */
function Meter({ value, max = 100, color = 'var(--ink)', height = 7 }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return <div className="meter" style={{ height }}><span style={{ width: pct + '%', background: color }} /></div>;
}

/* ---------- Segmented control ---------- */
function Seg({ options, value, onChange, tip }) {
  return (
    <div className="seg" data-tip={tip || undefined}>
      {options.map(o => (
        <button key={o.value} className={value === o.value ? 'active' : ''} data-tip={o.tip || undefined} onClick={() => onChange(o.value)}>{o.label}</button>
      ))}
    </div>
  );
}

/* ---------- Tabs (pill) ---------- */
function Tabs({ options, value, onChange }) {
  return (
    <div className="tabs">
      {options.map(o => (
        <button key={o.value} className={'tab' + (value === o.value ? ' active' : '')} data-tip={o.tip || undefined} onClick={() => onChange(o.value)}>{o.label}</button>
      ))}
    </div>
  );
}

/* ---------- Number field with stepper ---------- */
function NumField({ label, hint, value, onChange, step = 1, min, max, suffix, decimals = 0 }) {
  const clamp = v => {
    if (min != null) v = Math.max(min, v);
    if (max != null) v = Math.min(max, v);
    return +v.toFixed(decimals);
  };
  return (
    <div className="field">
      {label && <span className="field-label">{label}</span>}
      <div className="input-wrap">
        <input className="input" type="number" value={value} step={step} min={min} max={max}
          onChange={e => onChange(clamp(parseFloat(e.target.value) || 0))} style={{ paddingRight: suffix ? 34 : 11 }} />
        {suffix && <span className="input-suffix">{suffix}</span>}
      </div>
      {hint && <span className="field-hint">{hint}</span>}
    </div>
  );
}

/* ---------- Slider field ---------- */
function SliderField({ label, value, onChange, min, max, step = 1, fmt = v => v, hint }) {
  return (
    <div className="field">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        {label && <span className="field-label">{label}</span>}
        <span className="mono" style={{ fontSize: 13, fontWeight: 600 }}>{fmt(value)}</span>
      </div>
      <input className="range" type="range" value={value} min={min} max={max} step={step}
        onChange={e => onChange(parseFloat(e.target.value))} />
      {hint && <span className="field-hint">{hint}</span>}
    </div>
  );
}

/* ---------- Honest states (Loading / Empty / Error) ---------- */
function StateBlock({ icon, tone, title, sub, action, min = 200 }) {
  return (
    <div style={{ display: 'grid', placeItems: 'center', gap: 12, padding: '40px 20px', minHeight: min, textAlign: 'center' }}>
      <div style={{ width: 46, height: 46, borderRadius: 12, background: 'var(--surface-3)', display: 'grid', placeItems: 'center', color: tone || 'var(--ink-3)' }}>
        <Icon name={icon} size={22} />
      </div>
      <div>
        <div style={{ fontWeight: 600, fontSize: 13.5 }}>{title}</div>
        {sub && <div className="muted" style={{ fontSize: 12.5, marginTop: 4, maxWidth: 320, lineHeight: 1.5 }}>{sub}</div>}
      </div>
      {action}
    </div>
  );
}
function LoadingState({ label = 'Carregando…', min }) {
  return <StateBlock icon="refresh" title={label} sub="Buscando dados da API." min={min} />;
}
function EmptyState({ message = 'Sem dados', hint = 'Ainda não há histórico para o filtro selecionado.', min }) {
  return <StateBlock icon="info" title={message} sub={hint} min={min} />;
}
function ErrorState({ message = 'API offline', hint = 'Não foi possível buscar os dados do backend.', onRetry, min }) {
  return <StateBlock icon="warn" tone="var(--down)" title={message} sub={hint} min={min}
    action={onRetry && <Btn sm icon="refresh" onClick={onRetry}>Tentar novamente</Btn>} />;
}

/* ---------- Backend-gap marker (campo/endpoint inexistente) ---------- */
function GapTag({ children = 'gap de backend' }) {
  return (
    <span className="badge badge-warn" style={{ fontSize: 10, padding: '2px 7px' }} title="Endpoint/campo ainda não existe no contrato — não inventar dados">
      <Icon name="warn" size={11} />{children}
    </span>
  );
}

/* ---------- Global pair store hook + selector ---------- */
const ALL_OPT = { symbol: 'ALL', glyph: '∑', color: 'var(--ink)', base: 'Portfólio', label: 'Todos os pares' };

function useCurrentPair() {
  const [p, setP] = React.useState(window.CT_PAIR ? window.CT_PAIR.get() : 'BTC/USDT');
  React.useEffect(() => {
    const h = e => setP(e.detail);
    window.addEventListener('ct:pair', h);
    setP(window.CT_PAIR.get());
    return () => window.removeEventListener('ct:pair', h);
  }, []);
  return [p, v => window.CT_PAIR.set(v)];
}

function PairGlyph({ p, size = 22 }) {
  return (
    <span style={{ width: size, height: size, borderRadius: 6, background: p.symbol === 'ALL' ? 'var(--surface-3)' : p.color, color: p.symbol === 'ALL' ? 'var(--ink)' : '#fff', display: 'grid', placeItems: 'center', fontFamily: 'var(--mono)', fontWeight: 700, fontSize: size * 0.55, flexShrink: 0 }}>{p.glyph}</span>
  );
}

function PairSelect({ allowAll = false, size = 'md' }) {
  const [pair, setPair] = useCurrentPair();
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef(null);
  React.useEffect(() => {
    if (!open) return;
    const h = e => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, [open]);
  const opts = (allowAll ? [ALL_OPT] : []).concat(CT.pairs);
  const cur = pair === 'ALL' ? ALL_OPT : (CT.pairBy[pair] || CT.pairs[0]);
  const gsz = size === 'sm' ? 18 : 22;
  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button className="btn" aria-label="Selecionar par" aria-haspopup="listbox" aria-expanded={open}
        data-tip="Troca o ativo exibido em todo o console (BTC, ETH, SOL…). 'Portfólio' soma todos os pares numa visão consolidada."
        onClick={() => setOpen(o => !o)}
        style={{ gap: 9, padding: size === 'sm' ? '5px 9px' : '7px 11px', background: 'var(--surface)' }}>
        <PairGlyph p={cur} size={gsz} />
        <b style={{ fontSize: size === 'sm' ? 13 : 14 }}>{cur.symbol === 'ALL' ? 'Portfólio' : cur.symbol}</b>
        <Icon name="chevronDown" size={14} style={{ color: 'var(--ink-3)' }} />
      </button>
      {open && (
        <div role="listbox" style={{ position: 'absolute', top: 'calc(100% + 6px)', left: 0, minWidth: 230, background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--r)', boxShadow: 'var(--sh-pop)', padding: 6, zIndex: 30 }}>
          {opts.map(p => {
            const on = p.symbol === pair;
            const m = (window.CT && CT.metricsBySymbol) ? CT.metricsBySymbol[p.symbol] : null;
            const ch = p.symbol === 'ALL' ? (m ? m.pnl_period_pct : null) : p.change24h;
            return (
              <button key={p.symbol} role="option" aria-selected={on}
                onClick={() => { setPair(p.symbol); setOpen(false); }}
                className="btn btn-ghost"
                style={{ width: '100%', justifyContent: 'flex-start', gap: 10, padding: '8px 9px', background: on ? 'var(--surface-3)' : 'transparent' }}>
                <PairGlyph p={p} size={22} />
                <div style={{ textAlign: 'left', flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>{p.symbol === 'ALL' ? 'Todos os pares' : p.symbol}</div>
                  <div className="muted" style={{ fontSize: 10.5 }}>{p.symbol === 'ALL' ? 'Visão consolidada' : p.base}</div>
                </div>
                {ch != null && <span className="mono" style={{ fontSize: 11.5, fontWeight: 600, color: ch >= 0 ? 'var(--up)' : 'var(--down)' }}>{ch >= 0 ? '+' : ''}{ch}%</span>}
                {on && <Icon name="check" size={15} style={{ color: 'var(--ink)' }} />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* ---------- helpers ---------- */
const fmtUsd = (v, d = 2) => '$' + Number(v).toLocaleString('pt-BR', { minimumFractionDigits: d, maximumFractionDigits: d });
const fmtPct = (v, d = 1) => (v >= 0 ? '' : '') + Number(v).toFixed(d) + '%';
const fmtNum = (v, d = 2) => Number(v).toLocaleString('pt-BR', { minimumFractionDigits: d, maximumFractionDigits: d });

Object.assign(window, {
  Icon, Card, CardHead, Badge, Btn, Toggle, KPI, StatRow, Meter, Seg, Tabs,
  NumField, SliderField, fmtUsd, fmtPct, fmtNum,
  LoadingState, EmptyState, ErrorState, GapTag,
  useCurrentPair, PairSelect, PairGlyph,
});
