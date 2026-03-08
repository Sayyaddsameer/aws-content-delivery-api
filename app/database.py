"""
asyncpg connection pool + DB migration runner.

Usage as script:
    python -m app.database --migrate
"""

import asyncio
import sys
from pathlib import Path

import asyncpg

from app.config import settings

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=settings.database_url,
            min_size=2,
            max_size=10,
        )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def run_migrations() -> None:
    migration_dir = Path(__file__).parent.parent / "db" / "migrations"
    sql_files = sorted(migration_dir.glob("*.sql"))
    pool = await get_pool()
    async with pool.acquire() as conn:
        for sql_file in sql_files:
            print(f"[migrate] running {sql_file.name} ...")
            sql = sql_file.read_text(encoding="utf-8")
            await conn.execute(sql)
            print(f"[migrate] {sql_file.name} done.")
    print("[migrate] all migrations complete.")


if __name__ == "__main__":
    if "--migrate" in sys.argv:
        asyncio.run(run_migrations())
