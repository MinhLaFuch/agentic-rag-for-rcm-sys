"""Identity injection sentences cho demo UI."""

from __future__ import annotations

# Câu để inject user_id vào request text (khi profile có user_id và chưa có trong text)
IDENTITY_INJECTION_VI = "Tôi là user {user_id}."
IDENTITY_INJECTION_EN = "I am user {user_id}."


def identity_injection_vi(user_id: str) -> str:
    """Return Vietnamese identity injection sentence."""
    return IDENTITY_INJECTION_VI.format(user_id=user_id)


def identity_injection_en(user_id: str) -> str:
    """Return English identity injection sentence."""
    return IDENTITY_INJECTION_EN.format(user_id=user_id)
