# Platform web and landing page share one nginx container.
# Build context: platform_VP.
FROM node:24-bookworm-slim AS landing-build
WORKDIR /landing
COPY gui/landing-page/package.json gui/landing-page/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY gui/landing-page/ ./
RUN npm run build

FROM node:24-bookworm-slim AS build

WORKDIR /web
RUN corepack enable && corepack prepare pnpm@10.33.2 --activate

COPY agentscope/examples/web_ui/package.json agentscope/examples/web_ui/pnpm-lock.yaml agentscope/examples/web_ui/pnpm-workspace.yaml ./
COPY agentscope/examples/web_ui/frontend/package.json frontend/
COPY agentscope/examples/web_ui/backend/package.json backend/
RUN pnpm install --frozen-lockfile --ignore-scripts --filter frontend...

COPY agentscope/examples/web_ui/frontend frontend
# The browser calls the API at this address (baked in at build time).
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ARG VITE_VIN_EXPERIENCE_ENABLED=false
ENV VITE_VIN_EXPERIENCE_ENABLED=${VITE_VIN_EXPERIENCE_ENABLED}
# Git Bash rewrites "/api" to "C:/Program Files/Git/api"; refuse anything that is not a path or URL.
RUN case "$VITE_API_BASE_URL" in /*|http://*|https://*) ;; \
    *) echo "VITE_API_BASE_URL must start with / or http(s)://, got: $VITE_API_BASE_URL" >&2; exit 1 ;; esac
RUN pnpm --filter frontend run build
RUN if [ "$VITE_API_BASE_URL" = "/api" ]; then \
    WEB_DIST_DIR=/web/frontend/dist node --test frontend/tests/production-api.test.mjs; \
    fi

FROM nginx:1.27-alpine
ARG VCS_REF=unknown
LABEL org.opencontainers.image.title="Platform web with VAgents landing" \
      org.opencontainers.image.revision=$VCS_REF
COPY agentscope/examples/web_ui/frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /web/frontend/dist /usr/share/nginx/html
COPY --from=landing-build /landing/dist /usr/share/nginx/landing
EXPOSE 80
HEALTHCHECK --interval=20s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1/ && wget -q -O /dev/null http://127.0.0.1/login || exit 1
