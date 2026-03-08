"""
ETag utility: generate a SHA-256 content hash formatted as a strong ETag.
"""

import hashlib


def generate_etag(data: bytes) -> str:
    """
    Compute SHA-256 hash of file bytes and return as a strong ETag string.
    The returned value is the raw hex digest (without quotes).
    Callers must add surrounding quotes when setting the ETag header.

    Example:
        etag = generate_etag(file_bytes)    # "abc123..."
        response.headers["ETag"] = f'"{etag}"'
    """
    return hashlib.sha256(data).hexdigest()


def parse_etag_header(header_value: str) -> str:
    """
    Strip surrounding quotes from an ETag header value.
    E.g. '"abc123"' → 'abc123'
    """
    return header_value.strip('"').strip()
