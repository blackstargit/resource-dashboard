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

Either way, `uv sync` creates `.venv/` and installs everything from `uv.lock`. Edit `.env` first if you need to override `PORT`, `HOST`, or `DISK_PATH`.

The dashboard serves at `http://localhost:8202` once the frontend is built (`cd frontend && pnpm install && pnpm build`) — without it, the API still runs but `/` returns a 404 for `index.html`.

## Notes

- `uv run <cmd>` runs inside the project venv without activating it — no `source .venv/bin/activate` / `.venv\Scripts\Activate.ps1` needed.
- To add a dependency: `uv add <package>`. This updates both `pyproject.toml` and `uv.lock` — commit both.
- GPU stats: NVIDIA GPUs are read via `pynvml` (NVML) on both platforms. On Windows, non-NVIDIA GPUs (Intel/AMD) are additionally listed via a WMI query (name + VRAM only, no live utilization).
- `DISK_PATH` defaults to `/`, which `psutil.disk_usage` resolves correctly on Windows too (current drive's root). Override it in `.env` if you want a specific drive, e.g. `DISK_PATH=D:\`.
