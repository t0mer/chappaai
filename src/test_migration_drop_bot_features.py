# ruff: noqa: F811
import asyncio

from alembic import command
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

# fresh_db_uri is a fixture: importing it registers it here (hence F401/F811)
from test_migrations import _config, fresh_db_uri  # noqa: F401

REV = "b0328428962c"
PREV = "f6a7b8c9d0e1"
TABLES = {"kbtopic", "kb_topic_message", "group_summary_schedule"}
GROUP_COLUMNS = {
    "summary_language",
    "notify_on_spam",
    "last_ingest",
    "last_summary_sync",
}


def _snapshot(uri: str) -> tuple[set[str], set[str], str]:
    async def work():
        engine = create_async_engine(uri)
        async with engine.connect() as conn:

            def inspect_schema(sync_conn):
                insp = inspect(sync_conn)
                return (
                    set(insp.get_table_names()),
                    {c["name"] for c in insp.get_columns("group")},
                )

            tables, columns = await conn.run_sync(inspect_schema)
            version = (
                await conn.execute(text("SELECT version_num FROM alembic_version"))
            ).scalar_one()
        await engine.dispose()
        return tables, columns, version

    return asyncio.run(work())


def _seed_group(uri: str) -> None:
    async def work():
        engine = create_async_engine(uri)
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    """INSERT INTO openwa_session (id, openwa_session_id, label, enabled)
                       VALUES ('s1', 'default', 'default', true)"""
                )
            )
            await conn.execute(
                text(
                    """INSERT INTO "group" (group_jid, session_id, managed, created_at)
                       VALUES ('1@g.us', 's1', true, now())"""
                )
            )
        await engine.dispose()

    asyncio.run(work())


def test_drop_bot_features_upgrade_downgrade_upgrade(fresh_db_uri):
    config = _config(fresh_db_uri)
    command.upgrade(config, PREV)
    tables, columns, _ = _snapshot(fresh_db_uri)
    assert TABLES <= tables and GROUP_COLUMNS <= columns

    command.upgrade(config, REV)
    tables, columns, version = _snapshot(fresh_db_uri)
    assert version == REV
    assert not TABLES & tables and not GROUP_COLUMNS & columns
    assert {"group", "message", "reaction", "opt_out"} <= tables

    # Existing groups survive the downgrade: NOT NULL columns are backfilled.
    _seed_group(fresh_db_uri)
    command.downgrade(config, PREV)
    tables, columns, version = _snapshot(fresh_db_uri)
    assert version == PREV and TABLES <= tables and GROUP_COLUMNS <= columns

    command.upgrade(config, "head")
    tables, columns, version = _snapshot(fresh_db_uri)
    assert version == REV and not TABLES & tables and not GROUP_COLUMNS & columns
