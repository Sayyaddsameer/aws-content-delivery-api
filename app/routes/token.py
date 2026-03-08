"""
POST /assets/{asset_id}/token
Generates a cryptographically secure access token for a private asset.
Returns the token and its expiry. Token is valid for TOKEN_TTL_SECONDS.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.database import get_pool
from app.utils.token import generate_token, token_expires_at

router = APIRouter()


@router.post("/assets/{asset_id}/token", status_code=201)
async def create_access_token(asset_id: str):
    """
    Create a time-limited access token for a private asset.

    The token is a 256-bit (64 hex char) cryptographically secure random value.
    Use it to access the asset via GET /assets/private/{token}.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        asset = await conn.fetchrow(
            "SELECT id FROM assets WHERE id = $1", asset_id
        )

    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found.")

    token = generate_token()
    expires = token_expires_at()

    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO access_tokens (token, asset_id, expires_at) VALUES ($1, $2, $3)",
            token, asset_id, expires,
        )

    return JSONResponse(
        status_code=201,
        content={
            "token": token,
            "asset_id": str(asset_id),
            "expires_at": expires.isoformat(),
            "access_url": f"/assets/private/{token}",
        },
    )
