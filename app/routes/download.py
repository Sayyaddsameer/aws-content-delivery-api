"""
GET  /assets/{asset_id}/download  — Download asset with full caching headers.
HEAD /assets/{asset_id}/download  — Same headers, no body.

Supports conditional GET via If-None-Match (ETag) header.
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import Response, StreamingResponse

from app.database import get_pool
from app.storage import download_object
from app.utils.etag import parse_etag_header

router = APIRouter()


def _cache_control(is_private: bool) -> str:
    if is_private:
        return "private, no-store, no-cache, must-revalidate"
    return "public, s-maxage=3600, max-age=60"


async def _get_asset(asset_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM assets WHERE id = $1", asset_id
        )
    if row is None:
        raise HTTPException(status_code=404, detail="Asset not found.")
    return row


@router.get("/assets/{asset_id}/download")
async def download_asset(asset_id: str, request: Request):
    row = await _get_asset(asset_id)

    stored_etag = row["etag"]
    last_modified = row["updated_at"].strftime("%a, %d %b %Y %H:%M:%S GMT")
    cache_control = _cache_control(row["is_private"])

    # ── Conditional GET: If-None-Match ──────────────────────────────
    if_none_match = request.headers.get("if-none-match", "")
    if if_none_match:
        client_etag = parse_etag_header(if_none_match)
        if client_etag == stored_etag:
            return Response(
                status_code=304,
                headers={
                    "ETag": f'"{stored_etag}"',
                    "Cache-Control": cache_control,
                    "Last-Modified": last_modified,
                },
            )

    # ── Full response ────────────────────────────────────────────────
    data = download_object(row["object_storage_key"])
    return Response(
        content=data,
        media_type=row["mime_type"],
        headers={
            "ETag": f'"{stored_etag}"',
            "Last-Modified": last_modified,
            "Cache-Control": cache_control,
            "Content-Length": str(row["size_bytes"]),
        },
    )


@router.head("/assets/{asset_id}/download")
async def head_asset(asset_id: str):
    row = await _get_asset(asset_id)

    stored_etag = row["etag"]
    last_modified = row["updated_at"].strftime("%a, %d %b %Y %H:%M:%S GMT")
    cache_control = _cache_control(row["is_private"])

    return Response(
        status_code=200,
        headers={
            "ETag": f'"{stored_etag}"',
            "Last-Modified": last_modified,
            "Cache-Control": cache_control,
            "Content-Length": str(row["size_bytes"]),
            "Content-Type": row["mime_type"],
        },
    )
