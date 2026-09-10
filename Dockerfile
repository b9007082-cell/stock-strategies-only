FROM node:22-bookworm-slim AS web-builder
WORKDIR /app/web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM node:22-bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN python3 -m venv .venv && .venv/bin/pip install --no-cache-dir uv && .venv/bin/uv sync --no-dev
COPY . .
COPY --from=web-builder /app/web/.next ./web/.next
COPY --from=web-builder /app/web/node_modules ./web/node_modules
RUN chmod +x start-cloud.sh
ENV PORT=10000
EXPOSE 10000
CMD ["./start-cloud.sh"]
