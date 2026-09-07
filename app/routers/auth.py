"""
app/routers/auth.py
===================
Challenge/response login for the single dashboard user.

The password never crosses the wire, and neither does the session key. The
client fetches the KDF parameters, derives the verifier locally, and proves
knowledge of it against a one-shot challenge. See app/core/auth.py.

Routes are prefixed at /api/v1/auth. /challenge, /login and /logout are the
only endpoints the signature middleware lets through unsigned.
"""
import time

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.core import auth
from app.core.config import (
    ALLOW_PROCESS_KILL,
    API_V1_PREFIX,
    SESSION_TTL_SECONDS,
    SIGNATURE_WINDOW_SECONDS,
)
from app.core.logging import get_logger

logger = get_logger("routers.auth")

router = APIRouter(prefix=f"{API_V1_PREFIX}/auth")


class LoginRequest(BaseModel):
    username: str
    challenge: str
    proof: str


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.get("/challenge")
def challenge(request: Request):
    """
    Public KDF parameters plus a one-shot challenge.

    The salt is not a secret; it exists so the verifier cannot be precomputed.
    Refused while the caller is locked out, so this cannot be used to farm
    challenges for offline work any faster than login itself allows.
    """
    if auth.is_locked_out(_client_ip(request)):
        raise HTTPException(429, "Too many failed attempts. Try again later.")

    user = auth.get_user()
    if not user:
        raise HTTPException(503, "No user has been seeded yet.")
    _name, salt_hex, _verifier, iterations = user
    return {
        "salt": salt_hex,
        "iterations": iterations,
        "challenge": auth.new_challenge(),
    }


# Sync def: FastAPI runs it in the threadpool, so PBKDF2 does not stall the
# event loop (and with it the SSE stream) while it runs.
@router.post("/login")
def login(body: LoginRequest, request: Request):
    ip = _client_ip(request)
    if auth.is_locked_out(ip):
        logger.warning("Login locked out for %s", ip)
        raise HTTPException(429, "Too many failed attempts. Try again later.")

    if not auth.verify_login(body.username, body.challenge, body.proof):
        auth.record_failure(ip)
        time.sleep(0.5)
        logger.warning("Failed login for '%s' from %s", body.username, ip)
        raise HTTPException(401, "Invalid username or password")

    auth.clear_failures(ip)
    return {
        "session_id": auth.create_session(),
        # The client signs with a timestamp, so it needs to know how far its
        # own clock is from ours. Without this, a skewed clock looks like a
        # permanent 401 and is miserable to debug.
        "server_time": time.time(),
        "expires_in": SESSION_TTL_SECONDS,
        "signature_window": SIGNATURE_WINDOW_SECONDS,
    }


@router.post("/logout")
def logout(request: Request):
    """Signed like any other route, so a sniffed session id cannot be used to
    log the real user out. A client that has lost its key just drops its local
    state; the orphaned session is unusable and expires on its own."""
    auth.delete_session(request.headers.get("X-Auth-Session"))
    return {"ok": True}


@router.get("/me")
def me():
    """Reached only when the middleware has already verified the signature."""
    return {"authenticated": True, "allow_process_kill": ALLOW_PROCESS_KILL}
