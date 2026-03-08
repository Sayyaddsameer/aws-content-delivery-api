# Architecture — AWS Content Delivery API

## Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        INTERNET / CLIENTS                        │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   AWS CloudFront (CDN Edge)                      │
│  ┌─────────────────┐  ┌──────────────────┐  ┌───────────────┐  │
│  │  Public Cache   │  │  Immutable Cache  │  │ Private Pass- │  │
│  │  s-maxage=3600  │  │  max-age=31536000 │  │ through       │  │
│  └────────┬────────┘  └────────┬──────────┘  └───────┬───────┘  │
└───────────┼────────────────────┼────────────────────-┼──────────┘
            │  Cache MISS        │  Cache MISS          │ Always
            │  (adds X-CDN-Secret│  (adds X-CDN-Secret) │ origin
            ▼                    ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│              FastAPI Origin Server (Python 3.11)                 │
│                                                                  │
│  [Origin Shield Middleware] → validates X-CDN-Secret header      │
│                                                                  │
│  POST /assets/upload          → S3 upload + DB insert            │
│  GET|HEAD /assets/{id}/dl     → Conditional GET (ETag/304)       │
│  POST /assets/{id}/publish    → Version + CDN invalidation       │
│  GET /assets/public/{ver_id}  → Immutable versioned content      │
│  GET /assets/private/{token}  → Token validation + serve         │
└──────────────┬──────────────────────────┬───────────────────────┘
               │                          │
               ▼                          ▼
   ┌────────────────────┐      ┌─────────────────────┐
   │  PostgreSQL (RDS)  │      │   AWS S3 / MinIO    │
   │                    │      │                     │
   │  assets            │      │  assets/{id}/file   │
   │  asset_versions    │      │  assets/{id}/ver/   │
   │  access_tokens     │      │                     │
   └────────────────────┘      └─────────────────────┘
```

---

## Component Responsibilities

### FastAPI App (`app/`)
- **Routing**: All 6 endpoints
- **ETag logic**: Reads stored SHA-256 hash from DB, compares with `If-None-Match` header
- **Cache-Control**: Sets headers based on asset type (public/private/immutable)
- **Token validation**: Checks token exists and `expires_at > NOW()`

### PostgreSQL
Stores metadata only (no file content):
- `assets`: core record, ETag, MIME type, size, current version pointer
- `asset_versions`: immutable snapshots with their own S3 keys and ETags
- `access_tokens`: short-lived tokens for private content

### AWS S3 / MinIO
- All binary content stored here
- Public bucket for public/versioned assets
- Objects served via API proxy (not directly exposed)

### AWS CloudFront
- Caches public asset responses at edge locations
- Configured to forward and honor `Cache-Control` headers from origin
- Custom origin header `X-CDN-Secret` added to all origin requests
- Cache invalidation triggered by `POST /assets/{id}/publish`

---

## HTTP Caching Strategy

| Endpoint | Cache-Control | ETag | Invalidation |
|---|---|---|---|
| `GET /assets/{id}/download` (public) | `public, s-maxage=3600, max-age=60` | On publish (CDN purge) |
| `GET /assets/{id}/download` (private) | `private, no-store, no-cache` | N/A |
| `GET /assets/public/{version_id}` | `public, max-age=31536000, immutable` | Never (immutable URL) |
| `GET /assets/private/{token}` | `private, no-store, no-cache, must-revalidate` | Token TTL handles it |

### ETag Flow
```
Upload/Publish:
  file bytes → SHA-256 → hex digest → stored in assets.etag

Request:
  Client sends: If-None-Match: "abc123..."
  Server reads: assets.etag from DB
  Match?  → 304 Not Modified (empty body, headers only)
  No match → 200 OK + file content from S3
```

---

## Security Design

| Control | Implementation |
|---|---|
| Origin shielding | `X-CDN-Secret` header validated by middleware |
| Private tokens | `secrets.token_hex(32)` = 256-bit entropy |
| Token expiry | DB `expires_at` checked on every request |
| No token in logs | Tokens only in URL path, not query params |
| S3 private | Bucket is not publicly accessible; API proxies content |
