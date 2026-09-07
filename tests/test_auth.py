"""
Smallest check that the auth logic actually holds. Run: uv run python test_auth.py
"""
import hashlib
import hmac
import os
import tempfile
import time

os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")
# Keep the self-check fast; production uses the config default.
os.environ["PBKDF2_ITERATIONS"] = "1000"

from app.core import auth  # noqa: E402  (must follow the env setup above)

PASSWORD = "correct-horse-battery"
auth.seed_admin("admin", PASSWORD)

name, salt, verifier_hex, iters = auth.get_user()
assert name == "admin" and iters == 1000
assert PASSWORD not in verifier_hex, "password must not be recoverable from storage"


def client_login(username, password):
    """Mirror of what the browser does, to prove both sides agree."""
    _n, salt, _v, iterations = auth.get_user()  # served by GET /auth/challenge
    challenge = auth.new_challenge()
    verifier = auth.derive_verifier(password, salt, iterations)
    proof = hmac.new(verifier, challenge.encode(), hashlib.sha256).hexdigest()
    return username, challenge, proof, verifier


# -- Login ---------------------------------------------------------------------
assert auth.verify_login(*client_login("admin", PASSWORD)[:3])
assert not auth.verify_login(*client_login("admin", "wrong-password-xx")[:3])
assert not auth.verify_login(*client_login("root", PASSWORD)[:3])

# A challenge is single-use, so a sniffed proof cannot be replayed.
user, challenge, proof, verifier = client_login("admin", PASSWORD)
assert auth.verify_login(user, challenge, proof)
assert not auth.verify_login(user, challenge, proof), "challenge must burn"

# -- Request signing -----------------------------------------------------------
sid = auth.create_session()
key = auth.session_key(sid, verifier_hex)
assert key == auth.session_key(sid, verifier_hex)

def signed(method, path, ts=None, nonce=None):
    """Sign as the client would, with the key derived from the live session."""
    ts = ts or str(time.time())
    nonce = nonce or os.urandom(8).hex()
    k = auth.session_key(sid, auth.get_user()[2])
    return method, path, ts, nonce, auth.sign(k, method, path, ts, nonce)

assert auth.verify_request(sid, *signed("GET", "/api/v1/auth/me"))

# The signature is bound to the method and the path.
m, p, ts, n, sig = signed("GET", "/api/v1/resources/processes")
assert not auth.verify_request(sid, "DELETE", "/api/v1/resources/processes/1", ts, n, sig)
assert not auth.verify_request(sid, m, "/api/v1/resources/other", ts, n, sig)

# Replay of a captured signature is refused.
m, p, ts, n, sig = signed("GET", "/api/v1/auth/me")
assert auth.verify_request(sid, m, p, ts, n, sig)
assert not auth.verify_request(sid, m, p, ts, n, sig), "nonce must not be reusable"

# Stale timestamps are refused, as are unsigned and wrongly-signed requests.
assert not auth.verify_request(sid, *signed("GET", "/api/v1/auth/me", ts="1"))
assert not auth.verify_request(sid, "GET", "/api/v1/auth/me", None, None, None)
assert not auth.verify_request(sid, "GET", "/api/v1/auth/me", str(time.time()), "x", "bad")

# Knowing the session id alone buys nothing without the derived key.
wrong = auth.sign(b"not-the-key", "GET", "/api/v1/auth/me", str(time.time()), "zz")
assert not auth.verify_request(sid, "GET", "/api/v1/auth/me", str(time.time()), "zz", wrong)

# -- Session lifecycle ---------------------------------------------------------
auth.delete_session(sid)
assert not auth.verify_request(sid, *signed("GET", "/api/v1/auth/me")), "logout must revoke"

sid = auth.create_session()
assert auth.verify_request(sid, *signed("GET", "/api/v1/auth/me"))
auth.seed_admin("admin", "a-brand-new-password")
assert not auth.verify_request(sid, *signed("GET", "/api/v1/auth/me")), (
    "password change must revoke sessions"
)

# -- Lockout -------------------------------------------------------------------
for _ in range(auth.LOGIN_MAX_FAILURES):
    assert not auth.is_locked_out("1.2.3.4")
    auth.record_failure("1.2.3.4")
assert auth.is_locked_out("1.2.3.4")
auth.clear_failures("1.2.3.4")
assert not auth.is_locked_out("1.2.3.4")

print("auth ok")
