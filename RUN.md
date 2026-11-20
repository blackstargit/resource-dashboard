# Running the dashboard

Deployment is **Docker Compose**: one container builds the frontend and runs the backend. Running natively is only for local development.

---

## Deployment (Docker)

The image builds the frontend itself (Dockerfile stage 1, `pnpm build`), so the host needs no Node/pnpm/uv — but the `frontend/` submodule **must be checked out**, or the build has nothing to copy.

Prerequisites: Docker with the Compose plugin. For GPU stats, also an NVIDIA driver and the NVIDIA Container Toolkit (install steps in the [README](README.md#quick-start-docker)).

### First deploy

```bash
git clone --recurse-submodules <repo-url> resource-dashboard
cd resource-dashboard
cp .env.example .env    # set ADMIN_USERNAME / ADMIN_PASSWORD (min 12 chars) and PORT
```

```bash
# with GPU stats (main production, sadiq-ai)
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build

# without GPU stats
docker compose up -d --build
```

The container uses host networking, so it listens directly on the host's `PORT` (`8200` on production; see CLAUDE.md "Deployment" for each host).

### Update to the latest code

```bash
git pull
git submodule update --init --recursive
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
```

Recreating the container drops open live streams; the browser reconnects. Logins survive.

### Day to day

```bash
docker compose ps
docker compose logs -f
```

- **Change the password / any `.env` value:** edit `.env`, then rerun the `up -d` command above. The container only reads `.env` when it is created, and the user is re-seeded on startup. A password change logs out every session.
- **Data:** the user and sessions live in the `dashboard-data` volume (`/data/dashboard.db`). `docker compose down` keeps it; `down -v` deletes it (it is recreated from `.env` on the next start).
- **Process kill:** `ALLOW_PROCESS_KILL=true` in `.env` lets the browser SIGTERM real host processes (the container shares the host PID namespace). Leave it `false` unless needed.

---

## Local development (no Docker)

Requires Python 3.12+, [uv](https://docs.astral.sh/uv/getting-started/installation/), Node 22+ and pnpm (`corepack enable`). Works on Linux and Windows.

**1. Build the frontend first** — the backend serves `frontend/dist`; without it `/` returns 404.

```bash
git submodule update --init --recursive
cd frontend
pnpm install
pnpm build
cd ..
```

**2. Run the backend:**

```bash
uv sync                          # creates .venv/ from uv.lock
cp .env.example .env             # Windows: Copy-Item .env.example .env — then set ADMIN_USERNAME / ADMIN_PASSWORD
uv run python main.py            # http://localhost:8202
```

Rebuild the frontend (`pnpm build`) after frontend changes, or use the dev server for hot reload instead:

```bash
cd frontend && pnpm dev          # :8003, proxies /api to the backend on :8202 (vite.config.ts)
```

### Checks

```bash
uv run python -m tests.test_auth # auth self-check: login, replay, retargeting, revocation
cd frontend && pnpm lint
```

### Notes

- The user is seeded into SQLite (`data/dashboard.db`) on every startup; `uv run python seed.py` does the same on demand.
- Add a Python dependency with `uv add <package>` and commit both `pyproject.toml` and `uv.lock`.
- GPU stats use `pynvml` (NVIDIA). On Windows, non-NVIDIA GPUs are also listed via WMI (name + VRAM only).
- `DISK_PATH` defaults to `/`, which also resolves on Windows (current drive's root); override e.g. `DISK_PATH=D:\`.
