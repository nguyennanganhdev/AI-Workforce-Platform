# Web UI: build the Vite app, serve it with nginx.
# Build context: examples/web_ui (the pnpm workspace root).
FROM node:24-bookworm-slim AS build

WORKDIR /web
RUN corepack enable && corepack prepare pnpm@12.11.2 --activate

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY frontend/package.json frontend/
COPY backend/package.json backend/
RUN pnpm install --frozen-lockfile --ignore-scripts --filter frontend...

COPY frontend frontend
# The browser calls the API at this address (baked in at build time).
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
# Git Bash rewrites "/api" to "C:/Program Files/Git/api"; refuse anything that is not a path or URL.
RUN case "$VITE_API_BASE_URL" in /*|http://*|https://*) ;; \
    *) echo "VITE_API_BASE_URL must start with / or http(s)://, got: $VITE_API_BASE_URL" >&2; exit 1 ;; esac
RUN pnpm --filter frontend run build
RUN if [ "$VITE_API_BASE_URL" = "/api" ]; then \
    WEB_DIST_DIR=/web/frontend/dist node --test frontend/tests/production-api.test.mjs; \
    fi

FROM nginx:1.27-alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /web/frontend/dist /usr/share/nginx/html
EXPOSE 80
