"""
GET /assets/private/{token}
Validates a short-lived access token and serves the associated private asset.
On valid token: 200 with Cache-Control: private, no-store, no-cache, must-revalidate
On invalid/expired token: 401 Unauthorized
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.database import get_pool
from app.storage import download_object
from app.utils.token import is_expired

router = APIRouter()

CACHE_CONTROL_PRIVATE = "private, no-store, no-cache, must-revalidate"


@router.get("/assets/private/{token}")
async def get_private_asset(token: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        token_row = await conn.fetchrow(
            "SELECT * FROM access_tokens WHERE token = $1", token
        )

    if token_row is None:
        raise HTTPException(status_code=401, detail="Invalid or unknown access token.")

    if is_expired(token_row["expires_at"]):
        raise HTTPException(status_code=401, detail="Access token has expired.")

    # Fetch the associated asset
    async with pool.acquire() as conn:
        asset = await conn.fetchrow(
            "SELECT * FROM assets WHERE id = $1", str(token_row["asset_id"])
        )
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found.")

    data = download_object(asset["object_storage_key"])
    last_modified = asset["updated_at"].strftime("%a, %d %b %Y %H:%M:%S GMT")

    return Response(
        content=data,
        media_type=asset["mime_type"],
        headers={
            "ETag": f'"{asset["etag"]}"',
            "Last-Modified": last_modified,
            "Cache-Control": CACHE_CONTROL_PRIVATE,
            "Content-Length": str(len(data)),
        },
    )
