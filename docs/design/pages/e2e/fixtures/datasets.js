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

// GET /v1/hitl/config — the header's autonomy badge.
export const HITL_CONFIG = { level: 1, threshold_usdt: 100.0, label: "Assistido" };

// GET /v1/market/{pair}/ticker — the header price (when a single pair is selected).
export function ticker(pair) {
  return { pair, last: 64810.0, change_24h_pct: 2.34, as_of: new Date().toISOString() };
}
