from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from pydantic import field_validator
from sqlmodel import (
    Field,
    Relationship,
    SQLModel,
    Index,
    ARRAY,
    Column,
    String,
    DateTime,
)

from whatsapp.jid import normalize_jid

if TYPE_CHECKING:
    from .message import Message
    from .sender import Sender


class BaseGroup(SQLModel):
    group_jid: str = Field(primary_key=True, max_length=255)
    session_id: str = Field(foreign_key="openwa_session.id", index=True, max_length=64)
    group_name: Optional[str] = Field(default=None, max_length=255)
    display_name: Optional[str] = Field(default=None, max_length=255)
    group_topic: Optional[str] = Field(default=None)
    owner_jid: Optional[str] = Field(
        max_length=255, foreign_key="sender.jid", nullable=True, default=None
    )
    managed: bool = Field(default=False)
    community_keys: Optional[List[str]] = Field(
        default=None, sa_column=Column(ARRAY(String))
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    @field_validator("group_jid", "owner_jid", mode="before")
    @classmethod
    def normalize(cls, value: Optional[str]) -> str | None:
        return normalize_jid(value) if value else None


class Group(BaseGroup, table=True):
    owner: Optional["Sender"] = Relationship(back_populates="groups_owned")
    messages: List["Message"] = Relationship(back_populates="group")

    __table_args__ = (
        Index("idx_group_community_keys", "community_keys", postgresql_using="gin"),
    )


Group.model_rebuild()
