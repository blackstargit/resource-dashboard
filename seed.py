"""
Seed the single dashboard user from ADMIN_USERNAME / ADMIN_PASSWORD in .env.

    uv run python seed.py

Idempotent. Re-run after changing ADMIN_PASSWORD to rotate the password;
that also revokes every existing login session.
"""
from app.core.auth import seed_admin

if __name__ == "__main__":
    print(seed_admin())
