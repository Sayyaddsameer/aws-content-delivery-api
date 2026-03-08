"""
Integration tests for POST /assets/upload
"""

import io
from tests.conftest import FAKE_CONTENT


def test_upload_returns_201(client):
    response = client.post(
        "/assets/upload",
        files={"file": ("test.txt", io.BytesIO(FAKE_CONTENT), "text/plain")},
    )
    assert response.status_code == 201


def test_upload_returns_id_and_etag(client):
    response = client.post(
        "/assets/upload",
        files={"file": ("test.txt", io.BytesIO(FAKE_CONTENT), "text/plain")},
    )
    body = response.json()
    assert "id" in body
    assert "etag" in body
    assert len(body["etag"]) == 64  # SHA-256 hex


def test_upload_returns_correct_metadata(client):
    response = client.post(
        "/assets/upload",
        files={"file": ("hello.txt", io.BytesIO(FAKE_CONTENT), "text/plain")},
    )
    body = response.json()
    assert body["filename"] == "hello.txt"
    assert body["mime_type"] == "text/plain"
    assert body["size_bytes"] == len(FAKE_CONTENT)


def test_upload_empty_file_returns_400(client):
    response = client.post(
        "/assets/upload",
        files={"file": ("empty.txt", io.BytesIO(b""), "text/plain")},
    )
    assert response.status_code == 400
