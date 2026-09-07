"""
app/core/config.py
==================
Central configuration — environment variables, path constants.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Server ────────────────────────────────────────────────────────────────────
HOST: str = os.getenv("HOST", "127.0.0.1")
PORT: int = int(os.getenv("PORT", 8202))
RELOAD: bool = os.getenv("RELOAD", "False")

# ── API ───────────────────────────────────────────────────────────────────────
API_V1_PREFIX: str = "/api/v1"

# ── Auth ──────────────────────────────────────────────────────────────────────
# The single dashboard user. Seeded into SQLite by seed.py / on startup.
ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "")
ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "")

DB_PATH: str = os.getenv("DB_PATH", "data/dashboard.db")
SESSION_TTL_SECONDS: int = int(os.getenv("SESSION_TTL_SECONDS", 7 * 24 * 3600))

# Cost of turning the password into a verifier. This is also exactly what an
# eavesdropper must pay per password guess, so raise it if login feels fast.
# The browser computes it too, so it is a UX/security trade: ~1s on a laptop.
PBKDF2_ITERATIONS: int = int(os.getenv("PBKDF2_ITERATIONS", 300_000))

# How far a request timestamp may drift from server time before it is refused.
SIGNATURE_WINDOW_SECONDS: int = int(os.getenv("SIGNATURE_WINDOW_SECONDS", 120))

LOGIN_MAX_FAILURES: int = int(os.getenv("LOGIN_MAX_FAILURES", 5))
LOGIN_WINDOW_SECONDS: int = int(os.getenv("LOGIN_WINDOW_SECONDS", 300))

# Terminating host processes from a browser is the one destructive thing this
# app can do. Off by default; opt in only if you trust the network path.
ALLOW_PROCESS_KILL: bool = os.getenv("ALLOW_PROCESS_KILL", "false").lower() == "true"

# ── Paths ─────────────────────────────────────────────────────────────────────
# Two levels up from app/core/ → project root
BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIST: Path = BASE_DIR / "frontend" / "dist"

# Root filesystem to report disk usage for. In Docker this is set to the
# path where the host's root filesystem is bind-mounted (see docker-compose.yml).
DISK_PATH: str = os.getenv("DISK_PATH", "/")
