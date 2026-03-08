"""
Cryptographically secure access token generation and validation.
"""

import secrets
from datetime import datetime, timezone

from app.config import settings


def generate_token() -> str:
    """
    Generate a 64-character hexadecimal token (256 bits of entropy).
    Uses secrets.token_hex which is cryptographically secure.
    """
    return secrets.token_hex(32)


def token_expires_at() -> datetime:
    """
    Return the expiry datetime for a newly created token.
    TTL is configurable via TOKEN_TTL_SECONDS env variable.
    """
    from datetime import timedelta
    return datetime.now(timezone.utc) + timedelta(seconds=settings.token_ttl_seconds)


def is_expired(expires_at: datetime) -> bool:
    """
    Return True if the given expiry time is in the past.
    """
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) > expires_at
