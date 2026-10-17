"""Request mẫu cho từng kind (demo)."""

from __future__ import annotations

from package.evaluation.agent import TEMPLATES


def sample_requests(language: str = "vi") -> dict[str, str]:
    """Trả về các request mẫu cho từng kind."""
    templates = TEMPLATES.get(language, TEMPLATES["vi"])
    return {
        "similar": templates["similar"].format(user_id="user123", item_id="Video_Games::B00EXAMPLE", k=5),
        "personalized": templates["personalized"].format(user_id="user123", k=5),
        "constrained": templates["constrained"].format(user_id="user123", category="Video Games", price_max=50, k=5),
        "cold_text": templates["cold_text"].format(user_id="user456", category="Toys", k=5),
        "ambiguous": templates["ambiguous"][0],  # "Gợi ý cho tôi sản phẩm hay."
    }
