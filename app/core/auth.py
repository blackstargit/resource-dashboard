"""
app/core/auth.py
================
Single-user authentication designed to survive being served over plain HTTP.

Nothing secret is ever transmitted. The password is turned into a `verifier`
(PBKDF2-HMAC-SHA256) on the client; login proves knowledge of that verifier
against a server-issued challenge; and every subsequent request carries an
HMAC signature over (method, path, timestamp, nonce) rather than a bearer
token. A passive eavesdropper therefore learns nothing replayable.

ponytail: this is the ceiling for plain HTTP. An ACTIVE attacker who can
modify traffic simply rewrites the served JavaScript and takes everything.
Only TLS fixes that -- see README "Serving over plain HTTP".
"""
import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager

from app.core.config import (
    ADMIN_PASSWORD,
    ADMIN_USERNAME,
    DB_PATH,
    LOGIN_MAX_FAILURES,
    LOGIN_WINDOW_SECONDS,
    PBKDF2_ITERATIONS,
    SESSION_TTL_SECONDS,
    SIGNATURE_WINDOW_SECONDS,
)
from app.core.logging import get_logger

logger = get_logger("core.auth")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id         INTEGER PRIMARY KEY CHECK (id = 1),
    username   TEXT NOT NULL,
    salt       TEXT NOT NULL,
    verifier   TEXT NOT NULL,
    iterations INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    id         TEXT PRIMARY KEY,
    expires_at REAL NOT NULL
);
"""


@contextmanager
def _db():
    """Yield a short-lived connection. New per call so any thread can use it."""
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _db() as conn:
        conn.executescript(SCHEMA)


# -- Verifier -----------------------------------------------------------------
# The client derives the same value from the password, so both sides hold it
# without it ever crossing the wire. PBKDF2 rather than scrypt because the
# browser has to compute it too, and `crypto.subtle` is unavailable over plain
# HTTP -- the frontend uses @noble/hashes, whose PBKDF2 is the practical choice.
def derive_verifier(password: str, salt_hex: str, iterations: int) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt_hex), iterations, dklen=32
    )


def get_user() -> tuple[str, str, str, int] | None:
    """Return (username, salt_hex, verifier_hex, iterations) or None."""
    with _db() as conn:
        return conn.execute(
            "SELECT username, salt, verifier, iterations FROM users WHERE id = 1"
        ).fetchone()


# -- Seeding ------------------------------------------------------------------
def seed_admin(username: str | None = None, password: str | None = None) -> str:
    """
    Create or update the single user from ADMIN_USERNAME / ADMIN_PASSWORD.
    Idempotent. Changing the password revokes every existing session.
    """
    init_db()
    username = username or ADMIN_USERNAME
    password = password or ADMIN_PASSWORD
    row = get_user()

    if not username or not password:
        if row:
            return "kept existing user (no ADMIN_USERNAME/ADMIN_PASSWORD set)"
        raise SystemExit(
            "No user exists and ADMIN_USERNAME/ADMIN_PASSWORD are not set. "
            "Set both in .env, then run: uv run python seed.py"
        )

    if len(password) < 12:
        raise SystemExit("ADMIN_PASSWORD must be at least 12 characters.")

    if row:
        name, salt_hex, verifier_hex, iters = row
        unchanged = (
            name == username
            and iters == PBKDF2_ITERATIONS
            and hmac.compare_digest(
                derive_verifier(password, salt_hex, iters),
                bytes.fromhex(verifier_hex),
            )
        )
        if unchanged:
            return "user '%s' already up to date" % username

    salt_hex = secrets.token_bytes(16).hex()
    verifier = derive_verifier(password, salt_hex, PBKDF2_ITERATIONS)
    with _db() as conn:
        conn.execute(
            "INSERT INTO users (id, username, salt, verifier, iterations) "
            "VALUES (1, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET "
            "username = excluded.username, salt = excluded.salt, "
            "verifier = excluded.verifier, iterations = excluded.iterations",
            (username, salt_hex, verifier.hex(), PBKDF2_ITERATIONS),
        )
        conn.execute("DELETE FROM sessions")
    return "user '%s' written (all sessions revoked)" % username


# -- Login challenge ----------------------------------------------------------
# ponytail: in-memory, per-process. Fine for one user on one container.
CHALLENGE_TTL = 60.0
_challenges: dict[str, float] = {}


def new_challenge() -> str:
    now = time.time()
    for c, exp in list(_challenges.items()):
        if exp < now:
            del _challenges[c]
    challenge = secrets.token_hex(32)
    _challenges[challenge] = now + CHALLENGE_TTL
    return challenge


def verify_login(username: str, challenge: str, proof: str) -> bool:
    """Check proof == HMAC(verifier, challenge). Burns the challenge either way."""
    expires = _challenges.pop(challenge, None)
    if expires is None or expires < time.time():
        return False
    row = get_user()
    if not row:
        return False
    name, _salt, verifier_hex, _iters = row
    expected = hmac.new(
        bytes.fromhex(verifier_hex), challenge.encode(), hashlib.sha256
    ).hexdigest()
    # Both compared regardless, so a wrong username costs the same time.
    ok_user = hmac.compare_digest(username, name)
    ok_proof = hmac.compare_digest(expected, proof)
    return ok_user and ok_proof


# -- Sessions -----------------------------------------------------------------
def create_session() -> str:
    """
    Return a session id. It is public: it travels in the clear on every request
    and is useless on its own. The matching key is derived, never sent.
    """
    session_id = secrets.token_urlsafe(24)
    with _db() as conn:
        conn.execute(
            "INSERT INTO sessions (id, expires_at) VALUES (?, ?)",
            (session_id, time.time() + SESSION_TTL_SECONDS),
        )
        conn.execute("DELETE FROM sessions WHERE expires_at < ?", (time.time(),))
    return session_id


def session_key(session_id: str, verifier_hex: str) -> bytes:
    return hmac.new(
        bytes.fromhex(verifier_hex), session_id.encode(), hashlib.sha256
    ).digest()


def delete_session(session_id: str | None) -> None:
    if session_id:
        with _db() as conn:
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))


# -- Request signatures -------------------------------------------------------
# ponytail: in-memory replay cache, per-process. Bounded by the signature
# window so it self-prunes; move to SQLite only if this ever runs >1 worker.
_seen_nonces: dict[str, float] = {}


def sign(key: bytes, method: str, path: str, ts: str, nonce: str) -> str:
    """
    Query strings are deliberately not signed -- nothing dangerous lives there
    (they only select sort order and poll interval). The one destructive route,
    DELETE .../processes/{pid}, carries its target in the path, which is signed.
    """
    msg = ("%s\n%s\n%s\n%s" % (method.upper(), path, ts, nonce)).encode()
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def verify_request(
    session_id: str | None,
    method: str,
    path: str,
    ts: str | None,
    nonce: str | None,
    sig: str | None,
) -> bool:
    if not (session_id and ts and nonce and sig):
        return False

    now = time.time()
    try:
        if abs(now - float(ts)) > SIGNATURE_WINDOW_SECONDS:
            return False
    except ValueError:
        return False

    for seen_nonce, seen_at in list(_seen_nonces.items()):
        if now - seen_at > SIGNATURE_WINDOW_SECONDS * 2:
            del _seen_nonces[seen_nonce]
    if nonce in _seen_nonces:
        logger.warning("Replayed nonce rejected for %s %s", method, path)
        return False

    with _db() as conn:
        row = conn.execute(
            "SELECT expires_at FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
    if not row or row[0] < now:
        return False

    user = get_user()
    if not user:
        return False

    expected = sign(session_key(session_id, user[2]), method, path, ts, nonce)
    if not hmac.compare_digest(expected, sig):
        return False

    _seen_nonces[nonce] = now
    return True


# -- Login throttling ---------------------------------------------------------
# ponytail: in-memory, per-process. See note above.
_failures: dict[str, list[float]] = {}


def record_failure(ip: str) -> None:
    _failures.setdefault(ip, []).append(time.time())


def is_locked_out(ip: str) -> bool:
    cutoff = time.time() - LOGIN_WINDOW_SECONDS
    recent = [t for t in _failures.get(ip, []) if t > cutoff]
    _failures[ip] = recent
    return len(recent) >= LOGIN_MAX_FAILURES


def clear_failures(ip: str) -> None:
    _failures.pop(ip, None)
