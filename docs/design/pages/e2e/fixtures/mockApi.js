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
  authMe, deskSummary, EQUITY, HEALTH, HITL_CONFIG, metrics, ONBOARDING, PAIRS_FLAT,
  PAIRS_RICH, ticker,
} from "./datasets.js";

// Wrap a payload in the API envelope the client's req() unwraps ({ data, meta }).
function envelope(payload) {
  return JSON.stringify({ data: payload });
}

// Exact "METHOD /path" stubs every authenticated boot touches (probe + landing).
// Per-test `routes` override or extend this. Values are payloads or (req,url)=>payload.
function baseline({ authMode, role }) {
  return {
    "GET /health": () => HEALTH,
    "GET /v1/auth/me": () => authMe({ authMode, role }),
    "GET /v1/pairs": () => PAIRS_RICH,
    "GET /v1/market/pairs": () => PAIRS_FLAT,
    "GET /v1/hitl/config": () => HITL_CONFIG,
    "GET /v1/metrics": () => metrics(),
    "GET /v1/metrics/equity": () => EQUITY,
    "GET /v1/onboarding/status": () => ONBOARDING,
    "GET /v1/desk/summary": () => deskSummary(),
    "GET /v1/orders": () => [], // sidebar pending-count poll → empty
  };
}

// Parameterized paths (pair in the path). Checked after exact keys.
const PATTERNS = [
  { re: /^GET \/v1\/market\/([^/]+)\/ticker$/,
    payload: (m) => ticker(m[1].replace("-", "/")) },
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

  await page.route("**/api/**", async (route) => {
    const req = route.request();
    const method = req.method();
    const url = new URL(req.url());
    // Strip the API base prefix so keys are stable ("GET /v1/..." / "GET /health").
    const path = url.pathname.replace(/^\/api/, "");
    const key = `${method} ${path}`;

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
