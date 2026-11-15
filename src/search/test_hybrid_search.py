import pytest
from typing import cast
from unittest.mock import MagicMock
from datetime import datetime
from sqlmodel.ext.asyncio.session import AsyncSession

from models import Message, Group
from search.hybrid_search import keyword_search


@pytest.mark.asyncio
async def test_keyword_search_multi_language(mock_session: AsyncSession):
    """Test that keyword search works for non-English text (Hebrew)."""
    group = Group(session_id="s1", group_jid="456@g.us", group_name="Hebrew Group")

    message = Message(
        session_id="s1",
        message_id="msg_he_1",
        chat_jid=group.group_jid,
        sender_jid="user_1@s.whatsapp.net",
        text="שלום, מה שלומך? אני בודק את החיפוש.",
        timestamp=datetime.now(),
        group_jid=group.group_jid,
    )

    # Mock the DB result
    mock_result = MagicMock()
    mock_row = MagicMock()
    mock_row.message_id = message.message_id
    mock_row.timestamp = message.timestamp
    mock_row.text = message.text
    mock_row.media_url = message.media_url
    mock_row.chat_jid = message.chat_jid
    mock_row.sender_jid = message.sender_jid
    mock_row.session_id = message.session_id
    mock_row.group_jid = message.group_jid
    mock_row.reply_to_id = message.reply_to_id
    mock_row.rank = 0.8
    mock_result.fetchall.return_value = [mock_row]
    cast(MagicMock, mock_session.execute).side_effect = None
    cast(MagicMock, mock_session.execute).return_value = mock_result

    # Search for "בודק" (testing)
    results = await keyword_search(mock_session, "בודק", [group.group_jid])

    assert len(results) > 0
    assert results[0][0].message_id == message.message_id
