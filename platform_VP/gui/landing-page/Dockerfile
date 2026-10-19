FROM node:22-alpine AS build
WORKDIR /app
RUN apk add --no-cache ca-certificates
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY index.html vite.config.ts tsconfig.json postcss.config.mjs ./
COPY src ./src
COPY components ./components
COPY lib ./lib
COPY scripts ./scripts
COPY public ./public
RUN npm run build

FROM nginx:1.28-alpine
ARG VCS_REF=unknown
LABEL org.opencontainers.image.title="VAgents landing page" \
      org.opencontainers.image.source="https://github.com/nguyennanganhdev/AI-Workforce-Platform" \
      org.opencontainers.image.revision=$VCS_REF
COPY deploy/container-nginx.conf /etc/nginx/nginx.conf
COPY --from=build /app/dist /usr/share/nginx/html
USER nginx
EXPOSE 8080
HEALTHCHECK --interval=20s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1:8080/ || exit 1
ENTRYPOINT ["nginx", "-g", "daemon off;"]
