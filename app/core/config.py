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

# ── Paths ─────────────────────────────────────────────────────────────────────
# Two levels up from app/core/ → project root
BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIST: Path = BASE_DIR / "frontend" / "dist"
