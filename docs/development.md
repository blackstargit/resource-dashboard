# Development

Backend dependencies are managed with [uv](https://docs.astral.sh/uv/) (`pyproject.toml` + `uv.lock`); the frontend is a git submodule built with pnpm. Works the same on Windows and Linux.

## Prerequisites

- Python 3.12+ and [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Node 22+ and pnpm (`corepack enable`)

## First run

```bash
git submodule update --init --recursive
uv sync                          # creates .venv/ from uv.lock
cp .env.example .env             # Windows: Copy-Item .env.example .env
```

Edit `.env`: `ADMIN_USERNAME` and `ADMIN_PASSWORD` are required (min 12 characters — the server exits without them). Nothing else needs changing to serve over plain HTTP; see the README's "Serving over plain HTTP" for what that does and does not protect.

```bash
cd frontend && pnpm install && pnpm build && cd ..
uv run python main.py
```

The dashboard serves at `http://localhost:8202` (`PORT` in `.env`). Without a frontend build the API still runs, but `/` returns a 404 for `index.html`.

## Frontend dev server

```bash
cd frontend && pnpm dev          # :8003, proxies /api to the backend on :8202 (vite.config.ts)
```

## Checks

```bash
uv run python -m tests.test_auth # auth self-check: login, replay, retargeting, revocation
cd frontend && pnpm lint
```

## Notes

- The user is seeded into SQLite on every startup. `uv run python seed.py` does the same on demand; changing the password revokes every session.
- `uv run <cmd>` runs inside the project venv without activating it.
- Add a dependency with `uv add <package>` — commit both `pyproject.toml` and `uv.lock`.
- GPU stats: NVIDIA GPUs are read via `pynvml` (NVML) on both platforms. On Windows, non-NVIDIA GPUs (Intel/AMD) are additionally listed via WMI (name + VRAM only, no live utilization).
- `DISK_PATH` defaults to `/`, which `psutil.disk_usage` resolves correctly on Windows too (current drive's root). Override in `.env` for a specific drive, e.g. `DISK_PATH=D:\`.
