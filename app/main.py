"""
FastAPI application entry point.
Registers all route handlers, middleware, and lifecycle events.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.database import get_pool, close_pool
from app.middleware.origin_shield import origin_shield_middleware
from app.routes import upload, download, publish, public, private, token


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialise DB connection pool
    await get_pool()
    yield
    # Shutdown: close DB connection pool
    await close_pool()


app = FastAPI(
    title="AWS Content Delivery API",
    description=(
        "High-performance content delivery API with HTTP caching, "
        "ETag support, CDN integration (CloudFront), and secure private assets."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS (permissive for development — tighten for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Origin Shield (no-op unless ORIGIN_SHIELD_ENABLED=true)
app.add_middleware(BaseHTTPMiddleware, dispatch=origin_shield_middleware)

# Register routers
app.include_router(upload.router)
app.include_router(download.router)
app.include_router(publish.router)
app.include_router(public.router)
app.include_router(private.router)
app.include_router(token.router)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}
