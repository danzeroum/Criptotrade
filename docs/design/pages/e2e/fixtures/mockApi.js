// Fail-loud e2e API fixture (mock-cleanup plan, condition #1).
//
// installMockApi(page, scenario) intercepts every API request with page.route and
// serves canned responses from ./datasets.js. Any endpoint that is NOT explicitly
// stubbed FAILS THE TEST with a clear message ("endpoint não stubado: GET /v1/xyz")
// instead of silently hitting the network or an old in-app mock branch — the drift
// detector that keeps a migrated spec honest as the strangler migration removes
// production mock branches slice by slice.
//
// This is the substrate the whole mock-cleanup program builds on: production code
// always calls the real apiClient; e2e supplies data purely via interception, so
// no mock branch ever ships in production.

import {
  AGENTS, authMe, candles, deskSummary, EQUITY, HEALTH, HITL_CONFIG, MARKET_INDICATORS,
  JOURNAL, JOURNAL_METRICS, MARKET_LEVELS, MARKET_PATTERNS, MARKET_REGIME, MARKET_SIGNAL,
  MARKET_VOLUME_PROFILE,
  metrics, ONBOARDING, PAIRS_FLAT, PAIRS_RICH, processEvents, RISK_CIRCUIT_BREAKER,
  RISK_CONFIG, RISK_KELLY, RISK_PROTECTIONS, RISK_SKIPS, RISK_SLOTS, SYS_CONFIG, ticker,
} from "./datasets.js";

// Wrap a payload in the API envelope the client's req() unwraps ({ data, meta }).
function envelope(payload) {
  return JSON.stringify({ data: payload });
}
function fulfillJson(route, payload) {
  return route.fulfill({ status: 200, contentType: "application/json", body: envelope(payload) });
}

// Exact "METHOD /path" stubs every authenticated boot touches (probe + landing).
// Per-test `routes` override or extend this. Values are payloads or (req,url)=>payload.
// Note: /v1/pairs and its POST/PATCH/DELETE mutations are handled statefully in the
// route handler (see installMockApi), not here.
function baseline({ authMode, role }) {
  return {
    "GET /health": () => HEALTH,
    "GET /v1/auth/me": () => authMe({ authMode, role }),
    "GET /v1/market/pairs": () => PAIRS_FLAT,
    "GET /v1/hitl/config": () => HITL_CONFIG,
    "GET /v1/metrics": () => metrics(),
    "GET /v1/metrics/equity": () => EQUITY,
    "GET /v1/onboarding/status": () => ONBOARDING,
    "GET /v1/desk/summary": () => deskSummary(),
    "GET /v1/orders": () => [], // sidebar pending-count poll → empty
    // Risco (screen_risk)
    "GET /v1/risk/protections": () => RISK_PROTECTIONS,
    "GET /v1/risk/circuit-breaker": () => RISK_CIRCUIT_BREAKER,
    "GET /v1/risk/kelly": () => RISK_KELLY,
    "GET /v1/risk/slots": () => RISK_SLOTS,
    "GET /v1/process/skips": () => RISK_SKIPS,
    // Observabilidade (screen_observability)
    "GET /v1/process/events": () => processEvents(),
    // Config (screen_settings)
    "GET /v1/config": () => SYS_CONFIG,
    "GET /v1/risk/config": () => RISK_CONFIG,
    "GET /v1/agents": () => AGENTS,
    // Diário (screen_journal)
    "GET /v1/journal": () => JOURNAL,
    "GET /v1/journal/metrics": () => JOURNAL_METRICS,
  };
}

// Parameterized paths (pair in the path). Checked after exact keys.
const PATTERNS = [
  { re: /^GET \/v1\/market\/([^/]+)\/ticker$/, payload: (m) => ticker(m[1].replace("-", "/")) },
  { re: /^GET \/v1\/market\/([^/]+)\/candles/, payload: (m) => candles(m[1].replace("-", "/")) },
  { re: /^GET \/v1\/market\/[^/]+\/indicators$/, payload: () => MARKET_INDICATORS },
  { re: /^GET \/v1\/market\/[^/]+\/regime$/, payload: () => MARKET_REGIME },
  { re: /^GET \/v1\/market\/[^/]+\/levels$/, payload: () => MARKET_LEVELS },
  { re: /^GET \/v1\/market\/[^/]+\/volume-profile$/, payload: () => MARKET_VOLUME_PROFILE },
  { re: /^GET \/v1\/market\/[^/]+\/patterns$/, payload: () => MARKET_PATTERNS },
  { re: /^GET \/v1\/market\/[^/]+\/signal$/, payload: () => MARKET_SIGNAL },
  { re: /^GET \/v1\/market\/[^/]+\/confluence$/, payload: () => null },
];

// EventSource endpoints — fulfilled as a short text/event-stream so the client
// connects cleanly (it reconnects on its own retry interval; each hit is stubbed).
const SSE_PATHS = new Set(["/v1/alerts"]);

/**
 * Install the fail-loud mock API on a Playwright page.
 * @param {import('@playwright/test').Page} page
 * @param {{authMode?: 'none'|'demo'|'user', role?: string, routes?: object}} scenario
 * @returns {{ unstubbed: string[] }} handle exposing any unstubbed endpoints hit
 */
export async function installMockApi(page, scenario = {}) {
  const { authMode = "user", role = "admin", routes = {} } = scenario;
  const table = { ...baseline({ authMode, role }), ...routes };
  const unstubbed = [];
  // Stateful operated pairs (N8²/N9): POST/PATCH/DELETE mutate; GET /v1/pairs reflects.
  // Seeded fresh per test from PAIRS_RICH (BNB starts paused).
  const operated = PAIRS_RICH.operados.map((o) => ({ ...o }));
  const decode = (seg) => decodeURIComponent(seg).replace("-", "/");

  await page.route("**/api/**", async (route) => {
    const req = route.request();
    const method = req.method();
    const url = new URL(req.url());
    // Strip the API base prefix so keys are stable ("GET /v1/..." / "GET /health").
    const path = url.pathname.replace(/^\/api/, "");
    const key = `${method} ${path}`;

    // --- stateful operated pairs -------------------------------------------
    if (path === "/v1/pairs" && method === "GET") {
      return fulfillJson(route, { operados: operated, observaveis: PAIRS_RICH.observaveis });
    }
    if (path === "/v1/pairs/operated" && method === "POST") {
      const sym = (req.postDataJSON() || {}).symbol;
      const row = { symbol: sym, last_cycle_at: null, status: "aguardando", paused: false };
      operated.push(row);
      return fulfillJson(route, row);
    }
    const opMatch = path.match(/^\/v1\/pairs\/operated\/(.+)$/);
    if (opMatch && method === "PATCH") {
      const row = operated.find((o) => o.symbol === decode(opMatch[1]));
      if (row) row.paused = !!(req.postDataJSON() || {}).paused;
      return fulfillJson(route, row || {});
    }
    if (opMatch && method === "DELETE") {
      const i = operated.findIndex((o) => o.symbol === decode(opMatch[1]));
      if (i >= 0) operated.splice(i, 1);
      return fulfillJson(route, { removed: decode(opMatch[1]) });
    }

    if (SSE_PATHS.has(path)) {
      await route.fulfill({
        status: 200, contentType: "text/event-stream", body: ": connected\n\n",
      });
      return;
    }

    let entry = table[key];
    if (entry === undefined) {
      for (const p of PATTERNS) {
        const m = key.match(p.re);
        if (m) { entry = () => p.payload(m); break; }
      }
    }
    if (entry === undefined) {
      unstubbed.push(key);
      await route.abort("failed");
      // Fail loud: surface as a route-handler error so the test cannot pass by
      // silently falling through to the network or a stale mock branch.
      throw new Error(
        `[mockApi] endpoint não stubado: ${key} — adicione um stub em fixtures ` +
        `ou passe { routes: { '${key}': <payload> } } ao installMockApi.`,
      );
    }
    const payload = typeof entry === "function" ? entry(req, url) : entry;
    await route.fulfill({
      status: 200, contentType: "application/json", body: envelope(payload),
    });
  });

  return { unstubbed };
}
