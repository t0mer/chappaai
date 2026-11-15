from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from handler import MessageHandler
from whatsapp import InboundMessage, InboundReaction


def inbound(text, *, chat="user@s.whatsapp.net", sender="user@s.whatsapp.net", **kw):
    return InboundMessage(
        id=kw.pop("id", "m1"),
        chat_jid=chat,
        sender_jid=sender,
        timestamp=datetime.now(timezone.utc),
        text=text,
        sender_name="User",
        **kw,
    )


def reaction(emoji="👍") -> InboundReaction:
    return InboundReaction(
        message_id="m1",
        sender_jid="user@s.whatsapp.net",
        emoji=emoji,
        timestamp=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_whatsapp():
    return AsyncMock()


@pytest.fixture
def handler(mock_session, mock_whatsapp):
    h = MessageHandler(mock_session, mock_whatsapp, AsyncMock(), "s1")
    h.store_reaction = AsyncMock()
    h.store_message = AsyncMock()
    return h


async def test_message_handler_stores_reaction_event(
    handler, mock_session, mock_whatsapp
):
    event = reaction()
    await handler(event)
    handler.store_reaction.assert_awaited_once_with(event)
    handler.store_message.assert_not_awaited()
    mock_session.commit.assert_awaited_once()
    assert mock_whatsapp.mock_calls == []


@pytest.mark.parametrize(
    "event",
    [
        inbound("hello", chat="g@g.us"),
        inbound("@bot hi", chat="g@g.us", mentioned_jids=("bot@s.whatsapp.net",)),
        inbound("opt-out"),
        inbound("from me", chat="g@g.us", from_me=True),
    ],
    ids=["group", "mention", "dm-command", "from-me"],
)
async def test_message_handler_only_stores_messages(
    handler, mock_session, mock_whatsapp, event
):
    await handler(event)
    handler.store_message.assert_awaited_once_with(event)
    mock_session.commit.assert_awaited_once()
    # Listen-only: the gateway is never used to reply.
    assert mock_whatsapp.mock_calls == []


async def test_store_reaction_ignores_empty_emoji(mock_session, mock_whatsapp):
    handler = MessageHandler(mock_session, mock_whatsapp, AsyncMock(), "s1")
    assert await handler.store_reaction(reaction(emoji="")) is None
    mock_session.execute.assert_not_called()
