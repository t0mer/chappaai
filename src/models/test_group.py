from models.group import Group


def test_group_normalization():
    group = Group(session_id="s1", group_jid="123456789-123456@g.us")
    assert group.group_jid == "123456789-123456@g.us"

    # Test normalization via field validator (if applicable during init)
    # The validator is on the class, so we can test it directly or via init if pydantic validates
    # Pydantic validation happens on init
    # Test with model_validate
    group_validated = Group.model_validate(
        {
            "group_jid": "123456789-123456@g.us",
            "owner_jid": "1234567890.1:1@s.whatsapp.net",
            "session_id": "s1",
        }
    )
    assert group_validated.owner_jid == "1234567890@s.whatsapp.net"
