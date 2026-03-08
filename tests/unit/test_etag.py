"""
Unit tests for app/utils/etag.py
"""

import hashlib
from app.utils.etag import generate_etag, parse_etag_header


def test_etag_is_sha256_hex():
    data = b"hello world"
    expected = hashlib.sha256(data).hexdigest()
    assert generate_etag(data) == expected


def test_etag_is_deterministic():
    data = b"same content"
    assert generate_etag(data) == generate_etag(data)


def test_etag_different_content_differs():
    assert generate_etag(b"file-v1") != generate_etag(b"file-v2")


def test_etag_empty_bytes():
    etag = generate_etag(b"")
    # SHA-256 of empty string is well-defined
    assert etag == hashlib.sha256(b"").hexdigest()


def test_parse_etag_strips_quotes():
    assert parse_etag_header('"abc123"') == "abc123"


def test_parse_etag_no_quotes():
    assert parse_etag_header("abc123") == "abc123"


def test_parse_etag_strips_whitespace():
    assert parse_etag_header('  "abc123"  ') == "abc123"
