"""
Unit tests for app/utils/token.py
"""

import re
from datetime import datetime, timezone, timedelta
from app.utils.token import generate_token, token_expires_at, is_expired


def test_token_is_64_char_hex():
    token = generate_token()
    assert len(token) == 64
    assert re.fullmatch(r"[0-9a-f]{64}", token)


def test_tokens_are_unique():
    tokens = {generate_token() for _ in range(100)}
    assert len(tokens) == 100  # No collisions


def test_token_expires_at_is_future():
    expires = token_expires_at()
    assert expires > datetime.now(timezone.utc)


def test_is_expired_with_past_date():
    past = datetime.now(timezone.utc) - timedelta(seconds=1)
    assert is_expired(past) is True


def test_is_expired_with_future_date():
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    assert is_expired(future) is False


def test_is_expired_handles_naive_datetime():
    # Naive datetimes (no tzinfo) should be treated as UTC
    naive_past = datetime.utcnow() - timedelta(seconds=10)
    assert is_expired(naive_past) is True
