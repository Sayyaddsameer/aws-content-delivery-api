# API Documentation — AWS Content Delivery API

Base URL: `http://localhost:3000` (local) | `https://your-cloudfront.com` (production)

---

## POST /assets/upload

Upload a new asset. Accepts `multipart/form-data` with a `file` field.

**Request**
```
POST /assets/upload
Content-Type: multipart/form-data

file: <binary file data>
```

**Response: 201 Created**
```json
{
  "id": "a1b2c3d4-...",
  "filename": "photo.jpg",
  "mime_type": "image/jpeg",
  "size_bytes": 204800,
  "etag": "e3b0c44298fc1c149afb...",
  "object_storage_key": "assets/a1b2c3d4.../photo.jpg",
  "is_private": false,
  "created_at": "2026-03-02T05:00:00+00:00",
  "updated_at": "2026-03-02T05:00:00+00:00"
}
```

**Errors**: `400` empty file

---

## GET /assets/{id}/download

Download an asset. Supports conditional GET via `If-None-Match`.

**Request Headers (optional)**
```
If-None-Match: "e3b0c44298fc1c149afb..."
```

**Response: 200 OK**
```
Content-Type: image/jpeg
Content-Length: 204800
ETag: "e3b0c44298fc1c149afb..."
Last-Modified: Mon, 02 Mar 2026 05:00:00 GMT
Cache-Control: public, s-maxage=3600, max-age=60

<binary file content>
```

**Response: 304 Not Modified** (when ETag matches)
```
ETag: "e3b0c44298fc1c149afb..."
Cache-Control: public, s-maxage=3600, max-age=60
Last-Modified: Mon, 02 Mar 2026 05:00:00 GMT

(empty body)
```

**Errors**: `404` asset not found

---

## HEAD /assets/{id}/download

Same as GET but returns headers only (no body). Use to check ETag without downloading content.

**Response: 200 OK**
```
ETag: "e3b0c44298fc1c149afb..."
Last-Modified: Mon, 02 Mar 2026 05:00:00 GMT
Cache-Control: public, s-maxage=3600, max-age=60
Content-Type: image/jpeg
Content-Length: 204800

(no body)
```

---

## POST /assets/{id}/publish

Publish a new version of an existing asset. Triggers CDN cache invalidation.

**Request**
```
POST /assets/uuid/publish
Content-Type: multipart/form-data

file: <new binary file data>
```

**Response: 200 OK**
```json
{
  "id": "a1b2c3d4-...",
  "filename": "photo-v2.jpg",
  "mime_type": "image/jpeg",
  "size_bytes": 307200,
  "etag": "new-sha256-hash...",
  "current_version_id": "v1b2c3d4-...",
  "is_private": false,
  "updated_at": "2026-03-02T06:00:00+00:00",
  "version": {
    "id": "v1b2c3d4-...",
    "object_storage_key": "assets/a1b2c3d4.../versions/.../photo-v2.jpg",
    "public_url": "/assets/public/v1b2c3d4-..."
  }
}
```

**Errors**: `404` asset not found, `400` empty file

---

## GET /assets/public/{version_id}

Serve an immutable asset version. Designed for aggressive CDN caching.

**Response: 200 OK**
```
Content-Type: image/jpeg
Content-Length: 307200
ETag: "new-sha256-hash..."
Last-Modified: Mon, 02 Mar 2026 06:00:00 GMT
Cache-Control: public, max-age=31536000, immutable

<binary file content>
```

**Errors**: `404` version not found

> **Note**: Because Cache-Control is `immutable`, CDN will serve this from edge for 1 year without revalidating. When you publish a new version, you get a new `version_id` URL — old URLs remain cached indefinitely.

---

## GET /assets/private/{token}

Access a private asset using a temporary access token. Token must exist in DB and not be expired.

**Response: 200 OK** (valid token)
```
Content-Type: application/pdf
Content-Length: 102400
ETag: "private-sha256-hash..."
Last-Modified: Mon, 02 Mar 2026 05:00:00 GMT
Cache-Control: private, no-store, no-cache, must-revalidate

<binary file content>
```

**Response: 401 Unauthorized** (invalid or expired token)
```json
{"detail": "Access token has expired."}
```

---

## Health Check

```
GET /health
→ 200 OK  {"status": "ok"}
```

---

## Generating Access Tokens

Use the utility directly in Python:
```python
from app.utils.token import generate_token, token_expires_at
import asyncpg, asyncio

async def create_token(asset_id: str):
    conn = await asyncpg.connect("postgresql://...")
    token = generate_token()
    expires = token_expires_at()
    await conn.execute(
        "INSERT INTO access_tokens (token, asset_id, expires_at) VALUES ($1, $2, $3)",
        token, asset_id, expires
    )
    return token

token = asyncio.run(create_token("your-asset-uuid-here"))
print(f"Access URL: /assets/private/{token}")
```
