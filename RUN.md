# Running the backend

Dependencies are managed with [uv](https://docs.astral.sh/uv/) (`pyproject.toml` + `uv.lock`). Works the same on Windows and Linux.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- pnpm (for the frontend build — see `frontend/README.md`)

## Windows (PowerShell)

```powershell
uv sync
Copy-Item .env.example .env
uv run python main.py
```

## Linux / macOS

```bash
uv sync
cp .env.example .env
uv run python main.py
```

Either way, `uv sync` creates `.venv/` and installs everything from `uv.lock`. Edit `.env` first: `ADMIN_USERNAME` and `ADMIN_PASSWORD` are required (min 12 characters — the server exits without them). Nothing else needs changing to serve over plain HTTP; see the README's "Serving over plain HTTP" for what that does and does not protect.

The user is seeded into SQLite automatically on startup. To reseed on demand (e.g. after changing the password in `.env`):

```bash
uv run python seed.py
```

The dashboard serves at `http://localhost:8202` once the frontend is built (`cd frontend && pnpm install && pnpm build`) — without it, the API still runs but `/` returns a 404 for `index.html`.

## Notes

- Auth self-check: `uv run python test_auth.py`.

- `uv run <cmd>` runs inside the project venv without activating it — no `source .venv/bin/activate` / `.venv\Scripts\Activate.ps1` needed.
- To add a dependency: `uv add <package>`. This updates both `pyproject.toml` and `uv.lock` — commit both.
- GPU stats: NVIDIA GPUs are read via `pynvml` (NVML) on both platforms. On Windows, non-NVIDIA GPUs (Intel/AMD) are additionally listed via a WMI query (name + VRAM only, no live utilization).
- `DISK_PATH` defaults to `/`, which `psutil.disk_usage` resolves correctly on Windows too (current drive's root). Override it in `.env` if you want a specific drive, e.g. `DISK_PATH=D:\`.
