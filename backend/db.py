import json
import os
from typing import Any

import asyncpg
from dotenv import load_dotenv


load_dotenv()

_pool: asyncpg.Pool | None = None


class DatabaseError(Exception):
    """Raised when database access is unavailable or fails."""

    def __init__(self, message: str, status_code: int = 500) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


async def init_db() -> None:
    global _pool

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        _pool = None
        return

    try:
        _pool = await asyncpg.create_pool(database_url)
        async with _pool.acquire() as connection:
            await connection.execute(
                """
                CREATE EXTENSION IF NOT EXISTS pgcrypto;

                CREATE TABLE IF NOT EXISTS users (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL DEFAULT '',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS analyses (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    region TEXT NOT NULL,
                    resources_scanned INTEGER NOT NULL DEFAULT 0,
                    issues_found INTEGER NOT NULL DEFAULT 0,
                    estimated_savings TEXT,
                    analysis_result JSONB NOT NULL,
                    status TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
    except Exception as exc:
        _pool = None
        raise DatabaseError(f"Failed to initialize database: {exc}", status_code=503) from exc


async def close_db() -> None:
    global _pool

    if _pool is not None:
        await _pool.close()
        _pool = None


async def create_user(email: str, password_hash: str) -> asyncpg.Record:
    pool = _require_pool()

    try:
        async with pool.acquire() as connection:
            return await connection.fetchrow(
                """
                INSERT INTO users (email, password_hash)
                VALUES ($1, $2)
                RETURNING id, email, created_at
                """,
                email,
                password_hash,
            )
    except asyncpg.UniqueViolationError as exc:
        raise DatabaseError("A user with this email already exists.", status_code=409) from exc


async def get_user_by_email(email: str) -> asyncpg.Record | None:
    pool = _require_pool()

    async with pool.acquire() as connection:
        return await connection.fetchrow(
            """
            SELECT id, email, password_hash, created_at
            FROM users
            WHERE email = $1
            """,
            email,
        )


async def get_user_by_id(user_id: str) -> asyncpg.Record | None:
    pool = _require_pool()

    async with pool.acquire() as connection:
        return await connection.fetchrow(
            """
            SELECT id, email, created_at
            FROM users
            WHERE id = $1::uuid
            """,
            user_id,
        )


async def get_or_create_user(email: str) -> asyncpg.Record:
    pool = _require_pool()

    async with pool.acquire() as connection:
        return await connection.fetchrow(
            """
            INSERT INTO users (email)
            VALUES ($1)
            ON CONFLICT (email) DO UPDATE SET email = EXCLUDED.email
            RETURNING id, email, created_at
            """,
            email,
        )


async def save_analysis(
    *,
    analysis_id: str | None,
    user_id: str,
    region: str,
    resources_scanned: int,
    issues_found: int,
    estimated_savings: str,
    analysis_result: dict[str, Any],
    status: str,
) -> asyncpg.Record:
    pool = _require_pool()
    analysis_json = json.dumps(analysis_result, default=str)

    async with pool.acquire() as connection:
        if analysis_id:
            return await connection.fetchrow(
                """
                INSERT INTO analyses (
                    id, user_id, region, resources_scanned, issues_found,
                    estimated_savings, analysis_result, status
                )
                VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7::jsonb, $8)
                RETURNING *
                """,
                analysis_id,
                user_id,
                region,
                resources_scanned,
                issues_found,
                estimated_savings,
                analysis_json,
                status,
            )

        return await connection.fetchrow(
            """
            INSERT INTO analyses (
                user_id, region, resources_scanned, issues_found,
                estimated_savings, analysis_result, status
            )
            VALUES ($1::uuid, $2, $3, $4, $5, $6::jsonb, $7)
            RETURNING *
            """,
            user_id,
            region,
            resources_scanned,
            issues_found,
            estimated_savings,
            analysis_json,
            status,
        )


async def get_user_history(user_id: str) -> list[dict[str, Any]]:
    pool = _require_pool()

    async with pool.acquire() as connection:
        rows = await connection.fetch(
            """
            SELECT
                id,
                region,
                resources_scanned,
                issues_found,
                estimated_savings,
                analysis_result,
                status,
                created_at
            FROM analyses
            WHERE user_id = $1::uuid
            ORDER BY created_at DESC
            """,
            user_id,
        )

    return [_analysis_record_to_dict(row) for row in rows]


def _require_pool() -> asyncpg.Pool:
    if _pool is None:
        raise DatabaseError(
            "DATABASE_URL is not configured. Add it to your environment or .env file.",
            status_code=503,
        )

    return _pool


def _analysis_record_to_dict(row: asyncpg.Record) -> dict[str, Any]:
    analysis_result = row["analysis_result"]
    if isinstance(analysis_result, str):
        analysis_result = json.loads(analysis_result)

    return {
        "id": str(row["id"]),
        "region": row["region"],
        "resources_scanned": row["resources_scanned"],
        "issues_found": row["issues_found"],
        "estimated_savings": row["estimated_savings"],
        "analysis_result": analysis_result,
        "status": row["status"],
        "created_at": row["created_at"].isoformat(),
    }
