/* ============================================================
   Criptotrade — API client
   Single data bridge between the UI and the FastAPI backend.
   Unwraps APIResponse<T> envelopes automatically.

   Configuration (set before this script loads):
     window.API_BASE = 'http://localhost:8000'  (default)
     window.API_KEY  = 'your-key'               (optional)
     window.USE_MOCK_DATA = true                (fallback to CT.*)

   Request/response shapes are generated from the API's OpenAPI schema into
   ./openapi.d.ts (`npm run gen:types`). CI fails if either drifts (P3-4).
   ============================================================ */
const CT_API = (() => {
  // Same-origin by design in production (index.html sets window.API_BASE = "").
  // Defensive guard: on an HTTPS page, ignore any http:// base (e.g. a stale
  // deploy leaking the internal 'http://criptotrade-app:8000') — the browser
  // would block it as Mixed Content — and fall back to same-origin. Local dev
  // over HTTP keeps the http://localhost:8000 default untouched.
  const configuredBase = window.API_BASE ?? 'http://localhost:8000';
  const insecureOnHttps =
    window.location.protocol === 'https:' && /^http:\/\//i.test(configuredBase);
  if (insecureOnHttps) {
    console.warn('Ignoring insecure API_BASE on HTTPS; using same-origin API.');
  }
  const base = insecureOnHttps ? '' : configuredBase;
  const getKey = () => window.API_KEY ?? '';

  async function rawReq(path, opts = {}) {
    const method = (opts.method ?? 'GET').toUpperCase();
    const headers = {};
    if (method !== 'GET' && method !== 'HEAD') headers['Content-Type'] = 'application/json';
    const k = getKey();
    if (k) headers['X-API-Key'] = k;
    // credentials: session cookies (A1) ride along on the same-origin /api base.
    return fetch(base + path, { headers, credentials: 'include', ...opts });
  }

  async function req(path, opts = {}, { unwrap = true } = {}) {
    let r = await rawReq(path, opts);
    // Expired session: try one silent refresh, then retry the original call.
    // On a dead refresh, tell the app (lock screen) — never hard-redirect.
    if (r.status === 401 && !path.startsWith('/v1/auth/')) {
      const refreshed = await rawReq('/v1/auth/refresh', { method: 'POST' })
        .then(x => x.ok).catch(() => false);
      if (refreshed) {
        r = await rawReq(path, opts);
      } else if (window.CT_AUTH?.state()?.authenticated) {
        window.dispatchEvent(new CustomEvent('ct:auth-expired'));
      }
    }
    if (!r.ok) {
      const e = await r.json().catch(() => ({ error: 'network_error', message: r.statusText }));
      e.status = r.status;  // screens branch 403 (forbidden) vs generic errors
      throw e;
    }
    const j = await r.json();
    // unwrap:false keeps the {data, meta} envelope (pagination needs meta.total).
    return unwrap ? (j.data ?? j) : j;
  }

  // Query-string builder that drops empty values (audit filters are optional).
  const qs = (params) => {
    const pairs = Object.entries(params).filter(([, v]) => v !== '' && v != null);
    return pairs.length ? '?' + new URLSearchParams(pairs).toString() : '';
  };

  return {
    // ---- Phase 0: ready endpoints ----
    getHealth:        ()           => req('/health'),
    getMetrics:       (p = '7d', symbol) =>
      req(`/v1/metrics?period=${p}${symbol && symbol !== 'ALL' ? `&symbol=${encodeURIComponent(symbol)}` : ''}`),
    getHITL:          ()           => req('/v1/hitl/config'),
    patchHITL:        (body)       => req('/v1/hitl/config', { method: 'PATCH', body: JSON.stringify(body) }),
    getOrders:        (limit = 50, offset = 0, q = '') =>
      req(`/v1/orders?limit=${limit}&offset=${offset}${q}`),
    createOrder:      (body)       => req('/v1/orders', { method: 'POST', body: JSON.stringify(body) }),
    decideOrder:      (id, body)   => req(`/v1/orders/${id}/status`, { method: 'PATCH', body: JSON.stringify(body) }),
    getAgents:        ()           => req('/v1/agents'),
    getAgentConfig:   (id)         => req(`/v1/agents/${id}/config`),
    getAlertHistory:  (n = 50)     => req(`/v1/alerts/history?limit=${n}`),
    subscribeAlerts:  (onAlert, onError) => {
      const es = new EventSource(base + '/v1/alerts');
      es.addEventListener('alert', e => {
        try { onAlert(JSON.parse(e.data)); } catch (_) { /* ignore malformed */ }
      });
      es.onerror = onError ?? (() => {});
      return es;
    },

    // ---- Phase 1: market ----
    getPairs:         ()           => req('/v1/market/pairs'),
    getTicker:        (pair)       => req(`/v1/market/${pair.replace('/', '-')}/ticker`),
    getCandles:       (pair, tf = '1h', limit = 100) =>
      req(`/v1/market/${pair.replace('/', '-')}/candles?tf=${tf}&limit=${limit}`),
    getIndicators:    (pair) => req(`/v1/market/${pair.replace('/', '-')}/indicators`),
    getRegime:        (pair) => req(`/v1/market/${pair.replace('/', '-')}/regime`),
    getLevels:        (pair) => req(`/v1/market/${pair.replace('/', '-')}/levels`),
    getVolumeProfile: (pair) => req(`/v1/market/${pair.replace('/', '-')}/volume-profile`),
    getPatterns:      (pair) => req(`/v1/market/${pair.replace('/', '-')}/patterns`),
    getSignal:        (pair) => req(`/v1/market/${pair.replace('/', '-')}/signal`),
    getConfluence:    (pair) => req(`/v1/market/${pair.replace('/', '-')}/confluence`),

    // ---- Phase 2: risk ----
    getProtections:    ()     => req('/v1/risk/protections'),
    getCircuitBreaker: ()     => req('/v1/risk/circuit-breaker'),
    getKelly:          ()     => req('/v1/risk/kelly'),
    getRiskConfig:     ()     => req('/v1/risk/config'),
    patchRiskConfig:   (body) => req('/v1/risk/config', { method: 'PATCH', body: JSON.stringify(body) }),
    getEquity:         (p = '90d', symbol) =>
      req(`/v1/metrics/equity?period=${p}${symbol && symbol !== 'ALL' ? `&symbol=${encodeURIComponent(symbol)}` : ''}`),
    getProcessEvents:  (limit = 200) => req(`/v1/process/events?limit=${limit}`),

    // ---- Phase 3: backtest ----
    runBacktest:      (body) => req('/v1/backtest/run', { method: 'POST', body: JSON.stringify(body) }),
    runMonteCarlo:    (body) => req('/v1/backtest/montecarlo', { method: 'POST', body: JSON.stringify(body) }),
    runWalkForward:   (body) => req('/v1/backtest/walkforward', { method: 'POST', body: JSON.stringify(body) }),
    getBacktestJob:   (id)   => req(`/v1/backtest/jobs/${id}`),

    // ---- Phase 4: journal ----
    getJournal:       ()     => req('/v1/journal'),
    addJournalEntry:  (body) => req('/v1/journal', { method: 'POST', body: JSON.stringify(body) }),
    getJournalMetrics: ()    => req('/v1/journal/metrics'),

    // ---- Phase 5: config ----
    getConfig:        ()         => req('/v1/config'),
    patchConfig:      (body)     => req('/v1/config', { method: 'PATCH', body: JSON.stringify(body) }),
    patchAgentConfig: (id, body) => req(`/v1/agents/${id}/config`, { method: 'PATCH', body: JSON.stringify(body) }),
    patchAlertsConfig:(body)     => req('/v1/alerts/config', { method: 'PATCH', body: JSON.stringify(body) }),

    // ---- A3: users & roles ----
    getUsers:         ()         => req('/v1/users'),
    inviteUser:       (body)     => req('/v1/users/invite', { method: 'POST', body: JSON.stringify(body) }),
    resendInvite:     (id)       => req(`/v1/users/invites/${id}/resend`, { method: 'POST', body: '{}' }),
    revokeInvite:     (id)       => req(`/v1/users/invites/${id}`, { method: 'DELETE' }),
    patchUserRole:    (id, role) => req(`/v1/users/${id}/role`, { method: 'PATCH', body: JSON.stringify({ role }) }),
    patchUserStatus:  (id, status) => req(`/v1/users/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status }) }),
    deleteUser:       (id)       => req(`/v1/users/${id}`, { method: 'DELETE' }),
    getRoles:         ()         => req('/v1/roles'),
    acceptInvite:     (body)     => req('/v1/auth/invite/accept', { method: 'POST', body: JSON.stringify(body) }),

    // ---- A4: audit trail ----
    // Returns the FULL envelope ({data, meta}) — the screen paginates on meta.total.
    getAudit:         (params = {}) => req(`/v1/audit${qs(params)}`, {}, { unwrap: false }),
    getAuditEvent:    (id)          => req(`/v1/audit/${id}`),
    exportAudit:      async (format = 'csv', params = {}) => {
      const r = await rawReq(`/v1/audit/export${qs({ format, ...params })}`);
      if (!r.ok) {
        const e = await r.json().catch(() => ({ message: r.statusText }));
        e.status = r.status;
        throw e;
      }
      return r.blob();
    },

    // ---- A2: account & preferences (self-service) ----
    getAccountProfile:  ()       => req('/v1/account/profile'),
    patchAccountProfile:(body)   => req('/v1/account/profile', { method: 'PATCH', body: JSON.stringify(body) }),
    changePassword:     (body)   => req('/v1/account/password', { method: 'PATCH', body: JSON.stringify(body) }),
    getPreferences:     ()       => req('/v1/account/preferences'),
    patchPreferences:   (body)   => req('/v1/account/preferences', { method: 'PATCH', body: JSON.stringify(body) }),

    // ---- A7: security & sessions (self-service) ----
    getSessions:          ()         => req('/v1/security/sessions'),
    revokeSession:        (id)       => req(`/v1/security/sessions/${id}`, { method: 'DELETE' }),
    revokeOtherSessions:  ()         => req('/v1/security/sessions/revoke-others', { method: 'POST', body: '{}' }),
    getLoginHistory:      (limit = 20) =>
      req(`/v1/security/logins?limit=${limit}`, {}, { unwrap: false }),
    regenerateBackupCodes:(password) =>
      req('/v1/auth/2fa/backup/regenerate', { method: 'POST', body: JSON.stringify({ password }) }),

    // ---- A1: authentication ----
    getMe:            ()         => req('/v1/auth/me'),
    login:            (body)     => req('/v1/auth/login', { method: 'POST', body: JSON.stringify(body) }),
    verify2FA:        (body)     => req('/v1/auth/2fa/verify', { method: 'POST', body: JSON.stringify(body) }),
    logout:           ()         => req('/v1/auth/logout', { method: 'POST', body: '{}' }),
    forgotPassword:   (email)    => req('/v1/auth/password/forgot', { method: 'POST', body: JSON.stringify({ email }) }),
    resetPassword:    (body)     => req('/v1/auth/password/reset', { method: 'POST', body: JSON.stringify(body) }),
    setup2FA:         ()         => req('/v1/auth/2fa/setup', { method: 'POST', body: '{}' }),
    enable2FA:        (code)     => req('/v1/auth/2fa/enable', { method: 'POST', body: JSON.stringify({ code }) }),
    disable2FA:       (password) => req('/v1/auth/2fa/disable', { method: 'POST', body: JSON.stringify({ password }) }),
  };
})();

window.CT_API = CT_API;

/* ============================================================
   Global selected-pair store — shared between the header and the
   Market screen. Classic-scripts app => lives on window. Persists to
   localStorage and notifies subscribers via a 'ct:pair' CustomEvent.
   ============================================================ */
const CT_PAIR = (() => {
  const KEY = 'ct.pair';
  let current = (() => {
    try { return localStorage.getItem(KEY) || 'BTC/USDT'; } catch (_) { return 'BTC/USDT'; }
  })();
  return {
    get: () => current,
    set: (pair) => {
      if (!pair || pair === current) return;
      current = pair;
      try { localStorage.setItem(KEY, pair); } catch (_) { /* private mode: ignore */ }
      window.dispatchEvent(new CustomEvent('ct:pair', { detail: pair }));
    },
    /** Subscribe to changes; returns an unsubscribe fn. */
    subscribe: (fn) => {
      const handler = (e) => fn(e.detail);
      window.addEventListener('ct:pair', handler);
      return () => window.removeEventListener('ct:pair', handler);
    },
  };
})();
window.CT_PAIR = CT_PAIR;

/* ============================================================
   Global preferences store (A2). Mirrors CT_PAIR's pattern.
   Feeds the CENTRAL formatting helpers (fmtNum/fmtUsd/fmtDateTime…)
   so changing locale/timezone/format reflects across the whole
   console — never per-screen (C7 discipline). Defaults preserve
   today's behavior bit-for-bit: numbers en-US (M7), dates pt-BR,
   browser timezone. Populated from /v1/auth/me by CT_AUTH.
   ============================================================ */
const CT_PREFS = (() => {
  const DEFAULTS = { locale: 'pt-BR', timezone: 'auto', number_locale: 'auto', date_locale: 'auto' };
  let current = { ...DEFAULTS, ...(window.MOCK_PREFS ?? {}) };
  const emit = () => window.dispatchEvent(new CustomEvent('ct:prefs', { detail: current }));
  return {
    get: () => current,
    /** Locale for numbers: 'auto' keeps the M7 canonical en-US. */
    numberLocale: () => (current.number_locale === 'auto' ? 'en' : current.number_locale),
    /** Locale for dates: 'auto' keeps today's pt-BR. */
    dateLocale: () => (current.date_locale === 'auto' ? 'pt-BR' : current.date_locale),
    /** IANA timezone or null for the browser's own ('auto'). */
    timezone: () => (current.timezone === 'auto' ? null : current.timezone),
    apply: (prefs) => {
      current = { ...DEFAULTS, ...(prefs ?? {}) };
      emit();
      return current;
    },
    subscribe: (fn) => {
      const handler = (e) => fn(e.detail);
      window.addEventListener('ct:prefs', handler);
      return () => window.removeEventListener('ct:prefs', handler);
    },
  };
})();
window.CT_PREFS = CT_PREFS;

/* ============================================================
   Global auth/session store (A1). Mirrors CT_PAIR's pattern.
   kind: 'off' (auth disabled — no auth UI), 'user' (real session),
   'demo' (public demo, read-only), 'anonymous' (must log in).
   Mock branch (e2e): window.MOCK_AUTH='none' boots unauthenticated;
   anything else auto-authenticates as CT.currentUser (role via MOCK_ROLE).
   ============================================================ */
const CT_AUTH = (() => {
  let current = {
    loaded: false, mode: 'off', kind: 'off',
    authenticated: false, user: null, permissions: [],
  };
  const emit = () => window.dispatchEvent(new CustomEvent('ct:auth', { detail: current }));

  const fromMe = (me) => {
    // A2: the boot probe carries the user's preferences — hydrate the global
    // formatting store here so no screen needs an extra request.
    if (me.prefs) CT_PREFS.apply(me.prefs);
    const authenticated = !!(me.authenticated && me.user);
    let kind = 'anonymous';
    if (me.mode === 'off') kind = 'off';
    else if (authenticated) kind = 'user';
    else if (me.mode === 'demo') kind = 'demo';
    return {
      loaded: true, mode: me.mode, kind,
      authenticated, user: me.user ?? null,
      permissions: me.permissions ?? [],
    };
  };

  // Mirror of the backend matrix (src/auth/rbac.py) for mock/e2e mode only —
  // in live mode permissions ALWAYS come from /v1/auth/me.
  const MOCK_MATRIX = {
    visualizador: [],
    operador: ['approve_order', 'change_autonomy', 'view_audit'],
    admin: ['approve_order', 'change_autonomy', 'change_risk', 'edit_settings',
            'manage_keys', 'view_audit', 'manage_users'],
  };

  return {
    state: () => current,
    kind: () => current.kind,
    /** RBAC gate (A3): 'off' = auth disabled (no gating), user = matrix,
        demo/anonymous hold nothing (demo renders disabled+tooltip instead). */
    can: (perm) => {
      if (current.kind === 'off') return true;
      if (current.kind === 'user') return current.permissions.includes(perm);
      return false;
    },
    load: async () => {
      if (window.USE_MOCK_DATA) {
        const none = window.MOCK_AUTH === 'none';
        const role = window.MOCK_ROLE ?? window.CT?.currentUser?.role ?? 'admin';
        current = none
          ? { loaded: true, mode: 'required', kind: 'anonymous',
              authenticated: false, user: null, permissions: [] }
          : { loaded: true, mode: 'mock',
              kind: window.MOCK_AUTH === 'demo' ? 'demo' : 'user',
              authenticated: window.MOCK_AUTH !== 'demo',
              user: { ...(window.CT?.currentUser ?? { name: 'Demo', email: 'demo@dev' }), role },
              permissions: window.MOCK_AUTH === 'demo' ? [] : (MOCK_MATRIX[role] ?? []) };
      } else {
        try {
          current = fromMe(await CT_API.getMe());
        } catch (_) {
          current = { loaded: true, mode: 'unreachable', kind: 'off',
                      authenticated: false, user: null, permissions: [] };
        }
      }
      emit();
      return current;
    },
    apply: (me) => { current = fromMe(me); emit(); return current; },
    logout: async () => {
      try { await CT_API.logout(); } catch (_) { /* cookie may be gone already */ }
      current = { ...current, kind: current.mode === 'demo' ? 'demo' : 'anonymous',
                  authenticated: false, user: null, permissions: [] };
      emit();
    },
    subscribe: (fn) => {
      const handler = (e) => fn(e.detail);
      window.addEventListener('ct:auth', handler);
      return () => window.removeEventListener('ct:auth', handler);
    },
  };
})();
window.CT_AUTH = CT_AUTH;
