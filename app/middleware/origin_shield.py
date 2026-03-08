"""
Origin Shield Middleware.

When ORIGIN_SHIELD_ENABLED=true, only requests carrying the correct
X-CDN-Secret header (set by CloudFront as a custom origin header)
are allowed through. This prevents clients from bypassing the CDN
and hitting the origin API directly.
"""

from fastapi import Request, HTTPException
from app.config import settings


async def origin_shield_middleware(request: Request, call_next):
    if settings.origin_shield_enabled:
        cdn_secret = request.headers.get("x-cdn-secret", "")
        if cdn_secret != settings.cdn_secret:
            raise HTTPException(
                status_code=403,
                detail="Direct origin access is not permitted. Use the CDN endpoint.",
            )
    return await call_next(request)
