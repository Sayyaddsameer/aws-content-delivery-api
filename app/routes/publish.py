"""
POST /assets/{asset_id}/publish
Uploads a new version of an asset, creates an AssetVersion record,
updates the parent asset's ETag, and triggers CDN cache invalidation.
"""

import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

from app.database import get_pool
from app.storage import upload_object
from app.cdn import invalidate_paths
from app.utils.etag import generate_etag

router = APIRouter()


@router.post("/assets/{asset_id}/publish")
async def publish_asset(asset_id: str, file: UploadFile = File(...)):
    # Verify asset exists
    pool = await get_pool()
    async with pool.acquire() as conn:
        asset = await conn.fetchrow("SELECT * FROM assets WHERE id = $1", asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found.")

    # Read new file, compute ETag
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    new_etag = generate_etag(data)
    mime_type = file.content_type or asset["mime_type"]
    filename = file.filename or asset["filename"]
    size_bytes = len(data)

    version_id = str(uuid.uuid4())
    version_key = f"assets/{asset_id}/versions/{version_id}/{filename}"

    # Upload versioned file to S3/MinIO
    upload_object(key=version_key, data=data, content_type=mime_type)

    # Atomically create version + update asset
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Insert new asset_version
            await conn.execute(
                """
                INSERT INTO asset_versions (id, asset_id, object_storage_key, etag)
                VALUES ($1, $2, $3, $4)
                """,
                version_id, asset_id, version_key, new_etag,
            )
            # Update parent asset
            updated = await conn.fetchrow(
                """
                UPDATE assets
                SET current_version_id = $1,
                    etag = $2,
                    size_bytes = $3,
                    mime_type = $4,
                    filename = $5,
                    updated_at = NOW()
                WHERE id = $6
                RETURNING *
                """,
                version_id, new_etag, size_bytes, mime_type, filename, asset_id,
            )

    # Invalidate CDN cache for the mutable download URL
    invalidate_paths([f"/assets/{asset_id}/download"])

    return JSONResponse(
        status_code=200,
        content={
            "id": str(updated["id"]),
            "filename": updated["filename"],
            "mime_type": updated["mime_type"],
            "size_bytes": updated["size_bytes"],
            "etag": updated["etag"],
            "current_version_id": str(updated["current_version_id"]),
            "is_private": updated["is_private"],
            "updated_at": updated["updated_at"].isoformat(),
            "version": {
                "id": version_id,
                "object_storage_key": version_key,
                "public_url": f"/assets/public/{version_id}",
            },
        },
    )
