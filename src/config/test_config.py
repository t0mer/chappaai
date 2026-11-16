import pytest
from pydantic import ValidationError

from config import Settings


REQUIRED = dict(
    db_uri="postgresql+asyncpg://u:p@h/db",
    settings_encryption_key="A" * 43 + "=",
    anthropic_api_key="a",
    voyage_api_key="v",
    logfire_token="l",
)


def test_admin_disabled_by_default_and_blank_values_are_unset():
    s = Settings.model_validate(
        {**REQUIRED, "admin_password": "", "admin_session_secret": ""}
    )
    assert s.admin_password is None and s.admin_session_secret is None


def test_admin_session_secret_must_be_long_enough():
    with pytest.raises(ValidationError):
        Settings.model_validate({**REQUIRED, "admin_session_secret": "short"})
    ok = Settings.model_validate({**REQUIRED, "admin_session_secret": "x" * 32})
    assert ok.admin_session_secret == "x" * 32


def test_timezone_defaults_to_jerusalem(monkeypatch):
    monkeypatch.delenv("TIMEZONE", raising=False)
    s = Settings(_env_file=None, **REQUIRED)  # pyright: ignore[reportCallIssue]
    assert s.timezone == "Asia/Jerusalem"


@pytest.mark.parametrize(
    "name", ["UTC", "Europe/London", "Asia/Jerusalem", "America/New_York"]
)
def test_timezone_accepts_listed_iana_names(name):
    assert Settings.model_validate({**REQUIRED, "timezone": name}).timezone == name


@pytest.mark.parametrize(
    "name",
    ["", " ", "Asia/Jerusalem ", " UTC", "utc", "localtime", "posixrules", "Mars/X"],
)
def test_invalid_timezone_is_rejected(name):
    with pytest.raises(ValidationError) as exc:
        Settings.model_validate({**REQUIRED, "timezone": name})
    assert "TIMEZONE" in str(exc.value)


def test_invalid_timezone_error_does_not_echo_other_settings():
    secrets = {
        **REQUIRED,
        "openwa_api_key": "SECRET-API-KEY-123",
        "anthropic_api_key": "SECRET-ANTHROPIC-456",
        "db_uri": "postgresql+asyncpg://user:SECRET-PW-789@h/db",
        "timezone": "Mars/Olympus",
    }
    with pytest.raises(ValidationError) as exc:
        Settings.model_validate(secrets)
    text = str(exc.value)
    assert "Mars/Olympus" in text
    assert "SECRET" not in text


def test_default_timezone_is_validated(monkeypatch):
    monkeypatch.setattr("config.available_timezones", lambda: {"UTC"})
    with pytest.raises(ValidationError) as exc:
        Settings.model_validate(REQUIRED)
    assert "Asia/Jerusalem" in str(exc.value)


def test_settings_load_without_legacy_openwa_keys(monkeypatch):
    for k in (
        "WHATSAPP_HOST",
        "OPENWA_API_KEY",
        "OPENWA_SESSION_ID",
        "OPENWA_WEBHOOK_SECRET",
        "OPENWA_WEBHOOK_URL",
    ):
        monkeypatch.delenv(k, raising=False)
    s = Settings(_env_file=None, **REQUIRED)  # pyright: ignore[reportCallIssue]
    assert s.whatsapp_host == s.openwa_api_key == s.openwa_session_id == ""
    assert s.openwa_webhook_secret == s.openwa_webhook_url == ""


@pytest.mark.parametrize("key", ["", "not base64!", "c2hvcnQ="])
def test_settings_encryption_key_must_be_32_bytes_base64(key):
    with pytest.raises(ValidationError):
        Settings.model_validate({**REQUIRED, "settings_encryption_key": key})


def test_short_webhook_secret_still_rejected_when_set():
    with pytest.raises(ValidationError):
        Settings.model_validate({**REQUIRED, "openwa_webhook_secret": "short"})


@pytest.mark.parametrize("key", ["c2hvcnQta2V5LXZhbHVl", "not-base64-key-value!"])
def test_bad_encryption_key_is_never_echoed_in_the_error(key):
    with pytest.raises(ValidationError) as exc:
        Settings.model_validate({**REQUIRED, "settings_encryption_key": key})
    assert "settings_encryption_key" in str(exc.value)
    assert key not in str(exc.value)
    assert key not in repr(exc.value)


def test_encryption_key_is_hidden_from_repr():
    s = Settings.model_validate(REQUIRED)
    assert REQUIRED["settings_encryption_key"] not in repr(s)
    assert (
        s.settings_encryption_key.get_secret_value()
        == REQUIRED["settings_encryption_key"]
    )
