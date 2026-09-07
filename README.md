# AI Resource Monitoring Dashboard

A real-time system resource monitoring dashboard, tracking CPU, RAM, Disk, GPU usage, and running processes. The backend (Python/FastAPI) streams live stats over Server-Sent Events and serves the React frontend as static files, so the whole app runs as a single service.

> **Platform support: Linux and Windows.** `python main.py` runs natively on both (FastAPI/uvicorn/psutil are cross-platform, `psutil.disk_usage` works with both `/` and `C:\`-style paths, and the GPU collector has a Windows WMI fallback for non-NVIDIA cards). The Docker Compose setup (host PID namespace + root filesystem bind mount) targets Linux hosts; on Windows it runs inside Docker Desktop's Linux VM rather than monitoring the Windows host directly. systemd-based deployment (`resource-dash.service`) is Linux-only.

![Dashboard screenshot](./docs/screenshot.png)

## Features

- **Live metrics** — CPU (overall + per-core, plus current/max frequency), RAM, disk usage & I/O, and multi-GPU stats (load, VRAM, temperature), all pushed over SSE at an adjustable interval.
- **Process manager** — sortable top-process list (by CPU, memory, or GPU memory) with per-process GPU VRAM attribution, filterable by name/PID.
- **Kill processes from the UI** — terminate a runaway process (SIGTERM) directly from the process table. The backend refuses to kill itself.
- **System info** — uptime, boot time, and battery status (on laptops).
- **Self-monitoring** — the dashboard reports its own CPU/memory/thread usage, so you can see the observer's own footprint.
- **Capability-aware** — the health endpoint reports which collectors (CPU/RAM/disk/GPU) are actually available on the host, and the UI degrades gracefully (e.g. "unavailable" GPU panels) when they aren't.

> **Security note:** the dashboard requires a login, and the process-kill endpoint (`DELETE /api/v1/resources/processes/{pid}`) is additionally disabled unless you set `ALLOW_PROCESS_KILL=true`. If you serve this over plain HTTP, read [Serving over plain HTTP](#serving-over-plain-http) first.

## Quick Start (Docker)

The whole app — frontend build + backend — runs as a single container.

**Prerequisites:**

- [Docker](https://docs.docker.com/engine/install/) with the Compose plugin (`docker compose version`)
- An NVIDIA GPU with drivers installed on the host — **optional**. Without it the dashboard still runs fine, just with GPU panels reporting "unavailable".
- **NVIDIA Container Toolkit** — only needed if you want GPU stats. On Ubuntu/Debian:

  ```bash
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
  curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
  sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
  sudo nvidia-ctk runtime configure --runtime=docker
  sudo systemctl restart docker
  ```

  For other distros, see [NVIDIA&#39;s install guide](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).

**Run it:**

```bash
git clone --recurse-submodules <this-repo-url>
cd resource-dashboard

# Set the single dashboard user — compose refuses to start without these:
cp .env.example .env    # then edit ADMIN_USERNAME / ADMIN_PASSWORD

# Without GPU stats:
docker compose up -d --build

# With GPU stats (toolkit installed above):
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
```

The dashboard will be available at `http://localhost:8202`.

The container monitors the **host** machine, not itself: it shares the host's PID namespace (process/CPU stats) and mounts the host's root filesystem read-only at `/host` (disk stats), so the numbers you see match what you'd get running the app directly on the host.

## Project Structure

```
.
├── app/                          # Modularized FastAPI backend
│   ├── app.py                    # Application factory
│   ├── collectors/               # Resource metric collectors
│   │   ├── cpu.py
│   │   ├── ram.py
│   │   ├── disk.py
│   │   ├── gpu.py
│   │   └── processes.py
│   ├── core/                     # Core configuration and logging
│   │   ├── config.py
│   │   └── logging.py
│   └── routers/                  # API endpoint handlers
│       ├── resources.py          # Resource stats endpoints
│       └── stream.py             # Streaming endpoints
├── frontend/                     # React dashboard (git submodule)
└── main.py                       # Server entry point
```

## Quick Start (Local Development)

### Backend Setup

Dependencies are managed with [uv](https://docs.astral.sh/uv/). See [RUN.md](./RUN.md) for full step-by-step setup on Windows and Linux.

1. Install dependencies (creates `.venv` automatically):

   ```bash
   uv sync
   ```
2. Set up environment variables:

   ```bash
   cp .env.example .env
   ```

   Edit `.env` if you need to override any defaults.
3. Build the frontend:

   ```bash
   cd frontend
   pnpm install
   pnpm build
   cd ..
   ```
4. Run the server:

   ```bash
   uv run python main.py
   ```

   The dashboard will be available at `http://localhost:8202`

## Configuration

Available environment variables (see `.env.example`):

- `PORT`: Server port (default: 8202)
- `HOST`: Server host (default: 127.0.0.1)
- `RELOAD`: Enable uvicorn auto-reload on code changes (default: False)
- `DISK_PATH`: Filesystem path to report disk usage for (default: `/`). In Docker this points at the bind-mounted host root (`/host`).
- `ADMIN_USERNAME` / `ADMIN_PASSWORD`: The one dashboard user. Required (min 12 characters). Seeded into SQLite on startup.
- `DB_PATH`: SQLite file holding the user and active sessions (default: `data/dashboard.db`; `/data/dashboard.db` on the `dashboard-data` volume in Docker).
- `SESSION_TTL_SECONDS`: Session lifetime (default: 604800 — 7 days).
- `PBKDF2_ITERATIONS`: Password-derivation cost (default: 300000). Also the cost an eavesdropper pays per password guess, so higher is safer — but the browser computes it too, so it is a UX trade (~1s on a laptop). Changing it requires re-seeding.
- `SIGNATURE_WINDOW_SECONDS`: How far a client clock may drift from the server before requests are refused (default: 120).
- `LOGIN_MAX_FAILURES` / `LOGIN_WINDOW_SECONDS`: Failed logins per IP before a lockout (default: 5 per 300s).
- `ALLOW_PROCESS_KILL`: Allow terminating host processes from the browser (default: `false`).

## Authentication

The dashboard is single-user. Credentials come from `.env` and are seeded into SQLite
on every startup; `uv run python seed.py` does the same thing on demand. Change
`ADMIN_PASSWORD` and restart (or re-run `seed.py`) to rotate the password — that also
revokes every existing session.

**The password is never transmitted, and neither is any reusable token.** The scheme is
built for plain HTTP:

1. The browser fetches a salt, an iteration count, and a one-shot challenge.
2. It derives a *verifier* from the password locally (PBKDF2-HMAC-SHA256) and returns
   only `HMAC(verifier, challenge)`. The challenge is burned on use, so a captured proof
   cannot be replayed.
3. The server returns a session **id**, which is public. The matching session **key** is
   derived independently on both sides as `HMAC(verifier, session_id)` and never sent.
4. Every later request carries `HMAC(session_key, method + path + timestamp + nonce)`.
   Signatures are bound to one method and path, are single-use, and expire in seconds.

So anyone reading the wire sees no password, and nothing they capture can be replayed or
re-aimed at a different endpoint. The one destructive route, `DELETE …/processes/{pid}`,
has its target in the signed path.

Because `EventSource` cannot set headers, the live stream passes the same four values as
query parameters (`s`, `t`, `n`, `g`) instead. They are signatures, not bearer tokens, so
appearing in a URL costs nothing.

Run `uv run python test_auth.py` to exercise the whole scheme, including replay,
retargeting, and revocation.

## Serving over plain HTTP

This app is safe to serve over HTTP **against a passive eavesdropper** — someone
reading traffic on shared wifi, or an ISP logging it. They cannot recover your password
and cannot reuse anything they capture.

It is **not** safe against an *active* attacker who can modify traffic in flight. Over
HTTP such an attacker can rewrite the JavaScript before it reaches the browser, and no
client-side scheme survives that. Only TLS fixes it.

Given that:

- Leave `ALLOW_PROCESS_KILL=false` unless you specifically need it. The container shares
  the host PID namespace, so that endpoint can terminate host processes.
- If you can get TLS later, nothing here needs to change — the scheme works unmodified
  over HTTPS, and layering the two is strictly better than either alone.
- Two ways to get HTTPS without managing a certificate yourself, if the situation
  changes: a Cloudflare Tunnel (no inbound ports, no cert on the host) or Tailscale
  Funnel. Both terminate TLS for you.

## API Endpoints

All `/api/` endpoints below require a valid request signature and return `401` without one; `/auth/challenge` and `/auth/login` are the exceptions.

- `GET /`: Serves the React dashboard (index.html)
- `GET /api/v1/auth/challenge`: Public KDF parameters (`salt`, `iterations`) plus a one-shot `challenge`
- `POST /api/v1/auth/login`: `{"username", "challenge", "proof"}` → `{session_id, server_time}`. `401` on a bad proof, `429` after too many failures from one IP
- `POST /api/v1/auth/logout`: Revokes the session server-side
- `GET /api/v1/auth/me`: `200` if the signature is valid, `401` otherwise — the frontend uses this to decide between the login form and the dashboard
- `GET /api/v1/resources/stats`: Current snapshot of all resource stats — CPU, RAM, disk, GPUs, backend process, system (JSON)
- `GET /api/v1/resources/stats/stream`: Real-time resource stats stream (Server-Sent Events). Query param `interval` (seconds, clamped 0.1–10, default 1.0) sets the push rate.
- `GET /api/v1/resources/health`: Health check — reports which collectors (`cpu_monitoring`, `ram_monitoring`, `disk_monitoring`, `gpu_monitoring`) are available on this host
- `GET /api/v1/resources/processes`: Top processes. Query params `limit` (1–100, default 25) and `sort_by` (`cpu` | `memory` | `gpu_memory`)
- `DELETE /api/v1/resources/processes/{pid}`: Terminate a process by PID (SIGTERM). Returns 404 if the PID doesn't exist, 403 if permission is denied or the PID is the backend's own process

## Frontend

The React dashboard is included as a git submodule. To work with it:

```bash
# Update the submodule
git submodule update --init --recursive

# Rebuild frontend after changes
cd frontend && pnpm build && cd ..
```

The backend automatically serves the built frontend files when available. See [frontend/README.md](https://github.com/blackstargit/resource-dashboard-frontend/blob/main/README.md) for frontend-specific development instructions (dev server, structure, env vars).
