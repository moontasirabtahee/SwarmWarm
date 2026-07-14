"""
Opaque token helpers for refresh tokens, email verification, password resets, and
org invitations.

We store only a SHA-256 hash of each token in the database; the raw token is handed
to the user once (cookie/URL) and never persisted, so a database leak does not expose
usable tokens.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone


def generate_token() -> str:
    """A URL-safe, high-entropy opaque token."""
    return secrets.token_urlsafe(32)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def expiry_iso(*, days: int = 0, hours: int = 0, minutes: int = 0) -> str:
    dt = datetime.now(timezone.utc) + timedelta(days=days, hours=hours, minutes=minutes)
    return dt.replace(tzinfo=None).isoformat() + "Z"


def is_expired(iso_ts: str) -> bool:
    """True if the given ISO timestamp is in the past."""
    if not iso_ts:
        return True
    try:
        cleaned = iso_ts.replace("Z", "")
        return datetime.fromisoformat(cleaned) < datetime.utcnow()
    except (ValueError, TypeError):
        return True
