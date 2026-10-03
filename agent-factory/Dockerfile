FROM oven/bun:1.3.14
WORKDIR /app
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile --production --ignore-scripts
COPY src ./src
ENV FACTORY_HOST=0.0.0.0
EXPOSE 4010
USER bun
CMD ["bun", "src/server.ts"]
