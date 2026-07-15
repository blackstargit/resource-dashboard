# ── Stage 1: build the React frontend ───────────────────────────────────────
FROM node:22-alpine AS frontend-build
WORKDIR /app/frontend
RUN corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

# ── Stage 2: backend runtime ─────────────────────────────────────────────────
FROM python:3.12-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY main.py .
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

EXPOSE 8202
CMD ["python", "main.py"]
