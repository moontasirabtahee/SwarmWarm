"""
Password hashing (bcrypt).

Uses the `bcrypt` library directly with a SHA-256 pre-hash. The pre-hash lets us
accept passwords of any length (bcrypt itself silently truncates at 72 bytes) while
keeping the full entropy of the input. This replaces the weaker `sha256_crypt` scheme
and avoids the passlib 1.7.x + bcrypt 4/5 backend incompatibility.
"""
import base64
import hashlib

import bcrypt


def _prehash(password: str) -> bytes:
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(digest)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prehash(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    if not password or not hashed:
        return False
    try:
        return bcrypt.checkpw(_prehash(password), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False
