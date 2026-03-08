"""
Integration tests for GET /assets/private/{token}

Tests valid token access, expired token (401), invalid token (401),
and correct Cache-Control header.
"""

import io
from datetime import datetime, timezone, timedelta
from tests.conftest import FAKE_CONTENT
from app.utils.token import generate_token


def _upload(client):
    resp = client.post(
        "/assets/upload",
        files={"file": ("private.pdf", io.BytesIO(FAKE_CONTENT), "application/pdf")},
    )
    return resp.json()


async def _insert_token(asset_id: str, expires_at: datetime) -> str:
    """Directly insert an access token into DB for testing."""
    from app.database import get_pool
    token = generate_token()
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO access_tokens (token, asset_id, expires_at) VALUES ($1, $2, $3)",
            token, asset_id, expires_at,
        )
    return token


def _insert_token_sync(asset_id: str, expires_at: datetime) -> str:
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool_exec:
                future = pool_exec.submit(asyncio.run, _insert_token(asset_id, expires_at))
                return future.result()
        else:
            return loop.run_until_complete(_insert_token(asset_id, expires_at))
    except RuntimeError:
        return asyncio.run(_insert_token(asset_id, expires_at))


def test_private_valid_token_returns_200(client):
    asset = _upload(client)
    expires = datetime.now(timezone.utc) + timedelta(hours=1)
    token = _insert_token_sync(asset["id"], expires)

    resp = client.get(f"/assets/private/{token}")
    assert resp.status_code == 200


def test_private_valid_token_cache_control(client):
    asset = _upload(client)
    expires = datetime.now(timezone.utc) + timedelta(hours=1)
    token = _insert_token_sync(asset["id"], expires)

    resp = client.get(f"/assets/private/{token}")
    cc = resp.headers.get("cache-control", "")
    assert "private" in cc
    assert "no-store" in cc


def test_private_expired_token_returns_401(client):
    asset = _upload(client)
    expires = datetime.now(timezone.utc) - timedelta(seconds=1)
    token = _insert_token_sync(asset["id"], expires)

    resp = client.get(f"/assets/private/{token}")
    assert resp.status_code == 401


def test_private_invalid_token_returns_401(client):
    resp = client.get("/assets/private/completely-invalid-token-xyz-999")
    assert resp.status_code == 401
