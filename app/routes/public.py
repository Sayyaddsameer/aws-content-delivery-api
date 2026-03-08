"""
GET /assets/public/{version_id}
Serves a specific, immutable asset version with aggressive CDN caching.
Cache-Control: public, max-age=31536000, immutable (1 year)
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.database import get_pool
from app.storage import download_object

router = APIRouter()

CACHE_CONTROL_IMMUTABLE = "public, max-age=31536000, immutable"


@router.get("/assets/public/{version_id}")
async def get_public_version(version_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        version = await conn.fetchrow(
            """
            SELECT av.*, a.mime_type, a.filename
            FROM asset_versions av
            JOIN assets a ON a.id = av.asset_id
            WHERE av.id = $1
            """,
            version_id,
        )
    if version is None:
        raise HTTPException(status_code=404, detail="Asset version not found.")

    data = download_object(version["object_storage_key"])
    last_modified = version["created_at"].strftime("%a, %d %b %Y %H:%M:%S GMT")

    return Response(
        content=data,
        media_type=version["mime_type"],
        headers={
            "ETag": f'"{version["etag"]}"',
            "Last-Modified": last_modified,
            "Cache-Control": CACHE_CONTROL_IMMUTABLE,
            "Content-Length": str(len(data)),
        },
    )
