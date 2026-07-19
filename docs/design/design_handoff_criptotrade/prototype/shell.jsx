/* ============================================================
   Criptotrade — app shell (Sidebar + Header)
   ============================================================ */

const NAV = [
  { group: 'Operação', items: [
    { id: 'overview', label: 'Visão Geral', icon: 'grid', tip: 'Headline de performance do portfólio: P&L, Sharpe, win rate e drawdown num relance.' },
    { id: 'market', label: 'Mercado', icon: 'market', tip: 'Análise técnica ao vivo — candles, indicadores, padrões e o sinal de compra/venda da IA.' },
    { id: 'risk', label: 'Risco & Capital', icon: 'risk', tip: 'Guardrails, circuit breaker e dimensionamento — os limites que protegem o capital.' },
    { id: 'hitl', label: 'Console HITL', icon: 'hitl', badge: true, tip: 'Human-in-the-Loop: a fila de ordens que aguardam a sua aprovação ou rejeição.' },
    { id: 'orders', label: 'Ordens', icon: 'orders', tip: 'O ciclo de vida de cada ordem: pendente → aprovada → executada, e o histórico fechado.' },
  ]},
  { group: 'Inteligência', items: [
    { id: 'agents', label: 'Agentes & Estratégias', icon: 'agents', tip: 'Status dos agentes de IA (Strategy, Risk, Execution) e os parâmetros das estratégias.' },
    { id: 'journal', label: 'Diário', icon: 'journal', tip: 'Registro comportamental dos trades e métricas de disciplina (calibra Kelly e overconfidence).' },
    { id: 'backtest', label: 'Validação', icon: 'backtest', tip: 'Valida uma estratégia no histórico antes do paper: backtest, Monte Carlo e walk-forward.' },
  ]},
  { group: 'Sistema', items: [
    { id: 'observability', label: 'Observabilidade', icon: 'pulse', tip: 'Event log de cada ciclo do orquestrador (process mining) e métricas de operação.' },
    { id: 'settings', label: 'Configurações', icon: 'settings', tip: 'Todos os parâmetros: autonomia, capital, intervalo, fonte de dados e roteamento.' },
  ]},
];

function Sidebar({ active, onNav, pendingCount }) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">C</div>
        <div>
          <div className="brand-name">Cripto<b>trade</b></div>
          <div className="brand-tag">AI Trading · paper</div>
        </div>
      </div>
      <nav className="nav">
        {NAV.map(section => (
          <div key={section.group}>
            <div className="nav-label">{section.group}</div>
            {section.items.map(item => (
              <div key={item.id}
                className={'nav-item' + (active === item.id ? ' active' : '')}
                data-tip={item.tip || undefined}
                onClick={() => onNav(item.id)}>
                <Icon name={item.icon} size={17} className="ico" />
                {item.label}
                {item.badge && pendingCount > 0 && <span className="nav-badge">{pendingCount}</span>}
              </div>
            ))}
          </div>
        ))}
      </nav>
      <div className="nav-foot">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--ink-2)' }}>
          <span className="badge badge-ok" style={{ padding: '3px 7px' }}><span className="dot" />dry-run</span>
          <span className="muted" style={{ fontSize: 11 }}>zero conexão real</span>
        </div>
      </div>
    </aside>
  );
}

function Header({ regime, circuitBreaker, hitl, alertsCount, onBell }) {
  const [pair] = useCurrentPair();
  const cbOk = circuitBreaker.status === 'closed';
  const isAll = pair === 'ALL';
  const p = isAll ? null : (CT.pairBy[pair] || CT.pairs[0]);
  const m = CT.metricsBySymbol[isAll ? 'ALL' : pair];
  const priceVal = isAll ? m.portfolio_value_usdt : p.price;
  const chPct = isAll ? m.pnl_period_pct : p.change24h;
  const chUsd = isAll ? m.pnl_period_usdt : (p.price * p.change24h / 100);
  const up = chPct >= 0;
  return (
    <header className="header">
      {/* global pair selector (store CT_PAIR — compartilhado com Mercado, Visão Geral, Ordens, Backtest) */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <PairSelect allowAll />
        <div>
          <span className="mono" style={{ fontSize: 17, fontWeight: 600 }}>{fmtUsd(priceVal, isAll ? 0 : 2)}</span>
          <span className="mono" style={{ fontSize: 12.5, marginLeft: 8, color: up ? 'var(--up)' : 'var(--down)', fontWeight: 600 }}>
            {up ? '+' : ''}{chPct}% · {up ? '+' : ''}{fmtUsd(chUsd, isAll ? 0 : 2)}
          </span>
        </div>
      </div>

      <div className="vr" style={{ height: 28 }} />

      {/* regime */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 7 }} data-tip="Regime de mercado detectado automaticamente (Alta forte, Lateral, Caótico…). Define qual estratégia a IA prioriza.">
        <span className="label-xs">Regime</span>
        <Badge kind="info" dot>{regime.label} · {regime.strategy}</Badge>
      </div>

      {/* circuit breaker */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 7 }} data-tip="Disjuntor de segurança: pausa todo o trading se a perda diária passar de 4% ou após 3 perdas seguidas (cooldown 24h).">
        <span className="label-xs">Circuit Breaker</span>
        <Badge kind={cbOk ? 'ok' : 'down'} dot>{cbOk ? 'Fechado · operando' : 'Aberto · bloqueado'}</Badge>
      </div>

      {/* autonomy */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 7 }} data-tip="Nível de autonomia (0–3): define até que valor a IA aprova ordens sozinha. Acima do limite, exige você no HITL.">
        <span className="label-xs">Autonomia</span>
        <Badge kind="neutral"><Icon name="zap" size={12} />Nível {hitl.level}/3</Badge>
      </div>

      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 }}>
        <span className="chip" data-tip="Conexão com o backend ativa. Em demo, os dados são mockados (zero conexão real à exchange)."><span className="dot" style={{ width: 6, height: 6, borderRadius: 99, background: 'var(--up)', display: 'inline-block' }} />online</span>
        <button className="btn btn-ghost" style={{ padding: 8, position: 'relative' }} onClick={onBell} data-tip="Central de alertas: rejeições de risco, circuit breaker e avisos de dados em tempo real.">
          <Icon name="bell" size={18} />
          {alertsCount > 0 && <span style={{ position: 'absolute', top: 4, right: 4, width: 7, height: 7, borderRadius: 99, background: 'var(--down)', border: '1.5px solid #fff' }} />}
        </button>
        <div style={{ width: 30, height: 30, borderRadius: 99, background: 'var(--surface-3)', display: 'grid', placeItems: 'center', fontWeight: 600, fontSize: 12, color: 'var(--ink-2)' }} data-tip="Operador logado (mock da demo). No produto real, o menu abre Conta, Segurança, Bloquear e Sair — com login, 2FA, papéis e auditoria já entregues.">OP</div>
      </div>
    </header>
  );
}

Object.assign(window, { Sidebar, Header, NAV });
