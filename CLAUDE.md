# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Backend (uv-managed, Python 3.12+):

```bash
uv sync                        # install deps into .venv
cp .env.example .env           # then set ADMIN_USERNAME / ADMIN_PASSWORD (min 12 chars) — server exits without them
uv run python main.py          # run the server (serves API + built frontend on one port)
uv run python seed.py          # (re)seed the single admin user from .env; rotating the password revokes all sessions
uv run python test_auth.py     # the only test — a plain script (no pytest), exercises login/replay/retargeting/revocation
```

Frontend (`frontend/` is a separate git repo, vendored as a submodule):

```bash
git submodule update --init --recursive   # first checkout
cd frontend && pnpm install
pnpm dev                        # dev server on :8003, proxies /api to backend at :8202 (vite.config.ts)
pnpm build                      # outputs to frontend/dist, which the backend serves directly — no separate frontend server in prod
pnpm lint
```

Docker (whole app — frontend build + backend — as one container):

```bash
docker compose up -d --build                                          # no GPU stats
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build   # with NVIDIA GPU stats
```

## Architecture

**Single-origin app.** `app/app.py: create_app()` is the FastAPI factory (called from `main.py`). It mounts the API routers, then mounts `frontend/dist` as static files at `/` (built separately, checked into no repo — built via `pnpm build`). There's no CORS setup because the frontend is always served from the same origin as the API.

**Auth is not bearer tokens — it's per-request HMAC signing**, applied by one `@app.middleware("http")` in `app/app.py` covering everything under `/api/` except `/api/v1/auth/{challenge,login}`. The scheme (implemented in `app/core/auth.py`, consumed by `app/routers/auth.py`):

1. Client fetches `salt` + `iterations` + a one-shot `challenge` from `/auth/challenge`.
2. Client derives a PBKDF2 verifier from the password locally and proves knowledge of it via `HMAC(verifier, challenge)` — the password itself never crosses the wire, and the challenge is burned on use.
3. Server returns a public `session_id`; both sides independently derive a session key as `HMAC(verifier, session_id)`, which is also never transmitted.
4. Every subsequent request signs `method + path + timestamp + nonce` with that session key. Signatures are single-use (nonce cache), time-boxed (`SIGNATURE_WINDOW_SECONDS`), and bound to one exact method+path — so a captured signature can't be replayed or retargeted at a different route.

Because `EventSource` (used for the SSE stream) can't set headers, the same four signature values are also accepted as query params (`s`, `t`, `n`, `g`) — this is safe specifically *because* they're single-use signatures, not reusable tokens. This whole design is meant to remain safe against a passive eavesdropper even over plain HTTP; see `app/core/auth.py` module docstring and the README's "Serving over plain HTTP" for what it does and doesn't protect against. It's single-user by design — there is exactly one row in the `users` table (`id = 1` is enforced by a `CHECK`), seeded from `.env` on every startup.

**Resource collection** lives under `app/collectors/` (`cpu.py`, `ram.py`, `disk.py`, `gpu.py`, `processes.py`, `system.py`), each independently capability-checked — `GET /api/v1/resources/health` reports which ones actually work on the current host, and the frontend degrades panels gracefully rather than erroring when one is unavailable (e.g. no NVIDIA GPU). GPU stats use `pynvml`; Windows additionally lists non-NVIDIA GPUs via WMI (name/VRAM only, no live utilization).

**The container monitors the host, not itself.** `docker-compose.yml` runs with `pid: host` (so process/CPU stats reflect the host, not the container's namespace) and bind-mounts host `/` read-only at `/host` (`DISK_PATH=/host` in the container env). This is why `ALLOW_PROCESS_KILL` (the one destructive endpoint, `DELETE /api/v1/resources/processes/{pid}`) defaults to `false` — enabling it lets the browser SIGTERM real host processes.

**Config is centralized** in `app/core/config.py`, reading everything from `.env` (loaded via `python-dotenv`) with defaults matching `.env.example`. There's no separate settings-per-environment mechanism — Docker overrides values via `docker-compose.yml`'s `environment:` block instead.

## Deployment

Runs in Docker Compose on this host, container `resource-dashboard-resource-dashboard-1`, port `8212` (`.env`'s `PORT`, overriding the `.env.example` default of 8202).

Exposed to the internet via a Cloudflare Tunnel (systemd service `cloudflared` on this host — shared with other unrelated services, e.g. `whatsapp.boltertech.com`, not project-specific):

- Hostname: `server.boltertech.com` → `http://localhost:8212`
- Tunnel: `whatsapp` (id `2c221404-3c22-49bb-a262-8c8a66457efe`)
- Ingress config source of truth: `~/.cloudflared/config.yml`. The systemd service reads a separate root-owned copy at `/etc/cloudflared/config.yml` — after editing the former, sync and restart:
  ```bash
  sudo cp ~/.cloudflared/config.yml /etc/cloudflared/config.yml
  sudo systemctl restart cloudflared
  ```
- Gated additionally by **Cloudflare Access** (Zero Trust → Access → Applications → "Resource Dashboard"), policy allows only `subscriptions@boltertech.com`. This sits in front of the app's own auth scheme above — two logins required end to end: Cloudflare Access (email OTP), then the app's own username/password.

Single-user personal tool (checking up on one server) — no multi-tenant or public-signup considerations apply anywhere in this codebase.
