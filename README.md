# AWS Content Delivery API

A production-grade content delivery API built with **Python 3.11 + FastAPI**, designed for high-performance asset serving via AWS CloudFront CDN. Implements full HTTP caching (ETags, Cache-Control, 304 Not Modified), immutable content versioning, and secure time-limited private access tokens.

---

## Features

| Feature | Detail |
|---|---|
| **ETag-based caching** | SHA-256 content hash stored on upload, never recalculated |
| **Conditional GET** | `If-None-Match` → `304 Not Modified` when content unchanged |
| **Immutable versioning** | `/assets/public/{version_id}` with `Cache-Control: max-age=31536000, immutable` |
| **Private assets** | Temporary tokens (256-bit entropy, configurable TTL) |
| **CDN integration** | AWS CloudFront cache invalidation on publish |
| **Origin shielding** | Blocks direct traffic when running behind CloudFront |
| **Local dev** | MinIO (S3-compatible) + PostgreSQL via Docker Compose |

---

## Quick Start

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop) (includes Docker Compose)
- Python 3.11+

### 1. Clone & configure

```bash
cd aws-content-delivery-api
cp .env.example .env
# Edit .env if needed (defaults work out of the box locally)
```

### 2. Start everything

```bash
docker-compose up --build
```

API: `http://localhost:3000`
MinIO Console: `http://localhost:9001` (user: `minioadmin` / pass: `minioadmin`)
API Docs (Swagger): `http://localhost:3000/docs`

### 3. Run tests

```bash
docker-compose run --rm app pytest tests/ -v
```

### 4. Run benchmark

```bash
docker-compose run --rm app python scripts/run_benchmark.py
```

---

## Manual API Testing

```bash
# Upload a file
curl -X POST -F "file=@./myfile.jpg" http://localhost:3000/assets/upload

# Download (200 OK)
curl -v http://localhost:3000/assets/{id}/download

# Conditional GET — 304 if ETag matches
curl -v -H 'If-None-Match: "paste-etag-here"' http://localhost:3000/assets/{id}/download

# HEAD — headers only, no body
curl -I http://localhost:3000/assets/{id}/download

# Publish new version
curl -X POST -F "file=@./myfile-v2.jpg" http://localhost:3000/assets/{id}/publish

# Immutable public version
curl -v http://localhost:3000/assets/public/{version_id}

# Private access token (insert token into DB first)
curl -v http://localhost:3000/assets/private/{token}
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | postgres://… | PostgreSQL connection string |
| `S3_ENDPOINT_URL` | http://minio:9000 | S3/MinIO endpoint |
| `S3_BUCKET_NAME` | cdn-assets | Bucket name |
| `AWS_ACCESS_KEY_ID` | minioadmin | S3 credentials |
| `AWS_SECRET_ACCESS_KEY` | minioadmin | S3 credentials |
| `AWS_REGION` | us-east-1 | AWS region |
| `CDN_ENABLED` | false | Enable real CloudFront invalidation |
| `CDN_SECRET` | change-me | Shared secret header value for origin shield |
| `CLOUDFRONT_DISTRIBUTION_ID` | — | CloudFront distribution ID (prod only) |
| `ORIGIN_SHIELD_ENABLED` | false | Block non-CDN traffic (enable in prod) |
| `TOKEN_TTL_SECONDS` | 3600 | Private access token lifetime |

---

## Project Structure

```
aws-content-delivery-api/
├── app/
│   ├── main.py          # FastAPI app entry point
│   ├── config.py        # Settings (pydantic-settings)
│   ├── database.py      # asyncpg pool + migration runner
│   ├── storage.py       # S3/MinIO operations
│   ├── cdn.py           # CloudFront invalidation
│   ├── utils/
│   │   ├── etag.py      # SHA-256 ETag generation
│   │   └── token.py     # Secure token generation
│   ├── middleware/
│   │   └── origin_shield.py
│   └── routes/
│       ├── upload.py    # POST /assets/upload
│       ├── download.py  # GET|HEAD /assets/{id}/download
│       ├── publish.py   # POST /assets/{id}/publish
│       ├── public.py    # GET /assets/public/{version_id}
│       └── private.py   # GET /assets/private/{token}
├── tests/
│   ├── unit/            # ETag + token unit tests
│   └── integration/     # Full endpoint integration tests
├── scripts/
│   └── run_benchmark.py
├── docs/
│   ├── ARCHITECTURE.md
│   ├── API_DOCS.md
│   └── PERFORMANCE.md
├── db/migrations/001_init.sql
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
├── submission.yml
└── README.md
```

---

## Production Deployment (AWS)

1. **RDS PostgreSQL** → update `DATABASE_URL`
2. **AWS S3** → set real `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, remove `S3_ENDPOINT_URL`
3. **CloudFront** → set `CLOUDFRONT_DISTRIBUTION_ID`, `CDN_ENABLED=true`
4. **Origin Shield** → add `X-CDN-Secret` as CloudFront custom origin header, set `ORIGIN_SHIELD_ENABLED=true`, set `CDN_SECRET`

See `docs/ARCHITECTURE.md` for detailed architecture diagrams.
