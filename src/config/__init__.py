import base64
from os import environ
from typing import Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from zoneinfo import available_timezones


class Settings(BaseSettings):
    # API settings
    port: int = 5001
    host: str = "0.0.0.0"

    # Database settings
    db_uri: str

    # WhatsApp (OpenWA) settings
    # Legacy: imported once on first start, then managed in Admin > Settings
    whatsapp_host: str = ""
    openwa_api_key: str = ""
    openwa_session_id: str = ""
    openwa_webhook_secret: str = ""  # >= 16 chars when set (OpenWA requirement)
    openwa_webhook_url: str = ""  # if set, registered with OpenWA at startup

    # Base64 of 32 random bytes; encrypts secrets stored in the database
    settings_encryption_key: SecretStr

    anthropic_api_key: str

    # Voyage settings
    voyage_api_key: str
    voyage_max_retries: int = 5

    # Model settings
    model_name: str = "anthropic:claude-sonnet-4-6"

    # Optional settings
    debug: bool = False
    log_level: str = "INFO"
    logfire_token: str

    # Admin UI (disabled unless both password and session secret are set)
    admin_password: str | None = None
    admin_session_secret: str | None = None  # >= 32 chars
    admin_cookie_secure: bool = False

    # IANA zone the admin dashboard stats are bucketed in
    timezone: str = Field(default="Asia/Jerusalem", validate_default=True)

    @field_validator("timezone", mode="after")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        # Must be a canonical IANA name present in the tz database (this also
        # rejects '', surrounding whitespace, wrong case, 'posixrules' and a
        # missing tzdata install); 'localtime' is host-dependent, so refuse it.
        if v == "localtime" or v not in available_timezones():
            raise ValueError(
                f"Invalid TIMEZONE '{v}': expected an IANA name such as "
                "'Asia/Jerusalem' or 'UTC' (is the tzdata package installed?)"
            )
        return v

    @field_validator("openwa_webhook_secret")
    @classmethod
    def validate_webhook_secret(cls, v: str) -> str:
        if v and len(v) < 16:
            raise ValueError("openwa_webhook_secret must be at least 16 characters")
        return v

    @field_validator("settings_encryption_key")
    @classmethod
    def validate_settings_encryption_key(cls, v: SecretStr) -> SecretStr:
        try:
            ok = len(base64.b64decode(v.get_secret_value(), validate=True)) == 32
        except ValueError:
            ok = False
        if not ok:
            raise ValueError("settings_encryption_key must be base64 of 32 bytes")
        return v

    @field_validator("admin_session_secret")
    @classmethod
    def validate_admin_session_secret(cls, v: str | None) -> str | None:
        if v and len(v) < 32:
            raise ValueError("admin_session_secret must be at least 32 characters")
        return v or None

    @field_validator("admin_password")
    @classmethod
    def blank_admin_password_is_unset(cls, v: str | None) -> str | None:
        return v or None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        arbitrary_types_allowed=True,
        case_sensitive=False,
        extra="ignore",
        # Validation errors must never print a secret (the encryption key, API
        # keys) as their input value at startup.
        hide_input_in_errors=True,
    )

    @model_validator(mode="after")
    def apply_env(self) -> Self:
        if self.anthropic_api_key:
            environ["ANTHROPIC_API_KEY"] = self.anthropic_api_key

        if self.logfire_token:
            environ["LOGFIRE_TOKEN"] = self.logfire_token

        return self


@lru_cache
def get_settings() -> Settings:
    # Use model_validate({}) to trigger Pydantic's validation and environment variable loading
    # without passing arguments directly, which satisfies type checkers that would otherwise
    # complain about missing required fields in __init__.
    return Settings.model_validate({})
