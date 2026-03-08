"""
Integration tests for GET /assets/public/{version_id}
"""

import io
from tests.conftest import FAKE_CONTENT

NEW_CONTENT = b"Versioned immutable content for CDN."


def _upload_and_publish(client):
    upload = client.post(
        "/assets/upload",
        files={"file": ("img.png", io.BytesIO(FAKE_CONTENT), "image/png")},
    )
    asset = upload.json()
    pub = client.post(
        f"/assets/{asset['id']}/publish",
        files={"file": ("img-v2.png", io.BytesIO(NEW_CONTENT), "image/png")},
    )
    return pub.json()


def test_public_version_returns_200(client):
    pub = _upload_and_publish(client)
    version_id = pub["version"]["id"]
    resp = client.get(f"/assets/public/{version_id}")
    assert resp.status_code == 200


def test_public_version_cache_control_immutable(client):
    pub = _upload_and_publish(client)
    version_id = pub["version"]["id"]
    resp = client.get(f"/assets/public/{version_id}")
    cc = resp.headers.get("cache-control", "")
    assert "max-age=31536000" in cc
    assert "immutable" in cc
    assert "public" in cc


def test_public_version_has_etag(client):
    pub = _upload_and_publish(client)
    version_id = pub["version"]["id"]
    resp = client.get(f"/assets/public/{version_id}")
    assert "etag" in resp.headers


def test_public_version_has_last_modified(client):
    pub = _upload_and_publish(client)
    version_id = pub["version"]["id"]
    resp = client.get(f"/assets/public/{version_id}")
    assert "last-modified" in resp.headers


def test_public_version_404_for_unknown(client):
    resp = client.get("/assets/public/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
