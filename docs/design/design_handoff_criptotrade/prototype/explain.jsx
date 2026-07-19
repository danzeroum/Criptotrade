/* ============================================================
   Criptotrade — "Explicar simulação" (botão por tela)
   Conteúdo fundamentado no código real do repositório
   danzeroum/Criptotrade@master: src/api/routes/*, src/agents/*,
   src/analysis/*, src/orchestration/*, src/core/*, src/hitl/*.
   ============================================================ */
const { useState: _useSx, useEffect: _useEx } = React;

/* Cada tela: o que você vê (mock) ↔ o que acontece de verdade (pipeline real). */
const EXPLAIN = {
  overview: {
    icon: 'grid', title: 'Visão Geral',
    lead: 'O headline de performance do portfólio — Sharpe, win rate, drawdown, P&L e exposição.',
    endpoint: 'GET /v1/metrics',
    src: 'src/core/metrics.py · src/core/ledger.py · src/api/routes/metrics.py',
    steps: [
      ['Lê o ledger', 'O <b>PortfolioMetricsCalculator</b> percorre o ledger append-only (JSONL) e os eventos <code>position_closed</code> persistidos no SQLite WAL.'],
      ['Calcula as métricas', 'A partir dos fills e P&L realizado, computa <b>Sharpe, Win Rate, Max Drawdown, P&L e exposição</b> — os mesmos números expostos ao Prometheus (<code>criptotrade_sharpe_ratio</code> etc.).'],
      ['Serve via API', 'A API FastAPI responde <code>GET /v1/metrics</code>; o número é correto mesmo com o loop de trading rodando em <b>outro processo</b> (estado compartilhado por SQLite).'],
    ],
  },
  market: {
    icon: 'market', title: 'Dashboard de Mercado',
    lead: 'Candles, indicadores técnicos, padrões, regime e zonas de suporte/resistência — e o sinal do StrategyAgent.',
    endpoint: 'GET /v1/market/* · pipeline do StrategyAgent',
    src: 'src/analysis/{indicators,pattern_scanner,regime_detector,support_resistance,volume_profile}.py · src/agents/strategy_agent.py',
    steps: [
      ['Busca OHLCV na exchange', 'Com <code>EXCHANGE_DRY_RUN=false</code>, o <b>exchange_client</b> (ccxt/Binance) busca candles reais. Em dry-run, usa o motor sintético determinístico (zero rede).'],
      ['Roda a análise técnica', 'Os módulos de <code>src/analysis</code> calculam <b>RSI, MACD, Estocástico, Bollinger, ATR</b>, detectam <b>padrões</b> e <b>regime</b>, e mapeiam <b>suporte/resistência</b> e <b>volume profile</b> — tudo determinístico.'],
      ['Camada de IA (opcional)', 'Se <code>LLM_ENABLED=true</code>, os indicadores viram contexto estruturado para um <b>LLM consultivo</b> (<code>LLM_PROVIDER</code>: Gemini ou DeepSeek) que produz uma <b>tese</b> (<code>llm_thesis</code>) e ajusta a <b>confiança</b>. Se a API falhar, o sistema segue no modo determinístico — a TA é o piso.'],
      ['Emite o sinal', 'Sai um sinal <code>{ação, entrada, stop, alvo, confiança}</code>. Confiança < 0,6 é descartada antes de chegar ao risco.'],
    ],
  },
  risk: {
    icon: 'risk', title: 'Risco & Capital',
    lead: 'Guardrails por ordem, circuit breaker e dimensionamento de posição.',
    endpoint: 'GET /v1/risk/* · RiskAgent + GuardrailSystem',
    src: 'src/agents/risk_agent.py · src/safety/guardrails.py · src/orchestration/squad_orchestrator.py',
    steps: [
      ['Valida o sinal', 'O <b>RiskAgent</b> aplica os <b>guardrails</b>: tamanho de posição ≤ 5% do portfólio, <b>stop loss obrigatório</b> e <b>risk-reward ≥ 2.5</b>. Violou → <code>rejected</code> com motivo + alerta publicado.'],
      ['Confere o circuit breaker', 'O <b>CircuitBreaker</b> abre se a perda diária ≤ −4% ou após 3 perdas seguidas, com <b>cooldown de 24h</b>. O estado é <b>persistido em SQLite</b> — sobrevive a um restart do loop.'],
      ['Gate de capital', 'O dimensionamento usa o capital <b>disponível real</b> (base + P&L realizado − exposição aberta), não o capital inicial fixo.'],
    ],
  },
  hitl: {
    icon: 'hitl', title: 'Console HITL (Human-in-the-Loop)',
    lead: 'A fila de ordens pendentes que aguardam aprovação ou rejeição humana.',
    endpoint: 'GET /v1/orders · PATCH /v1/orders/{id}/status',
    src: 'src/hitl/orders.py (OrderStore) · src/hitl/config.py · src/orchestration/squad_orchestrator.py',
    steps: [
      ['Ordem entra na ponte', 'Aprovada no risco, a ordem é gravada no <b>OrderStore</b> (SQLite WAL) — a ponte cross-process entre o loop de trading e o operador.'],
      ['Auto ou manual', 'Pelo nível de <b>autonomia (0–3)</b>: se o notional ≤ threshold e não é crítica, vai <code>pending→filled</code> direto. Senão, espera você: <code>pending→approved→filled</code>.'],
      ['Fail-closed por timeout', 'Sem decisão dentro do <code>decision_timeout</code> (padrão 300s), a ordem é <b>cancelada automaticamente</b> — o sistema nunca executa por omissão.'],
      ['Tudo auditado', 'Aprovar/rejeitar grava <code>log_hitl_approval</code> no ledger com o operador e o horário.'],
    ],
  },
  orders: {
    icon: 'orders', title: 'Ordens',
    lead: 'O ciclo de vida completo das ordens e o histórico de trades fechados.',
    endpoint: 'GET /v1/orders · GET /v1/trades/closed',
    src: 'src/api/routes/orders.py · src/api/routes/trades.py · src/core/ledger.py',
    steps: [
      ['Estado vivo', 'A lista vem do <b>OrderStore</b> (SQLite): cada ordem carrega status (<code>pending/approved/filled/rejected/cancelled</code>), par, lado e notional.'],
      ['Fills com slippage e taxa', 'No paper trading o <b>ExecutionAgent</b> aplica slippage e taxa reais ao preço executado — o P&L não é fabricado.'],
      ['Fechamento por SL/TP ou por casamento', 'Posições fecham ao bater stop/alvo <b>ou quando um fill oposto do grid casa (FIFO)</b> com o lote aberto — gerando <code>position_closed</code> com o P&L individual (design "Grid com casamento de posições").'],
    ],
  },
  agents: {
    icon: 'agents', title: 'Agentes & Estratégias',
    lead: 'O status dos agentes do squad e a configuração das estratégias.',
    endpoint: 'GET /v1/agents · GET /v1/agents/{id}',
    src: 'src/agents/registry.py · src/agents/{strategy,risk,execution}_agent.py',
    steps: [
      ['Registro dos agentes', 'O <b>AgentRegistry</b> lista os agentes. Os três do caminho vivo — <b>Strategy, Risk, Execution</b> — são reais; agentes ainda não implementados respondem <code>501</code> e ficam ocultos por padrão.'],
      ['Ciclos do dia', 'O <code>cycles_today</code> é um <b>SELECT COUNT</b> cross-process sobre <code>cycle_events</code> — conta os ciclos reais executados pelo loop, independente do processo da API.'],
      ['Estratégia', 'A estratégia ativa (ex.: DCA otimizado) e seus parâmetros vêm de <code>config/strategies/</code>.'],
    ],
  },
  journal: {
    icon: 'journal', title: 'Diário',
    lead: 'Registro comportamental dos trades e métricas de disciplina.',
    endpoint: 'GET /v1/journal',
    src: 'src/api/routes/journal.py · migrations/002_journal.sql',
    steps: [
      ['Entradas persistidas', 'Cada entrada do diário é gravada em tabela dedicada no SQLite (migration <code>002_journal</code>), vinculada à ordem/trade correspondente.'],
      ['Camada comportamental', 'Notas e estado emocional acompanham o resultado, alimentando as <b>métricas de disciplina</b> que esta tela resume.'],
    ],
  },
  backtest: {
    icon: 'backtest', title: 'Validação de Estratégias',
    lead: 'Backtest, Monte Carlo e walk-forward para validar uma estratégia antes do paper.',
    endpoint: 'GET /v1/backtest · POST /v1/backtest',
    src: 'src/api/routes/backtest.py · src/backtest/ · migrations/003_backtest_jobs.sql',
    steps: [
      ['Job assíncrono', 'Um backtest é submetido como <b>job persistido</b> em SQLite (migration <code>003_backtest_jobs</code>) e processado fora do request.'],
      ['Simulações', 'Roda a estratégia sobre histórico, com <b>Monte Carlo</b> (distribuição de resultados) e <b>walk-forward</b> (robustez fora da amostra).'],
      ['Resultado consultável', 'Métricas e curvas de equity ficam disponíveis por <code>GET /v1/backtest/{id}</code>.'],
    ],
  },
  observability: {
    icon: 'pulse', title: 'Observabilidade',
    lead: 'O event log dos ciclos do orquestrador e as métricas de operação.',
    endpoint: 'GET /v1/process/events · GET /metrics (Prometheus)',
    src: 'src/api/routes/process.py · src/core/ledger.py (XES) · src/api/observability.py',
    steps: [
      ['Event log XES', 'Cada passo do ciclo (strategy→risk→HITL→execução) é registrado como <b>event log XES</b> — pronto para <b>process mining</b> (PM4Py): descobrir o fluxo real e gargalos.'],
      ['Métricas Prometheus', 'O <code>/metrics</code> expõe contadores de domínio (posições abertas, trades, P&L, win-rate, Sharpe) + latência HTTP — o <b>Grafana</b> já vem provisionado.'],
      ['Saúde dos processos', '<code>/health</code> e <code>/health/ready</code> (checa o SQLite); o loop emite heartbeat por ciclo.'],
    ],
  },
  settings: {
    icon: 'settings', title: 'Configurações',
    lead: 'Os parâmetros operacionais — autonomia, capital, intervalo, fonte de dados e roteamento.',
    endpoint: 'GET/PATCH /v1/hitl/config · /v1/config',
    src: 'src/hitl/config.py · src/core/config.py · src/api/routes/config.py',
    steps: [
      ['Variáveis de ambiente', 'Refletem env reais: <code>EXCHANGE_DRY_RUN</code> (fonte de dados), <code>ORDER_ROUTING</code> (paper/live), <code>LLM_ENABLED</code> + <code>LLM_PROVIDER</code> (Gemini/DeepSeek), <code>AUTONOMY_LEVEL</code>, <code>INITIAL_CAPITAL</code>, <code>ORCHESTRATOR_INTERVAL_SECONDS</code>.'],
      ['Autonomia 0–3', 'O nível define o threshold de auto-aprovação (R$0 / $500 / $1k / $5k) consumido pelo HITL.'],
      ['Auditável', 'Toda alteração sensível é registrada no <b>ledger</b> — nada muda em silêncio.'],
    ],
  },
};

function ExplainButton({ active }) {
  const [open, setOpen] = _useSx(false);
  const data = EXPLAIN[active];
  _useEx(() => {
    if (!open) return;
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);
  if (!data) return null;

  return (
    <>
      <button className="explain-fab" onClick={() => setOpen(true)} aria-label="Explicar o que esta tela representa">
        <Icon name="info" size={17} />
        <span>Como funciona de verdade</span>
      </button>

      {open && (
        <div className="explain-scrim" onClick={() => setOpen(false)}>
          <div className="explain-modal" onClick={e => e.stopPropagation()} role="dialog" aria-modal="true">
            <div className="explain-head">
              <div className="explain-head-ic"><Icon name={data.icon} size={18} /></div>
              <div style={{ flex: 1 }}>
                <div className="explain-kicker">Explicação da simulação</div>
                <div className="explain-title">{data.title}</div>
              </div>
              <button className="btn btn-ghost" style={{ padding: 6 }} onClick={() => setOpen(false)} aria-label="Fechar"><Icon name="x" size={18} /></button>
            </div>

            <div className="explain-body">
              <p className="explain-lead">{data.lead}</p>

              <div className="explain-demo">
                <span className="badge badge-warn" style={{ flexShrink: 0 }}><span className="dot" />Demonstração</span>
                <div>Nesta tela os dados são <b>mockados e determinísticos</b> (zero conexão real) — pensados para apresentar o produto. Abaixo, o que o sistema executa <b>em produção</b>.</div>
              </div>

              <div className="explain-steps-label">Na realidade, passo a passo</div>
              <ol className="explain-steps">
                {data.steps.map((s, i) => (
                  <li key={i}>
                    <span className="es-num">{i + 1}</span>
                    <div className="es-tx"><b>{s[0]}.</b> <span dangerouslySetInnerHTML={{ __html: s[1] }} /></div>
                  </li>
                ))}
              </ol>

              <div className="explain-meta">
                <div className="em-row"><span className="em-k">Endpoint</span><code>{data.endpoint}</code></div>
                <div className="em-row"><span className="em-k">No código</span><span className="em-src mono">{data.src}</span></div>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

Object.assign(window, { ExplainButton, EXPLAIN });
