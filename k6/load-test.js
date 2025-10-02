import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

const errorRate = new Rate('errors');

export const options = {
  stages: [
    { duration: '30s', target: 10 },
    { duration: '1m', target: 10 },
    { duration: '30s', target: 20 },
    { duration: '1m', target: 20 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<800'],
    http_req_failed: ['rate<0.01'],
    errors: ['rate<0.01'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8080';

export default function () {
  let healthRes = http.get(`${BASE_URL}/actuator/health`);
  check(healthRes, {
    'health check OK': (r) => r.status === 200,
    'health response time < 100ms': (r) => r.timings.duration < 100,
  });

  let apiRes = http.get(`${BASE_URL}/api/v1/resources`, {
    headers: {
      'Accept': 'application/json',
      'X-Trace-Id': `k6-${__VU}-${__ITER}`,
    },
  });

  check(apiRes, {
    'API GET status 200': (r) => r.status === 200,
    'API GET response time < 800ms': (r) => r.timings.duration < 800,
    'API GET has traceId': (r) => r.headers['X-Trace-Id'] !== undefined,
  });

  errorRate.add(apiRes.status !== 200);

  let payload = JSON.stringify({
    name: `Test Resource ${__VU}-${__ITER}`,
    value: Math.random() * 1000,
  });

  let postRes = http.post(`${BASE_URL}/api/v1/resources`, payload, {
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      'X-Trace-Id': `k6-post-${__VU}-${__ITER}`,
    },
  });

  check(postRes, {
    'API POST status 201': (r) => r.status === 201,
    'API POST response time < 800ms': (r) => r.timings.duration < 800,
  });

  errorRate.add(postRes.status !== 201);

  let errorRes = http.get(`${BASE_URL}/api/v1/resources/nonexistent`);
  check(errorRes, {
    'Error returns 404': (r) => r.status === 404,
    'Error is problem+json': (r) => r.headers['Content-Type'].includes('problem+json'),
    'Error has traceId': (r) => {
      let body = JSON.parse(r.body);
      return body.traceId !== undefined;
    },
  });

  sleep(1);
}

export function handleSummary(data) {
  return {
    '.BuildToValue/validations/k6-results.json': JSON.stringify(data),
    stdout: textSummary(data, { indent: ' ', enableColors: true }),
  };
}

function textSummary(data) {
  const passed = data.metrics.checks.values.passes;
  const failed = data.metrics.checks.values.fails;
  const p95 = data.metrics.http_req_duration.values['p(95)'];

  return `
    =====================================
    K6 Performance Test Results
    =====================================
    Checks Passed: ${passed}
    Checks Failed: ${failed}
    P95 Response Time: ${p95.toFixed(2)}ms
    Error Rate: ${(data.metrics.errors.values.rate * 100).toFixed(2)}%
    =====================================
  `;
}
