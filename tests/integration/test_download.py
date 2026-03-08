"""
Integration tests for GET and HEAD /assets/{asset_id}/download.
Tests 200 response, caching headers, ETag correctness, and
conditional GET returning 304 Not Modified.
"""

import io
from tests.conftest import FAKE_CONTENT
from app.utils.etag import generate_etag


def _upload(client):
    resp = client.post(
        "/assets/upload",
        files={"file": ("doc.txt", io.BytesIO(FAKE_CONTENT), "text/plain")},
    )
    assert resp.status_code == 201
    return resp.json()


def test_download_returns_200(client):
    asset = _upload(client)
    resp = client.get(f"/assets/{asset['id']}/download")
    assert resp.status_code == 200


def test_download_has_etag_header(client):
    asset = _upload(client)
    resp = client.get(f"/assets/{asset['id']}/download")
    assert "etag" in resp.headers
    expected = f'"{generate_etag(FAKE_CONTENT)}"'
    assert resp.headers["etag"] == expected


def test_download_has_cache_control(client):
    asset = _upload(client)
    resp = client.get(f"/assets/{asset['id']}/download")
    cc = resp.headers.get("cache-control", "")
    assert "public" in cc or "private" in cc  # at minimum a directive is set


def test_download_has_last_modified(client):
    asset = _upload(client)
    resp = client.get(f"/assets/{asset['id']}/download")
    assert "last-modified" in resp.headers


def test_download_returns_304_on_matching_etag(client):
    asset = _upload(client)
    etag = f'"{asset["etag"]}"'
    resp = client.get(
        f"/assets/{asset['id']}/download",
        headers={"If-None-Match": etag},
    )
    assert resp.status_code == 304
    assert resp.content == b""


def test_download_returns_200_on_mismatched_etag(client):
    asset = _upload(client)
    resp = client.get(
        f"/assets/{asset['id']}/download",
        headers={"If-None-Match": '"outdated-etag-value"'},
    )
    assert resp.status_code == 200


def test_download_404_for_unknown_id(client):
    resp = client.get("/assets/00000000-0000-0000-0000-000000000000/download")
    assert resp.status_code == 404


def test_head_returns_200_no_body(client):
    asset = _upload(client)
    resp = client.head(f"/assets/{asset['id']}/download")
    assert resp.status_code == 200
    assert resp.content == b""
    assert "etag" in resp.headers
    assert "cache-control" in resp.headers
    assert "last-modified" in resp.headers
