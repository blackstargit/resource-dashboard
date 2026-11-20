# TODO

Open work only. Finished items are deleted (git history keeps them). Tags:
`[next]` up next · `[later]` agreed but not scheduled · `[optional]` ·
`[decision]` blocked on a user decision.

---

## Features

### Process lifecycle tracking `[next]`

Pick a specific process and track it from start to end (CPU/RAM/GPU over its
whole lifetime, exit time/code), not just the live top-N snapshot that
`app/collectors/processes.py` gives today.

### Metrics history database `[decision]`

Persist metrics over time instead of only streaming live values. The idea was a
Postgres-compatible time-series database you can query with `psql` — most likely
**TimescaleDB** (a Postgres extension). Open questions: retention period, sample
rate, and whether it runs as a second compose service. Note `data/dashboard.db`
(SQLite) already exists, but only for the user and sessions.

---

## Cleanup

### Frontend dead files `[later]`

In the `frontend/` submodule (separate repo — commit and push there, then bump
the submodule pointer here):

- `src/assets/react.svg` is not imported anywhere — delete.
- `src/styles/index.css` and `src/styles/style.css` are one line each (the
  Tailwind import and the Google Fonts import); fold both into `styles.css` and
  drop the two extra imports in `src/main.tsx`.

### Pin the uv image in the Dockerfile `[optional]`

`COPY --from=ghcr.io/astral-sh/uv:latest` makes builds non-reproducible; pin a
version tag.

### `GET /` without a frontend build `[optional]`

`serve_root` in `app/app.py` returns a 500 (missing file) instead of a clear
message when `frontend/dist` hasn't been built.

### Old DB still in git history `[optional]`

`data/dashboard.db` was committed in `d42154d` and pushed, then untracked. It
holds the PBKDF2 verifier, which is login-equivalent. Decided: untrack only, no
history rewrite. Rotating `ADMIN_PASSWORD` makes the leaked verifier useless.
