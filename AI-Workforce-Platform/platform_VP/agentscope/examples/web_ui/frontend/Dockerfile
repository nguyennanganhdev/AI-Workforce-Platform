# Web UI: build the Vite app, serve it with nginx.
# Build context: examples/web_ui (the pnpm workspace root).
FROM node:22-bookworm-slim AS build

WORKDIR /web
RUN corepack enable && corepack prepare pnpm@10.34.7 --activate

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY frontend/package.json frontend/
COPY backend/package.json backend/
RUN pnpm install --frozen-lockfile --ignore-scripts --filter frontend... --child-concurrency=1 --network-concurrency=4

COPY frontend frontend
# The browser calls the API at this address (baked in at build time).
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV NODE_OPTIONS=--max-old-space-size=1536
RUN pnpm --filter frontend run build

FROM nginx:1.27-alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /web/frontend/dist /usr/share/nginx/html
EXPOSE 80
