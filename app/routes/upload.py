"""
POST /assets/upload
Accepts a multipart/form-data file upload, stores in S3/MinIO,
computes a strong SHA-256 ETag, and creates an Asset record.
"""

import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

from app.database import get_pool
from app.storage import upload_object
from app.utils.etag import generate_etag

router = APIRouter()


@router.post("/assets/upload", status_code=201)
async def upload_asset(file: UploadFile = File(...)):
    # Read file into memory (suitable for typical asset sizes)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # Compute strong ETag from file content
    etag = generate_etag(data)

    asset_id = str(uuid.uuid4())
    filename = file.filename or "unknown"
    mime_type = file.content_type or "application/octet-stream"
    size_bytes = len(data)
    object_key = f"assets/{asset_id}/{filename}"

    # Upload to S3/MinIO
    upload_object(key=object_key, data=data, content_type=mime_type)

    # Insert into DB
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO assets (id, object_storage_key, filename, mime_type, size_bytes, etag)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id, object_storage_key, filename, mime_type, size_bytes, etag,
                      current_version_id, is_private, created_at, updated_at
            """,
            asset_id, object_key, filename, mime_type, size_bytes, etag,
        )

    return JSONResponse(
        status_code=201,
        content={
            "id": str(row["id"]),
            "filename": row["filename"],
            "mime_type": row["mime_type"],
            "size_bytes": row["size_bytes"],
            "etag": row["etag"],
            "object_storage_key": row["object_storage_key"],
            "is_private": row["is_private"],
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat(),
        },
    )
