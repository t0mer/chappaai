"""Shared helpers for migration tests: a throwaway Postgres DB per test."""

import asyncio
import os
import sys
import uuid
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[1]


def _admin_uri() -> str:
    uri = os.environ.get("ADMIN_TEST_DB_URI")
    if not uri or "test" not in (make_url(uri).database or ""):
        pytest.skip("set ADMIN_TEST_DB_URI to a *test* Postgres database")
    return uri


async def _admin_sql(uri: str, sql: str) -> None:
    engine = create_async_engine(uri, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        await conn.execute(text(sql))
    await engine.dispose()


def _fresh_db(base: str):
    name = f"test_mig_{uuid.uuid4().hex[:8]}"
    asyncio.run(_admin_sql(base, f'CREATE DATABASE "{name}"'))
    try:  # everything after CREATE must be inside, so DROP always runs
        uri = make_url(base).set(database=name).render_as_string(hide_password=False)
        asyncio.run(_admin_sql(uri, "CREATE EXTENSION IF NOT EXISTS vector"))
        yield uri
    finally:
        asyncio.run(_admin_sql(base, f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))


@pytest.fixture
def fresh_db_uri():
    yield from _fresh_db(_admin_uri())


def test_fresh_db_is_dropped_when_extension_step_fails(monkeypatch):
    calls: list[str] = []

    async def fake_admin_sql(uri: str, sql: str) -> None:
        calls.append(sql)
        if sql.startswith("CREATE EXTENSION"):
            raise RuntimeError("pgvector not available")

    monkeypatch.setattr(sys.modules[__name__], "_admin_sql", fake_admin_sql)
    with pytest.raises(RuntimeError, match="pgvector"):
        next(_fresh_db("postgresql+asyncpg://u:p@h/test_base"))
    assert calls[0].startswith("CREATE DATABASE")
    assert calls[-1].startswith("DROP DATABASE IF EXISTS")


def _config(uri: str) -> Config:
    # no ini file: env.py would call logging.fileConfig and disable app loggers
    config = Config()
    config.set_main_option("script_location", str(ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", uri.replace("%", "%%"))
    return config
