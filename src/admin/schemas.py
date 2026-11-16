from __future__ import annotations

import ipaddress
import socket
from datetime import datetime
from typing import Generic, Literal, TypeVar
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

T = TypeVar("T")

MAX_KEYS = 50
MAX_KEY_LEN = 100
MAX_OFFSET = 1_000_000


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def clean_keys(value: list[str] | None) -> list[str] | None:
    """Trim, drop empties, de-duplicate (keep order). Empty result -> None."""
    if not value:
        return None
    seen: dict[str, None] = {}
    for key in value:
        key = key.strip()
        if key and key not in seen:
            seen[key] = None
    keys = list(seen)
    return keys or None


class GroupOut(BaseModel):
    group_jid: str
    group_name: str | None
    display_name: str | None
    group_topic: str | None
    owner_jid: str | None
    managed: bool
    community_keys: list[str]
    message_count: int

    @classmethod
    def from_group(cls, group, message_count: int) -> "GroupOut":
        return cls(
            group_jid=group.group_jid,
            group_name=group.group_name,
            display_name=group.display_name,
            group_topic=group.group_topic,
            owner_jid=group.owner_jid,
            managed=group.managed,
            community_keys=list(group.community_keys or []),
            message_count=int(message_count or 0),
        )


def _no_nul(value):
    if isinstance(value, str) and "\x00" in value:
        raise ValueError("NUL characters are not allowed")
    return value


class GroupPatch(BaseModel):
    managed: bool | None = None
    community_keys: list[str] | None = None
    display_name: str | None = Field(default=None, max_length=255)

    @field_validator("community_keys", mode="before")
    @classmethod
    def _keys(cls, value):
        if value is None:
            return None
        if not isinstance(value, list):
            raise ValueError("community_keys must be a list")
        for key in value:
            _no_nul(key)
            if not isinstance(key, str) or len(key.strip()) > MAX_KEY_LEN:
                raise ValueError(f"each key must be a string of <= {MAX_KEY_LEN} chars")
        return clean_keys(value) or []

    @field_validator("display_name")
    @classmethod
    def _display_name_no_nul(cls, value):
        return _no_nul(value)

    @field_validator("community_keys")
    @classmethod
    def _key_count(cls, value):
        if value is not None and len(value) > MAX_KEYS:
            raise ValueError(f"at most {MAX_KEYS} community keys")
        return value

    @model_validator(mode="after")
    def _no_null_flags(self):
        for name in ("managed",):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class ContactOut(BaseModel):
    jid: str
    push_name: str | None
    opted_out: bool


class ContactPatch(BaseModel):
    push_name: str | None = Field(default=None, max_length=255)

    @field_validator("push_name")
    @classmethod
    def _push_name_no_nul(cls, value):
        return _no_nul(value)


class OptOutOut(BaseModel):
    jid: str
    push_name: str | None
    created_at: datetime


class OptOutCreate(BaseModel):
    jid: str = Field(max_length=300)


class MessageOut(BaseModel):
    message_id: str
    timestamp: datetime
    text: str | None
    sender_jid: str
    sender_name: str | None
    group_jid: str | None
    chat_jid: str
    reply_to_id: str | None
    reaction_count: int
    has_media: bool


class MessagePage(BaseModel):
    items: list[MessageOut]
    next_cursor: str | None


StatsBucket = Literal["hour", "day", "week", "month"]


class StatsGroups(BaseModel):
    total: int
    managed: int


class StatsSplit(BaseModel):
    text: int
    media: int
    other: int


class StatsPoint(BaseModel):
    start: datetime
    count: int


class StatsTopGroup(BaseModel):
    group_jid: str
    name: str | None
    count: int


class StatsTopSender(BaseModel):
    sender_jid: str
    name: str | None
    count: int


class StatsOut(BaseModel):
    from_: datetime = Field(serialization_alias="from")
    to: datetime
    timezone: str
    bucket: StatsBucket
    bot_excluded: bool
    groups: StatsGroups
    chats: int
    messages: int
    active_senders: int
    reactions: int
    split: StatsSplit
    series: list[StatsPoint]
    top_groups: list[StatsTopGroup]
    top_senders: list[StatsTopSender]
    by_hour: list[int] = Field(min_length=24, max_length=24)
    by_weekday: list[int] = Field(min_length=7, max_length=7)


# --- OpenWA settings ------------------------------------------------------------
#
# Secrets are never echoed: secret fields carry no failing validators (a 422
# body would include the rejected input), so their length is checked in the
# handler, and no model-level validator may fail on a model holding secrets.

MIN_SECRET_LEN = 16
MAX_SECRET_LEN = 1024
MAX_URL_LEN = 2048


def _strip(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


def _http_url(value: str, *, allow_empty: bool, block_link_local: bool = False) -> str:
    if not value and allow_empty:
        return value
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("must look like http(s)://host")
    if block_link_local and _is_link_local(parts.hostname):
        # The message never echoes the value.
        raise ValueError("must not be a link-local or cloud metadata address")
    return value


def _is_link_local(host: str) -> bool:
    """True for a literal IP host in 169.254.0.0/16 or fe80::/10.

    Hostnames are not resolved. Numeric IPv4 shorthands that the OS resolver
    also accepts (for example a single decimal number) are parsed the same way.
    """
    try:
        ip: ipaddress.IPv4Address | ipaddress.IPv6Address = ipaddress.ip_address(
            host.split("%", 1)[0]
        )
    except ValueError:
        try:
            ip = ipaddress.IPv4Address(socket.inet_aton(host))
        except OSError:
            return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_link_local


class ConnectionOut(BaseModel):
    base_url: str
    webhook_url: str
    api_key_set: bool
    webhook_secret_set: bool


class ConnectionPut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Defaulted so a missing value fails on the field alone, not on the whole
    # body (a "field required" error would echo the body, secrets included).
    base_url: str = Field(default="", max_length=MAX_URL_LEN, validate_default=True)
    api_key: str | None = None
    webhook_secret: str | None = None
    webhook_url: str = Field(default="", max_length=MAX_URL_LEN)

    @field_validator(
        "base_url", "api_key", "webhook_secret", "webhook_url", mode="before"
    )
    @classmethod
    def _trim(cls, value):
        return _strip(value)

    @field_validator("base_url")
    @classmethod
    def _base_url(cls, value: str) -> str:
        return _http_url(value, allow_empty=False, block_link_local=True)

    @field_validator("webhook_url")
    @classmethod
    def _webhook_url(cls, value: str) -> str:
        return _http_url(value, allow_empty=True)


class ConnectionTest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_url: str | None = Field(default=None, max_length=MAX_URL_LEN)
    api_key: str | None = None
    openwa_session_id: str | None = Field(default=None, max_length=255)

    @field_validator("base_url", "api_key", "openwa_session_id", mode="before")
    @classmethod
    def _trim(cls, value):
        return _strip(value)

    @field_validator("base_url")
    @classmethod
    def _base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _http_url(value, allow_empty=True, block_link_local=True)


class ConnectionTestResult(BaseModel):
    ok: bool
    detail: str


class SessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=100)
    openwa_session_id: str = Field(min_length=1, max_length=255)

    @field_validator("label", "openwa_session_id", mode="before")
    @classmethod
    def _trim(cls, value):
        return _strip(value)


class SessionPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str | None = Field(default=None, min_length=1, max_length=100)
    openwa_session_id: str | None = Field(default=None, min_length=1, max_length=255)
    enabled: bool | None = None

    @field_validator("label", "openwa_session_id", mode="before")
    @classmethod
    def _trim(cls, value):
        return _strip(value)

    @model_validator(mode="after")
    def _no_nulls(self):
        for name in self.model_fields_set:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class SessionOut(BaseModel):
    id: str
    label: str
    openwa_session_id: str
    enabled: bool
    status: str | None
    error: str | None
    group_count: int


class WebhookRegistered(BaseModel):
    registered: bool


class SessionSynced(BaseModel):
    groups: int
