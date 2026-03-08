"""
pytest conftest: shared fixtures for unit and integration tests.

The integration tests spin up a TestClient against the real FastAPI app,
use an in-process database (set via DATABASE_URL env var, defaults to
the docker postgres), and mock S3 calls so no real MinIO is needed.
"""

import io
import os
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

import pytest
import asyncpg
from fastapi.testclient import TestClient

# Point at test DB (override in CI via env)
os.environ.setdefault("DATABASE_URL", "postgresql://cdnuser:cdnpass@postgres:5432/cdndb")
os.environ.setdefault("S3_ENDPOINT_URL", "http://minio:9000")
os.environ.setdefault("S3_BUCKET_NAME", "cdn-assets")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "minioadmin")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "minioadmin")
os.environ.setdefault("CDN_ENABLED", "false")
os.environ.setdefault("ORIGIN_SHIELD_ENABLED", "false")

from app.main import app


# ── S3 Mock ──────────────────────────────────────────────────────────────────

FAKE_CONTENT = b"Hello, CDN world! This is test file content."


@pytest.fixture(autouse=True)
def mock_s3(monkeypatch):
    """Mock all storage calls so tests don't need a real MinIO."""
    monkeypatch.setattr("app.routes.upload.upload_object", lambda **kw: None)
    monkeypatch.setattr("app.routes.download.download_object", lambda key: FAKE_CONTENT)
    monkeypatch.setattr("app.routes.publish.upload_object", lambda **kw: None)
    monkeypatch.setattr("app.routes.public.download_object", lambda key: FAKE_CONTENT)
    monkeypatch.setattr("app.routes.private.download_object", lambda key: FAKE_CONTENT)
    monkeypatch.setattr("app.cdn.invalidate_paths", lambda paths: None)


# ── DB Fixture ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


# ── Helpers exposed to tests ─────────────────────────────────────────────────

SAMPLE_FILE = ("test.txt", io.BytesIO(FAKE_CONTENT), "text/plain")
