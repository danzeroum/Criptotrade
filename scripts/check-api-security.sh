#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8080}"

echo "🔒 API Security: verificando headers e CORS em ${BASE_URL}"

# TLS/HSTS só é exigido quando há HTTPS (geralmente via reverse proxy)
if [[ "${BASE_URL}" == https* ]]; then
  curl -skI "${BASE_URL}" | grep -Ei '^strict-transport-security:' >/dev/null || echo "WARN: Sem HSTS (exigir em PROD/Proxy)"
fi

# Headers recomendados (podem estar no reverse proxy)
curl -skI "${BASE_URL}" | grep -Ei '^content-security-policy:'       >/dev/null || echo "WARN: CSP ausente (definir no proxy/app conforme UI)"
curl -skI "${BASE_URL}" | grep -Ei '^x-content-type-options:'        >/dev/null || echo "WARN: X-Content-Type-Options ausente"
curl -skI "${BASE_URL}" | grep -Ei '^x-frame-options:'               >/dev/null || echo "WARN: X-Frame-Options ausente"
curl -skI "${BASE_URL}" | grep -Ei '^referrer-policy:'               >/dev/null || echo "WARN: Referrer-Policy ausente"

# CORS (pode ser controlado por gateway/proxy)
if ! curl -skI "${BASE_URL}" | grep -Ei '^access-control-allow-origin:' >/dev/null; then
  echo "WARN: CORS header ausente (verifique config se necessário)"
fi

echo "✅ API Security check concluído (warnings são aceitáveis em DEV)"
