// Single source of truth for e2e mock DATA, ported from the console's mock
// sources (data.js / screen_desk._mockDesk). Condition #2 of the mock-cleanup
// plan: keep every fixture shape in ONE module so the final de-mock slice can
// delete data.js without a treasure hunt, and any shape drift lives in one place.
//
// TEST-ONLY. Never imported by production code — only by e2e specs / mockApi.js.

// Mirror of the backend RBAC matrix (src/auth/rbac.py) — permissions per role.
export const RBAC_MATRIX = {
  visualizador: [],
  operador: ["approve_order", "change_autonomy", "view_audit"],
  admin: ["approve_order", "change_autonomy", "change_risk", "edit_settings",
          "manage_keys", "view_audit", "manage_users"],
};

const DEMO_USER = {
  id: "u_demo", email: "demo@criptotrade.dev", name: "Operador Demo", role: "admin",
};

const DEFAULT_PREFS = {
  locale: "pt-BR", timezone: "auto", number_locale: "auto", date_locale: "auto",
};

// GET /v1/auth/me — MeOut per scenario (replaces the MOCK_AUTH/MOCK_ROLE globals).
//   authMode: 'none' (must log in) | 'demo' (public read-only) | 'user' (session)
//   role: applies to the 'user' scenario (drives the permission matrix).
export function authMe({ authMode = "user", role = "admin" } = {}) {
  if (authMode === "none") {
    return { mode: "required", authenticated: false, user: null, permissions: [] };
  }
  if (authMode === "demo") {
    return {
      mode: "demo", authenticated: false,
      user: { id: "demo", email: "demo@criptotrade", name: "Demo", role: "visualizador" },
      permissions: [],
    };
  }
  return {
    mode: "required", authenticated: true,
    user: { ...DEMO_USER, role },
    permissions: RBAC_MATRIX[role] ?? [],
    prefs: DEFAULT_PREFS,
  };
}

// GET /v1/pairs (rich) — >1 operados so the Mesa (N2) is the boot landing.
export const PAIRS_RICH = {
  operados: [
    { symbol: "BTC/USDT", last_cycle_at: null, status: "operando", paused: false },
    { symbol: "ETH/USDT", last_cycle_at: null, status: "operando", paused: false },
    { symbol: "SOL/USDT", last_cycle_at: null, status: "operando", paused: false },
    { symbol: "BNB/USDT", last_cycle_at: null, status: "operando", paused: true },
    { symbol: "XRP/USDT", last_cycle_at: null, status: "aguardando", paused: false },
  ],
  observaveis: ["ADA/USDT", "DOGE/USDT"],
};

// GET /v1/market/pairs (flat allowlist) — loadPairs().
export const PAIRS_FLAT = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"];

// GET /v1/desk/summary — the Mesa batch (ported from _mockDesk default rows).
export function deskSummary() {
  const iso = (minsAgo) => new Date(Date.now() - minsAgo * 60000).toISOString();
  return {
    rows: [
      { symbol: "SOL/USDT", last: 160.42, change_24h_pct: 4.81, regime: "strong_uptrend",
        regime_label: "Alta forte", signal_action: "buy", signal_confidence: 0.90,
        position_side: "buy", position_qty: 1.2, position_entry: 150.1, unrealized_pnl: 12.38,
        as_of: iso(1), last_cycle_at: iso(1), paused: false },
      { symbol: "BTC/USDT", last: 64810.0, change_24h_pct: 2.34, regime: "strong_uptrend",
        regime_label: "Alta forte", signal_action: "buy", signal_confidence: 0.82,
        position_side: "buy", position_qty: 0.03, position_entry: 61200.0, unrealized_pnl: 108.30,
        as_of: iso(1), last_cycle_at: iso(1), paused: false },
      { symbol: "ETH/USDT", last: 3208.5, change_24h_pct: -1.12, regime: "sideways",
        regime_label: "Lateral", signal_action: "sell", signal_confidence: 0.71,
        position_side: null, position_qty: null, position_entry: null, unrealized_pnl: null,
        as_of: iso(2), last_cycle_at: iso(2), paused: false },
      { symbol: "BNB/USDT", last: 592.3, change_24h_pct: 0.42, regime: "chaotic",
        regime_label: "Caótico", signal_action: "hold", signal_confidence: 0.34,
        position_side: null, position_qty: null, position_entry: null, unrealized_pnl: null,
        as_of: iso(2), last_cycle_at: iso(2), paused: true },
      { symbol: "XRP/USDT", last: 0.61, change_24h_pct: 1.05, regime: "unknown",
        regime_label: "Desconhecido", signal_action: null, signal_confidence: null,
        position_side: null, position_qty: null, position_entry: null, unrealized_pnl: null,
        as_of: null, last_cycle_at: null, paused: false },
    ],
    slots_used: 2, slots_max: 3, capital_allocated: 3673.0, capital_free: 6327.0,
    signals_active: 3,
  };
}

// GET /v1/onboarding/status — completed so the first-run redirect stays quiet.
export const ONBOARDING = { completed: true, dismissed: false, steps: [] };

// GET /health — the header's connectivity dot.
export const HEALTH = { status: "ok", paper_trading: true, dry_run: false };

// GET /v1/metrics — portfolio KPIs (overview + the Risco capital cards).
export function metrics() {
  return {
    has_data: true, calculated_at: new Date().toISOString(),
    portfolio_value_usdt: 10842.15, pnl_period_usdt: 842.15, pnl_period_pct: 0.0842,
    total_trades: 27, open_positions: 2, exposure_pct: 0.201,
    sharpe_ratio: 1.42, win_rate: 0.63, max_drawdown: 0.087, profit_factor: 1.9,
  };
}

// GET /v1/metrics/equity — the equity curve (empty = no history yet).
export const EQUITY = [];

// ---- Risco (screen_risk) — ported from the screen's inline mock blocks --------
export const RISK_PROTECTIONS = [
  { scope: "daily",   value: 1.2, limit: 4.0,  status: "ok", action: "none" },
  { scope: "weekly",  value: 3.1, limit: 8.0,  status: "ok", action: "none" },
  { scope: "monthly", value: 5.4, limit: 15.0, status: "ok", action: "none" },
];
export const RISK_CIRCUIT_BREAKER = {
  status: "armed", triggers: [], cooldown_hours: 24, cooldown_remaining: 0,
};
export const RISK_KELLY = {
  win_rate: 0.63, avg_win_pct: 2.1, avg_loss_pct: 1.2, full_kelly: 0.28,
  fraction: 0.5, fractional_kelly: 0.14, risk_of_ruin: 1.8, trades: 27, data_quality: "ok",
};
export const RISK_SLOTS = {
  slots_used: 2, slots_max: 3, capital: 10000, capital_free: 7984,
  slots: [
    { symbol: "BTC/USDT", side: "buy", notional: 1836, opened_at: null },
    { symbol: "SOL/USDT", side: "buy", notional: 180, opened_at: null },
  ],
  exposure: [
    { symbol: "BTC/USDT", notional: 1836, pct_of_capital: 18.36 },
    { symbol: "SOL/USDT", notional: 180, pct_of_capital: 1.8 },
  ],
};
export const RISK_SKIPS = [
  { symbol: "ETH/USDT", reason: "confidence_low", count: 4, confidence: 0.42 },
  { symbol: "XRP/USDT", reason: "no_slot", count: 2 },
  { symbol: "BNB/USDT", reason: "insufficient_capital", count: 1 },
];

// GET /v1/process/events (Observabilidade) — XES cycle traces with per-symbol
// durations (N6). Ported from screen_observability._mockProcessEvents.
export function processEvents() {
  const now = Date.now();
  const iso = (sAgo) => new Date(now - sAgo * 1000).toISOString();
  const cyc = (id, sAgo, perSymbol, failed) => {
    const syms = Object.keys(perSymbol);
    const dur = Object.values(perSymbol).reduce((a, b) => a + b, 0);
    const evs = [
      { case_id: id, activity: "agent_cycle_started", actor: "orchestrator",
        timestamp: iso(sAgo + 1), attributes: { symbols: syms } },
      { case_id: id, activity: "agent_cycle_completed", actor: "orchestrator",
        timestamp: iso(sAgo), attributes: {
          duration_ms: dur, ran: ["strategy", "risk"], failures: failed ? 1 : 0,
          per_symbol: perSymbol } },
    ];
    if (failed) evs.push({ case_id: id, activity: "agent_cycle_failed", actor: "strategy",
      timestamp: iso(sAgo + 0.5), attributes: { symbol: "ETH/USDT", error: "timeout" } });
    return evs;
  };
  return [
    ...cyc("cycle_a1b2", 12, { "BTC/USDT": 812, "ETH/USDT": 640, "SOL/USDT": 590 }, false),
    ...cyc("cycle_c3d4", 74, { "BTC/USDT": 903, "ETH/USDT": 1180, "SOL/USDT": 610 }, true),
    ...cyc("cycle_e5f6", 135, { "BTC/USDT": 780, "ETH/USDT": 655, "SOL/USDT": 602 }, false),
  ];
}

// ---- Config (screen_settings) — ported from the screen's inline mock blocks ----
export const SYS_CONFIG = {
  exchange: "binance", dry_run: true, initial_capital: 10000,
  orchestrator_interval_seconds: 60, autonomy_level: 1, app_env: "development",
};
export const RISK_CONFIG = {
  max_position_size_pct: 5, stop_loss_default_pct: 3, take_profit_default_pct: 6,
  max_daily_loss_pct: 4, max_weekly_loss_pct: 8, max_monthly_loss_pct: 15,
  kelly_fraction: 0.5, circuit_breaker_enabled: true,
};
// GET /v1/agents — the Config screen lists agents; empty is a valid honest state.
export const AGENTS = [];

// ---- Mercado (screen_market) — análise completa por endpoint ------------------
export function candles(pair = "BTC/USDT") {
  const base = pair.startsWith("BTC") ? 64000 : pair.startsWith("ETH") ? 3200 : 150;
  const now = Date.now();
  return Array.from({ length: 70 }, (_, i) => {
    const c = base * (1 + Math.sin(i / 6) * 0.012);
    return { t: now - (69 - i) * 3600e3, o: c * 0.999, h: c * 1.005, l: c * 0.995, c, v: 900 + (i % 10) * 40 };
  });
}
export const MARKET_INDICATORS = {
  rsi: 57.2, macd: { macd: 42.1, signal: 38.0, hist: 4.1 }, stoch: { k: 61, d: 55 },
  bb: { up: 65200, mid: 64500, low: 63800, pct_b: 0.62 },
  atr: 820, atr_pct: 1.27, ema9: 64650, ema21: 64200, sma20: 64100, sma50: 63500,
  sma200: 61000, obv_trend: "up", volume_ratio: 1.18, as_of: new Date().toISOString(),
};
export const MARKET_REGIME = {
  regime: "strong_uptrend", confidence: 0.78, label: "Alta forte",
  active_strategy: "trend_following", bars_in_regime: 6,
  since: new Date(Date.now() - 6 * 3600e3).toISOString(),
  last_transition: "sideways→strong_uptrend", extreme: false, as_of: new Date().toISOString(),
};
export const MARKET_LEVELS = {
  support: [{ price: 63800, strength: 3 }, { price: 62500, strength: 2 }],
  resistance: [{ price: 65200, strength: 3 }, { price: 66800, strength: 2 }],
  fib: [62000, 63000, 64000, 65000, 66000],
};
export const MARKET_VOLUME_PROFILE = {
  poc: 64100, vah: 65000, val: 63200, lvn: [63500, 64800],
  bins: Array.from({ length: 12 }, (_, i) => ({ price: 62000 + i * 400, volume: 500 + (i % 4) * 300 })),
};
export const MARKET_PATTERNS = [
  { name: "Martelo", direction: "bullish", confidence: 0.7, target: 65500 },
];
// ---- Diário (screen_journal) --------------------------------------------------
export const JOURNAL = [
  { id: 1, date: "2026-07-18", pair: "BTC/USDT", emotion_before: 3, pnl_pct: 1.8,
    plan_followed: true, setup: "Rompimento de resistência", note: "Segui o plano." },
  { id: 2, date: "2026-07-17", pair: "ETH/USDT", emotion_before: 5, pnl_pct: -0.9,
    plan_followed: false, setup: "FOMO", note: "Entrei sem confirmação." },
];
export const JOURNAL_METRICS = {
  by_emotion: [{ emotion: 3, avg_pnl: 1.2 }, { emotion: 5, avg_pnl: -0.6 }],
  plan_followed_pnl: 2.4, plan_deviated_pnl: -1.1, discipline_correlation: 0.62,
  real_win_rate: 0.58,
};

export const MARKET_SIGNAL = {
  action: "buy", entry: 64500, stop: 63200, take_profit: 66800, position_size_pct: 2,
  rr: 1.8, strategy: "trend_following", confidence: 0.76,
  reason: "RSI saindo de sobrevendido + suporte forte confirmado por volume.",
  confidence_factors: [
    { name: "trend", weight: 0.4, score: 0.8, contribution: 0.32, note: "" },
    { name: "momentum", weight: 0.3, score: 0.7, contribution: 0.21, note: "" },
    { name: "volume", weight: 0.3, score: 0.75, contribution: 0.225, note: "" },
  ],
  valid_until: new Date(Date.now() + 3600e3).toISOString(), as_of: new Date().toISOString(),
};

// GET /v1/hitl/config — header autonomy badge + the HITL Controls screen.
export const HITL_CONFIG = {
  level: 1, current_level: 1, threshold_usdt: 100.0, label: "Assistido",
  level_description: "Ordens acima do limite exigem aprovação humana.",
  pending_orders_count: 2, human_approved_today: 5, human_rejected_today: 1,
  levels: [
    { level: 0, threshold_usdt: 0, description: "Manual — toda ordem exige aprovação." },
    { level: 1, threshold_usdt: 100, description: "Assistido — ordens acima do limite exigem aprovação." },
    { level: 2, threshold_usdt: 500, description: "Semi-autônomo — só ordens grandes exigem aprovação." },
    { level: 3, threshold_usdt: 999999, description: "Autônomo — sem aprovação (confirmação extra)." },
  ],
};

// GET /v1/orders — pending queue (HITL) + Orders table. ≥2 pares incl. BTC/USDT
// para os chips de par (N4); confidence (Fix #3) + confidence_breakdown por ordem.
export const ORDERS = [
  { id: "ord_a1", pair: "BTC/USDT", side: "buy", quantity: 0.03, price: 64500, entry: 64500,
    stop_loss: 63200, take_profit: 66800, position_size_pct: 2, confidence: 0.82, status: "pending",
    strategy: "trend_following", agent_id: "strategy_agent", reason: "Rompimento confirmado por volume.",
    created_at: new Date().toISOString(),
    confidence_breakdown: [{ key: "trend", score: 0.85 }, { key: "momentum", score: 0.7 }, { key: "volume", score: 0.8 }] },
  { id: "ord_b2", pair: "ETH/USDT", side: "buy", quantity: 0.5, price: 3200, entry: 3200,
    stop_loss: 3080, take_profit: 3450, position_size_pct: 2, confidence: 0.71, status: "pending",
    strategy: "mean_reversion", agent_id: "strategy_agent", reason: "Reversão no suporte confirmada.",
    created_at: new Date().toISOString(),
    confidence_breakdown: [{ key: "trend", score: 0.6 }, { key: "momentum", score: 0.75 }, { key: "volume", score: 0.8 }] },
];

// GET /v1/trades — trades fechados (P&L realizado por par, N5). ≥2 símbolos incl. BTC/USDT.
export const TRADES = [
  { order_id: "t1", symbol: "BTC/USDT", side: "buy", entry_price: 61200, exit_price: 64810, quantity: 0.03, fee: 0.5, pnl: 108.30, pnl_pct: 5.9 },
  { order_id: "t2", symbol: "BTC/USDT", side: "buy", entry_price: 65000, exit_price: 63600, quantity: 0.03, fee: 0.5, pnl: -42.10, pnl_pct: -2.1 },
  { order_id: "t3", symbol: "ETH/USDT", side: "buy", entry_price: 3100, exit_price: 3223, quantity: 0.5, fee: 0.3, pnl: 61.50, pnl_pct: 4.0 },
  { order_id: "t4", symbol: "SOL/USDT", side: "buy", entry_price: 150, exit_price: 160.3, quantity: 1.2, fee: 0.2, pnl: 12.38, pnl_pct: 1.5 },
  { order_id: "t5", symbol: "SOL/USDT", side: "buy", entry_price: 148, exit_price: 168.7, quantity: 1.2, fee: 0.2, pnl: 24.90, pnl_pct: 3.0 },
  { order_id: "t6", symbol: "XRP/USDT", side: "buy", entry_price: 0.62, exit_price: 0.60, quantity: 400, fee: 0.1, pnl: -8.20, pnl_pct: -1.3 },
];

// GET /v1/users — exatamente 3 (rbac test 3 afirma tbody tr === 3).
export const USERS = [
  { id: "u_demo", name: "Operador Demo", email: "demo@criptotrade.dev", role: "admin", status: "active", last_login_at: new Date().toISOString(), invite_id: null },
  { id: "u_ana", name: "Ana", email: "ana@criptotrade.dev", role: "operador", status: "active", last_login_at: new Date(Date.now() - 86400e3).toISOString(), invite_id: null },
  { id: "u_novo", name: null, email: "novo@criptotrade.dev", role: "visualizador", status: "pending", last_login_at: null, invite_id: "inv_1" },
];

// GET /v1/roles — a "Matriz de permissões" renderiza de r.permissions.
export const ROLES = [
  { id: "admin", label: "Admin", permissions: ["approve_order", "change_autonomy", "change_risk", "edit_settings", "manage_keys", "view_audit", "manage_users"] },
  { id: "operador", label: "Operador", permissions: ["approve_order", "change_autonomy", "view_audit"] },
  { id: "visualizador", label: "Visualizador", permissions: [] },
];

// ---- Notificações (screen_notifications) — SECRETS SEMPRE MASCARADOS ----------
// Espelha data.js:479-497. Nunca um token em claro (o notifications.spec test 1
// afirma que o HTML não contém "AAAbbb" — a guarda de raw-secret é atendida por
// construção: só destination_masked / •••).
export const NOTIF_CHANNELS = [
  { id: "ch1", kind: "telegram", label: "Ops crítico", enabled: true,
    config_masked: { bot_token: "•••4821", chat_id: "-100200300" },
    destination_masked: "chat -100200300 · token •••4821",
    last_test_at: "2026-07-18T09:00:00+00:00", last_test_ok: true, last_error: null },
  { id: "ch2", kind: "email", label: "E-mail do dono", enabled: true,
    config_masked: { to_email: "dono@criptotrade.dev" },
    destination_masked: "dono@criptotrade.dev",
    last_test_at: null, last_test_ok: null, last_error: null },
];
export const NOTIF_RULES = [
  { id: "r1", alert_type: "circuit_breaker", min_severity: "critical",
    channel_ids: ["ch1", "ch2"], pairs: ["*"], enabled: true },
  { id: "r2", alert_type: "*", min_severity: "high",
    channel_ids: ["ch1"], pairs: ["BTC/USDT"], enabled: true },
];
export const NOTIF_SETTINGS = {
  quiet_start: "22:00", quiet_end: "07:00", quiet_tz: "America/Sao_Paulo", group_window_min: 5,
};

// ---- Conexões & Chaves (screen_connections) — SECRETS SEMPRE MASCARADOS -------
// Espelha data.js:500-515. api_key_masked / key_prefix apenas — nunca a chave real.
export const CONNECTIONS = [
  { id: "cx1", exchange_id: "binance", label: "Binance testnet", scope: "trade",
    testnet: true, is_active: true, api_key_masked: "•••b3f1",
    created_at: "2026-07-15T10:00:00+00:00", last_test_at: "2026-07-18T08:30:00+00:00",
    last_test_ok: true, last_test_detail: { read_ok: true, trade_detected: true }, revoked: false },
  { id: "cx2", exchange_id: "binance", label: "Binance leitura", scope: "read",
    testnet: false, is_active: false, api_key_masked: "•••9a2c",
    created_at: "2026-07-10T09:00:00+00:00", last_test_at: "2026-07-17T22:00:00+00:00",
    last_test_ok: false,
    last_test_detail: { read_ok: false, error: "Invalid API-key, IP, or permissions (chave •••9a2c)" },
    revoked: false },
];
export const PLATFORM_KEYS = [
  { id: "pk1", label: "grafana-readonly", key_prefix: "ctk_a1b2c3d4", scope: "visualizador",
    created_at: "2026-07-12T14:00:00+00:00", last_used_at: "2026-07-18T09:45:00+00:00", revoked: false },
];
export const EGRESS_IP = { ip: "203.0.113.42" };

// ---- Conta (screen_account) ---------------------------------------------------
export const ACCOUNT_PROFILE = {
  email: "demo@criptotrade.dev", name: "Operador Demo", job_title: "Operador", avatar_color: "ink", role: "admin",
};
export const PREFERENCES = {
  locale: "pt-BR", timezone: "America/Sao_Paulo", number_locale: "auto", date_locale: "auto",
};

// ---- Segurança (screen_security) — espelha data.js; UAs parseáveis pela heurística
export const SECURITY_SESSIONS = [
  { id: "s1", created_at: "2026-07-18T08:00:00+00:00", last_seen_at: "2026-07-18T09:30:00+00:00",
    ip: "187.20.14.2", user_agent: "Mozilla/5.0 (X11; Linux x86_64) Chrome/126.0", remember: false, current: true },
  { id: "s2", created_at: "2026-07-16T21:10:00+00:00", last_seen_at: "2026-07-17T07:45:00+00:00",
    ip: "177.94.3.71", user_agent: "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5) Safari/604.1", remember: true, current: false },
];
// getLoginHistory usa unwrap:false → a tela lê l.data; o envelope do fixture já é {data:[…]}.
export const SECURITY_LOGINS = [
  { id: 93, ts: "2026-07-18T08:00:00+00:00", action: "login", actor: "demo@criptotrade.dev", ip: "187.20.14.2", ua: "Mozilla/5.0 (X11; Linux x86_64) Chrome/126.0", success: true },
  { id: 90, ts: "2026-07-17T23:41:00+00:00", action: "login", actor: "demo@criptotrade.dev", ip: "45.12.9.30", ua: "Mozilla/5.0 (Windows NT 10.0) Firefox/128.0", success: false },
  { id: 88, ts: "2026-07-16T21:10:00+00:00", action: "login", actor: "demo@criptotrade.dev", ip: "177.94.3.71", ua: "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5) Safari/604.1", success: true },
];

// ---- Auditoria (screen_audit) — 8 eventos; id 7 (config_changed) tem before→after
export const AUDIT_EVENTS = [
  { id: 8, ts: "2026-07-18T09:12:00+00:00", action: "login", actor: "demo@criptotrade.dev", entity: "demo@criptotrade.dev", ip: "187.20.14.2", ua: "Chrome/Linux", success: true, before: null, after: null, detail: null },
  { id: 7, ts: "2026-07-18T08:55:00+00:00", action: "config_changed", actor: "demo@criptotrade.dev", entity: "risk", ip: null, ua: null, success: null,
    before: { max_daily_loss_pct: 5.0 }, after: { max_daily_loss_pct: 4.0 }, detail: null,
    data: { actor: "demo@criptotrade.dev", scope: "risk", before: { max_daily_loss_pct: 5.0 }, after: { max_daily_loss_pct: 4.0 } } },
  { id: 6, ts: "2026-07-18T08:40:00+00:00", action: "autonomy_changed", actor: "ana@criptotrade.dev", entity: null, ip: null, ua: null, success: null, before: { level: 1 }, after: { level: 2 }, detail: "Mercado estável, subindo autonomia" },
  { id: 5, ts: "2026-07-18T08:10:00+00:00", action: "order_approved", actor: "ana@criptotrade.dev", entity: "BTC/USDT", ip: null, ua: null, success: null, before: null, after: null, detail: null },
  { id: 4, ts: "2026-07-17T22:05:00+00:00", action: "order_rejected", actor: "ana@criptotrade.dev", entity: "ETH/USDT", ip: null, ua: null, success: null, before: null, after: null, detail: null },
  { id: 3, ts: "2026-07-17T21:00:00+00:00", action: "position_closed", actor: "orchestrator", entity: "BTC/USDT", ip: null, ua: null, success: null, before: null, after: null, detail: "P&L +12.40 USDT" },
  { id: 2, ts: "2026-07-17T20:30:00+00:00", action: "user_management", actor: "demo@criptotrade.dev", entity: "novo@criptotrade.dev", ip: null, ua: null, success: true, before: null, after: null, detail: "novo@criptotrade.dev as visualizador" },
  { id: 1, ts: "2026-07-17T19:00:00+00:00", action: "circuit_breaker", actor: "orchestrator", entity: null, ip: null, ua: null, success: null, before: null, after: null, detail: "3 perdas consecutivas" },
];
// GET /v1/audit — filtra por action (mesma semântica do SQL do backend); envelope
// {data:[…]} → a tela usa env.data e cai no fallback env.data.length para o total.
export function auditList(reqUrl) {
  const action = new URL(reqUrl).searchParams.get("action");
  return action ? AUDIT_EVENTS.filter((e) => e.action === action) : AUDIT_EVENTS;
}
export function auditEvent(id) {
  return AUDIT_EVENTS.find((e) => e.id === Number(id)) || null;
}

// POST /v1/api-keys — a chave em claro é mostrada UMA vez na criação (canned).
// A chave é montada por template (sem literal de alta entropia no source) para não
// disparar o gitleaks generic-api-key — é valor de teste fake, nunca um secret real.
export function createdPlatformKey(label) {
  const name = label || "nova-chave";
  return { id: "pk_new", label: name, key: `ctk_${name}_fake_demo`, scope: "visualizador" };
}

// GET /v1/market/{pair}/ticker — the header price (when a single pair is selected).
export function ticker(pair) {
  return { pair, last: 64810.0, change_24h_pct: 2.34, as_of: new Date().toISOString() };
}
