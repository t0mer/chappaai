from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import text
from sqlmodel import select

from handler import MessageHandler
from models import Group, Message, Reaction, Sender
from test_utils.openwa_session import OTHER_SESSION_ID, TEST_SESSION_ID
from whatsapp import InboundMessage, InboundReaction
from whatsapp.jid import JID

pytestmark = pytest.mark.usefixtures("other_session_row")

BOT = "bot@s.whatsapp.net"
USER = "972501@s.whatsapp.net"


def whatsapp() -> AsyncMock:
    client = AsyncMock()
    client.get_my_jid = AsyncMock(return_value=JID(user="bot", server="s.whatsapp.net"))
    client.get_my_lid = AsyncMock(return_value=None)
    return client


def inbound(text: str, chat: str, msg_id: str = "m1") -> InboundMessage:
    return InboundMessage(
        id=msg_id,
        chat_jid=chat,
        sender_jid=USER,
        timestamp=datetime(2026, 10, 13, tzinfo=timezone.utc),
        text=text,
        sender_name="User",
    )


async def seed_group(db_sessionmaker, jid: str, owner: str) -> None:
    async with db_sessionmaker() as session:
        session.add(Group(group_jid=jid, session_id=owner, managed=True))
        await session.commit()


async def handle(db_sessionmaker, session_id: str, event, wa: AsyncMock) -> None:
    async with db_sessionmaker() as session:
        handler = MessageHandler(session, wa, AsyncMock(), session_id)
        await handler(event)


async def messages(db_sessionmaker) -> list[Message]:
    async with db_sessionmaker() as session:
        return list((await session.exec(select(Message))).all())


async def test_message_in_group_owned_by_another_session_is_ignored(
    db_sessionmaker,
):
    await seed_group(db_sessionmaker, "a@g.us", TEST_SESSION_ID)
    wa = whatsapp()

    await handle(db_sessionmaker, OTHER_SESSION_ID, inbound("@bot hi", "a@g.us"), wa)

    assert await messages(db_sessionmaker) == []
    assert wa.mock_calls == []


async def test_message_in_own_group_is_stored(db_sessionmaker):
    await seed_group(db_sessionmaker, "b@g.us", OTHER_SESSION_ID)

    await handle(
        db_sessionmaker, OTHER_SESSION_ID, inbound("hello", "b@g.us"), whatsapp()
    )

    (stored,) = await messages(db_sessionmaker)
    assert (stored.group_jid, stored.session_id) == ("b@g.us", OTHER_SESSION_ID)


async def test_dm_is_stored_under_the_handler_session(db_sessionmaker):
    await handle(db_sessionmaker, OTHER_SESSION_ID, inbound("hello", USER), whatsapp())

    (stored,) = await messages(db_sessionmaker)
    assert stored.group_jid is None
    assert stored.session_id == OTHER_SESSION_ID


async def test_reaction_on_message_in_foreign_group_is_ignored(db_sessionmaker):
    async with db_sessionmaker() as session:
        # Unique index from the reaction migration that create_all lacks.
        await session.execute(
            text("CREATE UNIQUE INDEX ON reaction (message_id, sender_jid)")
        )
        await session.commit()
    await seed_group(db_sessionmaker, "a@g.us", TEST_SESSION_ID)
    await handle(
        db_sessionmaker, TEST_SESSION_ID, inbound("hello", "a@g.us"), whatsapp()
    )
    reaction = InboundReaction(
        message_id="m1",
        sender_jid=USER,
        emoji="👍",
        timestamp=datetime(2026, 10, 13, tzinfo=timezone.utc),
    )

    await handle(db_sessionmaker, OTHER_SESSION_ID, reaction, whatsapp())
    async with db_sessionmaker() as session:
        assert (await session.exec(select(Reaction))).all() == []

    await handle(db_sessionmaker, TEST_SESSION_ID, reaction, whatsapp())
    async with db_sessionmaker() as session:
        assert len((await session.exec(select(Reaction))).all()) == 1


async def test_message_upsert_keeps_the_original_session(db_sessionmaker):
    async with db_sessionmaker() as session:
        session.add(Sender(jid=USER))
        session.add(
            Message(
                message_id="dup",
                chat_jid=USER,
                sender_jid=USER,
                text="first",
                session_id=TEST_SESSION_ID,
            )
        )
        await session.commit()

    await handle(
        db_sessionmaker, OTHER_SESSION_ID, inbound("second", USER, "dup"), whatsapp()
    )

    (stored,) = await messages(db_sessionmaker)
    assert stored.session_id == TEST_SESSION_ID


async def test_group_created_by_another_session_during_the_race_is_not_taken(
    db_sessionmaker, monkeypatch
):
    # Session B passed its ownership check while the group was still unknown;
    # session A created it before B got to auto-create it.
    monkeypatch.setattr(MessageHandler, "_foreign_group", AsyncMock(return_value=False))
    async with db_sessionmaker() as session:
        session.add(
            Group(group_jid="r@g.us", session_id=TEST_SESSION_ID, group_name="Real")
        )
        await session.commit()
    wa = whatsapp()

    await handle(db_sessionmaker, OTHER_SESSION_ID, inbound("@bot hi", "r@g.us"), wa)

    assert await messages(db_sessionmaker) == []
    assert wa.mock_calls == []
    async with db_sessionmaker() as session:
        group = await session.get(Group, "r@g.us")
        assert group is not None
        assert (group.session_id, group.group_name) == (TEST_SESSION_ID, "Real")


async def test_first_message_of_unknown_group_creates_it_for_the_session(
    db_sessionmaker,
):
    await handle(
        db_sessionmaker, OTHER_SESSION_ID, inbound("hello", "new@g.us"), whatsapp()
    )
    async with db_sessionmaker() as session:
        group = await session.get(Group, "new@g.us")
        assert group is not None and group.session_id == OTHER_SESSION_ID
    (stored,) = await messages(db_sessionmaker)
    assert stored.session_id == OTHER_SESSION_ID
