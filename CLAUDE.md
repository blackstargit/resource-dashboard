# Resource Dashboard — Agent Reference

Single-user, real-time host resource monitor: FastAPI backend streams CPU/RAM/disk/GPU/network/process stats over SSE and serves the React frontend from the same origin. A personal tool for checking up on a server — no multi-tenant or public-signup considerations apply anywhere.

---

## IMPORTANT: Agent Rules

General rules — dictated prompts, explain before acting, no `sudo`, no
build/commit on your own, dependency checks, incremental compilation, where
lessons get written — are in [RULES.md](RULES.md), imported here and always
loaded:

@RULES.md

Project-specific rules:

- **This file is the memory.** Auto-memory is off via `.claude/settings.json` (which also pins the model, effort and plugin set every PC shares). Durable lessons go into the file that owns the topic (see "Where the detail lives"), never `~/.claude`.
- **Design flow:** brainstorm in chat (explore, ask, present the design, get approval), then implement directly. Don't write or commit a separate spec/design doc — the in-chat approval is the sign-off.
- **"Build/deploy/restart" here means** `docker compose … up -d --build` on a host (see Deployment). Recreating the container drops open SSE streams; logins survive (sessions are in the `dashboard-data` volume).
- **Secrets:** `.env` and `data/` (SQLite with the password verifier, which is login-equivalent) — don't read them; both are denied in `.claude/settings.json`. `data/` must never be committed again.
- **`frontend/` is a separate repo** (submodule, `github.com/blackstargit/resource-dashboard-frontend`). Commit and push frontend changes there first, then commit the bumped pointer here.
- **The doc layout is deliberate.** Open work lives in [TODO.md](TODO.md) (finished items are deleted, not logged). `archive/` holds superseded files (the systemd unit) — current docs win.

---

## Repository Structure

```
resource-dashboard/
├── app/
│   ├── app.py                 # create_app(): auth middleware, routers, SPA mount
│   ├── collectors/            # cpu, ram, disk, gpu, network, processes, system
│   ├── core/                  # config.py (env), auth.py (signing scheme), logging.py
│   └── routers/               # auth.py, resources.py, stream.py (SSE)
├── tests/test_auth.py         # the only test — plain script, no pytest
├── frontend/                  # React/Vite dashboard (submodule, own repo)
├── docs/                      # overview.md, screenshot.png
├── RUN.md                     # how to run: Docker deployment + local dev
├── deploy/cloudflared.yml     # reference tunnel ingress (secondary host)
├── archive/                   # superseded: resource-dash.service (systemd)
├── Dockerfile                 # 2 stages: pnpm build → python:3.12-slim + uv
├── docker-compose.yml         # pid: host, network_mode: host, / → /host:ro
├── docker-compose.gpu.yml     # NVIDIA overlay
├── main.py / seed.py          # entry point / reseed admin from .env
├── CLAUDE.md                  # this file: project rules, architecture, deployment, index
├── RULES.md                   # general, project-independent rules (imported)
├── .claude/settings.json      # auto-memory off, model/effort, plugins, permissions
└── TODO.md                    # open work
```

Git remotes: `origin` (GitHub) and `official` (self-hosted Gitea on the LAN).

---

## Commands

Backend (uv-managed, Python 3.12+):

```bash
uv sync                          # install deps into .venv
cp .env.example .env             # then set ADMIN_USERNAME / ADMIN_PASSWORD (min 12 chars) — server exits without them
uv run python main.py            # serves API + built frontend on one port
uv run python seed.py            # (re)seed the single admin user; rotating the password revokes all sessions
uv run python -m tests.test_auth # the only test: login/replay/retargeting/revocation (must be -m, run from repo root)
```

Frontend (`frontend/`):

```bash
git submodule update --init --recursive   # first checkout
cd frontend && pnpm install
pnpm dev                        # :8003, proxies /api to the backend at :8202 (vite.config.ts)
pnpm build                      # → frontend/dist, served directly by the backend
pnpm lint
```

Docker (frontend build + backend as one container):

```bash
docker compose up -d --build                                                 # no GPU stats
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build # with NVIDIA GPU stats
docker compose logs -f
```

Full guide: [RUN.md](RUN.md). Deployment is Docker only; running natively is for local development and needs `pnpm build` in `frontend/` first.

---

## Architecture

**Single origin.** `app/app.py: create_app()` (called from `main.py`) mounts the API routers, then `frontend/dist` as static files at `/`. No CORS, because the frontend is always same-origin.

**Auth is per-request HMAC signing, not bearer tokens.** One `@app.middleware("http")` in `app/app.py` covers everything under `/api/` except `/api/v1/auth/{challenge,login}`. Scheme (`app/core/auth.py`, consumed by `app/routers/auth.py`):

1. Client fetches `salt` + `iterations` + a one-shot `challenge` from `/auth/challenge`.
2. Client derives a PBKDF2 verifier locally and proves it via `HMAC(verifier, challenge)` — the password never crosses the wire; the challenge is burned on use.
3. Server returns a public `session_id`; both sides derive the session key as `HMAC(verifier, session_id)`, never transmitted.
4. Every request signs `method + path + timestamp + nonce`. Signatures are single-use (nonce cache), time-boxed (`SIGNATURE_WINDOW_SECONDS`), and bound to one method+path, so they can't be replayed or retargeted.

`EventSource` can't set headers, so the same four values are accepted as query params (`s`, `t`, `n`, `g`) — safe only *because* they're single-use signatures. Designed to hold against a passive eavesdropper over plain HTTP (not an active MITM); see the `app/core/auth.py` docstring and README "Serving over plain HTTP". Single-user by design: exactly one `users` row (`id = 1` enforced by a `CHECK`), seeded from `.env` on every startup. The frontend mirror of the client side is `frontend/src/lib/authCrypto.ts`.

**Collectors** (`app/collectors/`) are each capability-checked independently. `GET /api/v1/resources/health` reports which work on the host and the frontend degrades panels rather than erroring (e.g. no NVIDIA GPU). GPU uses `pynvml`; Windows also lists non-NVIDIA GPUs via WMI (name/VRAM only). Network reports raw bytes/sec RX/TX.

**The container monitors the host, not itself.** `docker-compose.yml` runs `pid: host` and `network_mode: host`, and bind-mounts host `/` read-only at `/host` (`DISK_PATH=/host`). That's why `ALLOW_PROCESS_KILL` (the one destructive endpoint, `DELETE /api/v1/resources/processes/{pid}`) defaults to `false` — enabling it lets the browser SIGTERM real host processes.

**Config** is centralized in `app/core/config.py`, read from `.env` via `python-dotenv`, defaults matching `.env.example`. No per-environment settings; Docker overrides via `docker-compose.yml`'s `environment:` block. A new env var is only tunable in Docker if it's also passed through there.

---

## Deployment

Multiple deployments, each a Docker Compose container named `resource-dashboard-resource-dashboard-1`; the port comes from that host's `.env` `PORT`.

| Host | Role | Port | Compose files | Exposure |
|---|---|---|---|---|
| `sadiq-ai` (`/var/www/resource-dashboard`) | **main production** | 8200 | base + `docker-compose.gpu.yml` | direct (host network), no tunnel |
| the `server.boltertech.com` server | secondary | 8212 | — | Cloudflare Tunnel + Access |

**`server.boltertech.com`** — tunnel `whatsapp` (id `2c221404-3c22-49bb-a262-8c8a66457efe`), run by that host's systemd `cloudflared` service, which is shared with unrelated services (e.g. `whatsapp.boltertech.com`). `deploy/cloudflared.yml` is a reference copy of its ingress. On that host the source of truth is `~/.cloudflared/config.yml`; the service reads a root-owned copy, so after editing (the user runs these):

```bash
sudo cp ~/.cloudflared/config.yml /etc/cloudflared/config.yml
sudo systemctl restart cloudflared
```

It is also gated by **Cloudflare Access** (Zero Trust → Access → Applications → "Resource Dashboard"), allowing one email only. That's two logins end to end: Access (email OTP), then the app's own username/password.

---

## Where the detail lives

| File | Covers | Loaded |
|---|---|---|
| [RULES.md](RULES.md) | General rules for any project: dictated prompts, explain before acting, hard limits (sudo/build/commit/secrets), pre-code checks, incremental compilation, where lessons go | **always** — imported in Agent Rules |
| [TODO.md](TODO.md) | All open work: features, cleanup, pending decisions | on demand |
| [README.md](README.md) | User-facing: features, Docker quick start, env vars, auth explainer, API endpoints | on demand |
| [RUN.md](RUN.md) | Docker deployment (first deploy, update, `.env` changes, volume, process kill) and local dev (frontend build first, dev server, checks) | on demand |
| [docs/overview.md](docs/overview.md) | Non-technical one-page pitch | on demand |

Keep each fact in exactly one of these files and link to it elsewhere.
