# Performance Report — AWS Content Delivery API

## Caching Architecture

The system implements a multi-layer caching strategy:

| Layer | Scope | TTL |
|---|---|---|
| CDN Edge (CloudFront) | Public assets | 3600s (s-maxage) |
| CDN Edge (CloudFront) | Versioned immutable assets | 31536000s (1 year) |
| Browser | Public assets | 60s (max-age) |
| Browser | Private assets | None (no-store) |
| Conditional validation | All cacheable assets | ETag-based 304 |

---

## Cache-Control Header Breakdown

### Public Mutable Assets (`GET /assets/{id}/download`)
```
Cache-Control: public, s-maxage=3600, max-age=60
```
- CDN caches for 1 hour (`s-maxage=3600`)
- Browser revalidates after 60 seconds (`max-age=60`)
- CDN cache is **programmatically purged** on `POST /assets/{id}/publish`

### Immutable Versioned Assets (`GET /assets/public/{version_id}`)
```
Cache-Control: public, max-age=31536000, immutable
```
- CDN and browser cache for 1 year
- `immutable` tells browsers **never** to revalidate during TTL
- No cache purge needed — new content = new URL (new `version_id`)

### Private Assets (`GET /assets/private/{token}`)
```
Cache-Control: private, no-store, no-cache, must-revalidate
```
- Never stored by CDN or shared caches
- Browser discards immediately after display

---

## ETag-Based Conditional Requests

Every asset has a **SHA-256 strong ETag** stored in the database at upload time.

**Flow:**
1. First request: server returns `200 OK` + `ETag: "sha256hex"`
2. Client stores ETag → next request sends `If-None-Match: "sha256hex"`
3. Server compares client ETag with DB record
4. Match → `304 Not Modified` (empty body, ~same latency, 0 bandwidth)
5. No match → `200 OK` + new content

**Savings**: For unchanged assets, 304 responses eliminate all bandwidth for the content body. Only response headers are transmitted.

---

## Expected CDN Cache Hit Ratio

Under production load with CloudFront configured:

| Asset Type | Expected CDN Cache Hit Rate |
|---|---|
| Versioned immutable (`/public/{version_id}`) | ~100% after first request per edge |
| Public mutable (`/assets/{id}/download`) | >95% within TTL window |
| Private token (`/assets/private/{token}`) | 0% (bypasses CDN by design) |

**Target: >95% cache hit rate for public assets** — achieved via:
1. Long `s-maxage` for mutable public content
2. 1-year `max-age + immutable` for versioned content
3. CloudFront Origin Shield reducing origin fan-out
4. Programmatic invalidation ensuring correctness

---

## Benchmark Results

Run `docker-compose run --rm app python scripts/run_benchmark.py` to generate results.

The benchmark script measures:
- **Download 200** latency: p50, p95 response time for fresh requests
- **Download 304** latency: p50, p95 for conditional requests with matching ETag
- **Public version** latency: p50, p95 for immutable versioned content
- **Cache-Control correctness**: verifies `immutable` + `max-age=31536000` present on 100% of `/public/` responses
- **304 hit rate**: percentage of conditional requests returning 304 (target: 100% for unchanged assets)

---

## Optimization Notes

1. **ETag pre-computed**: SHA-256 is calculated once on upload and stored in DB. Zero computational overhead on subsequent GET requests.
2. **No S3 HEAD on 304**: When a 304 is returned, no S3 request is made — only a DB lookup for the ETag.
3. **Immutable URLs eliminate invalidation**: New content = new version URL. No CDN purge cost, no stale-content risk.
4. **Origin Shield**: With `ORIGIN_SHIELD_ENABLED=true`, only CloudFront can reach the origin, reducing origin request rate by routing all edge caches through a single shield location.
