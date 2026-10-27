"""Request mẫu cho từng kind (demo)."""

from __future__ import annotations


def sample_requests(language: str = "vi") -> dict[str, str]:
    """Trả về các request mẫu cho từng kind (profile-agnostic, identity injected from profile)."""
    if language == "vi":
        return {
            "similar": "Gợi ý 5 sản phẩm tương tự như Video_Games::B00EXAMPLE.",
            "personalized": "Gợi ý 5 sản phẩm phù hợp với sở thích của tôi.",
            "constrained": "Gợi ý 5 sản phẩm Video Games dưới $50.",
            "cold_text": "Gợi ý 5 sản phẩm Toys.",
            "ambiguous": "Gợi ý cho tôi sản phẩm hay.",
        }
    else:  # en
        return {
            "similar": "Recommend 5 products similar to Video_Games::B00EXAMPLE.",
            "personalized": "Recommend 5 products suitable for my preferences.",
            "constrained": "Recommend 5 Video Games products under $50.",
            "cold_text": "Recommend 5 Toys products.",
            "ambiguous": "Recommend some good products for me.",
        }
