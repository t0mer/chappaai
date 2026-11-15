"""
Message search.

Only PostgreSQL full-text search over message text survives the removal of the
knowledge-base topics; hybrid (vector + keyword) search over chunks replaces it
in a later phase.
"""

import logging
from typing import List, Tuple

from sqlmodel import text
from sqlmodel.ext.asyncio.session import AsyncSession

from models import Message


logger = logging.getLogger(__name__)


async def keyword_search(
    session: AsyncSession,
    query: str,
    group_jids: List[str] | None = None,
    limit: int = 20,
) -> List[Tuple[Message, float]]:
    """
    Perform PostgreSQL full-text search on message content.

    Args:
        session: Database session
        query: The search query string
        group_jids: Optional list of group JIDs to filter by
        limit: Maximum number of results to return

    Returns:
        List of tuples containing (Message, ts_rank score)
    """
    # Build the full-text search query dynamically
    # We use plainto_tsquery for simple keyword matching
    # Note: We build the query conditionally to avoid asyncpg AmbiguousParameterError
    # when group_jids is None (asyncpg can't infer the type of a NULL array parameter)

    base_query = """
        SELECT m.*, ts_rank(to_tsvector('simple', COALESCE(m.text, '')), plainto_tsquery('simple', :query)) as rank
        FROM message m
        WHERE to_tsvector('simple', COALESCE(m.text, '')) @@ plainto_tsquery('simple', :query)
    """

    params: dict = {"query": query, "limit": limit}

    if group_jids:
        base_query += " AND m.group_jid = ANY(:group_jids)"
        params["group_jids"] = group_jids

    base_query += " ORDER BY rank DESC LIMIT :limit"

    search_query = text(base_query)

    result = await session.execute(search_query, params)

    rows = result.fetchall()
    messages = []
    for row in rows:
        # Construct Message from row data
        msg = Message(
            message_id=row.message_id,
            timestamp=row.timestamp,
            text=row.text,
            media_url=row.media_url,
            chat_jid=row.chat_jid,
            sender_jid=row.sender_jid,
            group_jid=row.group_jid,
            reply_to_id=row.reply_to_id,
            session_id=row.session_id,
        )
        messages.append((msg, row.rank))

    return messages
