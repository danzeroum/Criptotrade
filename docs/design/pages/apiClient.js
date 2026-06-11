/* ============================================================
   Criptotrade — API client
   Single data bridge between the UI and the FastAPI backend.
   Unwraps APIResponse<T> envelopes automatically.

   Configuration (set before this script loads):
     window.API_BASE = 'http://localhost:8000'  (default)
     window.API_KEY  = 'your-key'               (optional)
     window.USE_MOCK_DATA = true                (fallback to CT.*)
   ============================================================ */
const CT_API = (() => {
  const base = window.API_BASE ?? 'http://localhost:8000';
  const getKey = () => window.API_KEY ?? '';

  async function req(path, opts = {}) {
    const method = (opts.method ?? 'GET').toUpperCase();
    const headers = {};
    if (method !== 'GET' && method !== 'HEAD') headers['Content-Type'] = 'application/json';
    const k = getKey();
    if (k) headers['X-API-Key'] = k;
    const r = await fetch(base + path, { headers, ...opts });
    if (!r.ok) {
      const e = await r.json().catch(() => ({ error: 'network_error', message: r.statusText }));
      throw e;
    }
    const j = await r.json();
    return j.data ?? j;
  }

  return {
    // ---- Phase 0: ready endpoints ----
    getHealth:        ()           => req('/health'),
    getMetrics:       (p = '7d')   => req(`/v1/metrics?period=${p}`),
    getHITL:          ()           => req('/v1/hitl/config'),
    patchHITL:        (body)       => req('/v1/hitl/config', { method: 'PATCH', body: JSON.stringify(body) }),
    getOrders:        (limit = 50, offset = 0, q = '') =>
      req(`/v1/orders?limit=${limit}&offset=${offset}${q}`),
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
    getCandles:       (pair, tf = '1h', limit = 100) =>
      req(`/v1/market/${pair.replace('/', '-')}/candles?tf=${tf}&limit=${limit}`),
    getIndicators:    (pair) => req(`/v1/market/${pair.replace('/', '-')}/indicators`),
    getRegime:        (pair) => req(`/v1/market/${pair.replace('/', '-')}/regime`),
    getLevels:        (pair) => req(`/v1/market/${pair.replace('/', '-')}/levels`),
    getVolumeProfile: (pair) => req(`/v1/market/${pair.replace('/', '-')}/volume-profile`),
    getPatterns:      (pair) => req(`/v1/market/${pair.replace('/', '-')}/patterns`),
    getSignal:        (pair) => req(`/v1/market/${pair.replace('/', '-')}/signal`),

    // ---- Phase 2: risk ----
    getProtections:    ()     => req('/v1/risk/protections'),
    getCircuitBreaker: ()     => req('/v1/risk/circuit-breaker'),
    getKelly:          ()     => req('/v1/risk/kelly'),
    getRiskConfig:     ()     => req('/v1/risk/config'),
    patchRiskConfig:   (body) => req('/v1/risk/config', { method: 'PATCH', body: JSON.stringify(body) }),
    getEquity:         (p = '90d') => req(`/v1/metrics/equity?period=${p}`),

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
  };
})();

window.CT_API = CT_API;
