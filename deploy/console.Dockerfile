# Builds the React console (docs/design/pages) and bakes the minified output into
# the TLS-terminating nginx image used by docker-compose.prod.yml.
#
# Self-contained: the deploy host needs only Docker (no Node). The reverse-proxy
# config is mounted at runtime by compose, so editing it does not require a rebuild.
#
# Context = repo root:  docker build -f deploy/console.Dockerfile .

FROM node:22-alpine AS console
WORKDIR /console
# Install deps first (cached unless the lockfile changes), then build.
COPY docs/design/pages/package.json docs/design/pages/package-lock.json ./
RUN npm ci
COPY docs/design/pages/ ./
RUN npm run build

FROM nginx:stable
# Static console (built, minified, no in-browser Babel). nginx serves this at /
# and reverse-proxies /v1/ and /health to the API (see deploy/nginx/criptotrade.conf).
COPY --from=console /console/dist /usr/share/nginx/html
