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

// GET /v1/metrics — Visão Geral KPIs. has_data:false → the honest "no trades yet"
// empty state (the overview mounts briefly before the Mesa-landing redirect).
export function metrics() {
  return { has_data: false, calculated_at: new Date().toISOString() };
}

// GET /v1/metrics/equity — the overview equity curve (empty = no history yet).
export const EQUITY = [];

// GET /v1/hitl/config — the header's autonomy badge.
export const HITL_CONFIG = { level: 1, threshold_usdt: 100.0, label: "Assistido" };

// GET /v1/market/{pair}/ticker — the header price (when a single pair is selected).
export function ticker(pair) {
  return { pair, last: 64810.0, change_24h_pct: 2.34, as_of: new Date().toISOString() };
}
