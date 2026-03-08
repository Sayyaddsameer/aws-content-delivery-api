"""
Integration tests for POST /assets/{asset_id}/publish
"""

import io
from tests.conftest import FAKE_CONTENT

NEW_CONTENT = b"This is version 2 of the file with updated content."


def _upload(client):
    resp = client.post(
        "/assets/upload",
        files={"file": ("original.txt", io.BytesIO(FAKE_CONTENT), "text/plain")},
    )
    return resp.json()


def test_publish_returns_200(client):
    asset = _upload(client)
    resp = client.post(
        f"/assets/{asset['id']}/publish",
        files={"file": ("v2.txt", io.BytesIO(NEW_CONTENT), "text/plain")},
    )
    assert resp.status_code == 200


def test_publish_updates_etag(client):
    asset = _upload(client)
    old_etag = asset["etag"]
    resp = client.post(
        f"/assets/{asset['id']}/publish",
        files={"file": ("v2.txt", io.BytesIO(NEW_CONTENT), "text/plain")},
    )
    body = resp.json()
    assert body["etag"] != old_etag


def test_publish_creates_version_id(client):
    asset = _upload(client)
    resp = client.post(
        f"/assets/{asset['id']}/publish",
        files={"file": ("v2.txt", io.BytesIO(NEW_CONTENT), "text/plain")},
    )
    body = resp.json()
    assert "version" in body
    assert "id" in body["version"]
    assert "public_url" in body["version"]
    assert body["current_version_id"] == body["version"]["id"]


def test_publish_404_for_unknown_asset(client):
    resp = client.post(
        "/assets/00000000-0000-0000-0000-000000000000/publish",
        files={"file": ("v2.txt", io.BytesIO(NEW_CONTENT), "text/plain")},
    )
    assert resp.status_code == 404
