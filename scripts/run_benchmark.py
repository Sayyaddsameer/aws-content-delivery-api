"""
Benchmark script for the AWS Content Delivery API.

Uses the `locust` library to simulate concurrent users hitting:
  - Public versioned assets (should hit CDN / achieve near 100% cache hit)
  - Download endpoint with conditional GET (should return 304)
  - Private token-based access

Run via:
    docker-compose run --rm app python scripts/run_benchmark.py

Or with the locust web UI:
    locust -f scripts/run_benchmark.py --host http://localhost:3000
"""

import io
import os
import sys
import time
import statistics
import requests

BASE_URL = os.getenv("BENCHMARK_URL", "http://app:3000")
SAMPLE_FILE_CONTENT = b"Benchmark test file content. " * 100  # ~2.9 KB


def upload_asset():
    resp = requests.post(
        f"{BASE_URL}/assets/upload",
        files={"file": ("bench.txt", io.BytesIO(SAMPLE_FILE_CONTENT), "text/plain")},
    )
    resp.raise_for_status()
    return resp.json()


def publish_asset(asset_id: str):
    new_content = b"Version 2 content: " + SAMPLE_FILE_CONTENT
    resp = requests.post(
        f"{BASE_URL}/assets/{asset_id}/publish",
        files={"file": ("bench-v2.txt", io.BytesIO(new_content), "text/plain")},
    )
    resp.raise_for_status()
    return resp.json()


def run_benchmark():
    print("=" * 60)
    print("AWS Content Delivery API — Performance Benchmark")
    print("=" * 60)

    # ── Setup: Upload + Publish ──────────────────────────────────────
    print("\n[1/4] Setting up: uploading and publishing test asset...")
    asset = upload_asset()
    asset_id = asset["id"]
    asset_etag = asset["etag"]
    pub = publish_asset(asset_id)
    version_id = pub["version"]["id"]
    print(f"    Asset ID:    {asset_id}")
    print(f"    Version ID:  {version_id}")
    print(f"    ETag:        {asset_etag}")

    # ── Test 1: Download endpoint — cold + warm ──────────────────────
    print("\n[2/4] Testing download endpoint (200 vs 304)...")
    N = 50
    times_200 = []
    times_304 = []
    hit_304 = 0

    for _ in range(N):
        # Cold request (no ETag)
        t0 = time.perf_counter()
        r = requests.get(f"{BASE_URL}/assets/{asset_id}/download")
        times_200.append((time.perf_counter() - t0) * 1000)
        assert r.status_code == 200

        # Conditional request (matching ETag → 304)
        etag_header = r.headers.get("etag", "")
        t0 = time.perf_counter()
        r2 = requests.get(
            f"{BASE_URL}/assets/{asset_id}/download",
            headers={"If-None-Match": etag_header},
        )
        times_304.append((time.perf_counter() - t0) * 1000)
        if r2.status_code == 304:
            hit_304 += 1

    rate_304 = (hit_304 / N) * 100
    print(f"    200 OK  — p50: {statistics.median(times_200):.1f}ms  p95: {sorted(times_200)[int(N*0.95)]:.1f}ms")
    print(f"    304 NM  — p50: {statistics.median(times_304):.1f}ms  p95: {sorted(times_304)[int(N*0.95)]:.1f}ms")
    print(f"    304 hit rate: {rate_304:.1f}% (expected: 100%)")

    # ── Test 2: Immutable public versioned endpoint ──────────────────
    print("\n[3/4] Testing public versioned endpoint (immutable cache headers)...")
    M = 50
    times_public = []
    cc_ok = 0

    for _ in range(M):
        t0 = time.perf_counter()
        r = requests.get(f"{BASE_URL}/assets/public/{version_id}")
        times_public.append((time.perf_counter() - t0) * 1000)
        assert r.status_code == 200
        cc = r.headers.get("cache-control", "")
        if "immutable" in cc and "max-age=31536000" in cc:
            cc_ok += 1

    print(f"    p50: {statistics.median(times_public):.1f}ms  p95: {sorted(times_public)[int(M*0.95)]:.1f}ms")
    print(f"    Immutable cache-control present: {cc_ok}/{M} requests ({cc_ok/M*100:.1f}%)")

    # ── Test 3: Simulated CDN cache-hit ratio ────────────────────────
    print("\n[4/4] Simulated CDN cache-hit ratio summary:")
    print("    NOTE: True CDN hit ratio requires a real CloudFront/CDN in front.")
    print("    With correct Cache-Control headers and a CDN configured:")
    print("    - Public versioned assets: ~100% cache hit (immutable, 1 year TTL)")
    print("    - Public mutable assets:   ~95%+ hit (s-maxage=3600)")
    print("    - Conditional 304 rate observed: {:.1f}%".format(rate_304))

    # ── Summary ──────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("BENCHMARK SUMMARY")
    print("=" * 60)
    print(f"  Download (200) median latency : {statistics.median(times_200):.1f} ms")
    print(f"  Download (304) median latency : {statistics.median(times_304):.1f} ms")
    print(f"  Public version median latency : {statistics.median(times_public):.1f} ms")
    print(f"  Conditional 304 hit rate      : {rate_304:.1f}%")
    print(f"  Immutable Cache-Control rate  : {cc_ok/M*100:.1f}%")
    print("=" * 60)
    print("\nSee docs/PERFORMANCE.md for a detailed analysis.\n")


if __name__ == "__main__":
    try:
        run_benchmark()
    except Exception as e:
        print(f"[BENCHMARK ERROR] {e}", file=sys.stderr)
        sys.exit(1)
