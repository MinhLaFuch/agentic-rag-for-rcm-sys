"""Contracts of the requests the agents accept: the request texts per language and kind (fixed in code on purpose)."""

# Shared by the agent evaluation (builds its requests from them) and the demo (shows them as samples).
TEMPLATES = {
    "vi": {
        "similar": "Tôi là user {user_id}, vừa mua {item_id}. Gợi ý cho tôi {k} sản phẩm tương tự.",
        "personalized": "Tôi là user {user_id}. Gợi ý cho tôi {k} sản phẩm hợp với thói quen mua hàng của tôi.",
        "constrained": 'Tôi là user {user_id}. Tìm cho tôi {k} sản phẩm thuộc nhóm "{category}" giá dưới {price_max} đô.',
        "cold_text": 'Tôi là user {user_id}, mới đến và chưa mua gì. Tôi muốn tìm {k} sản phẩm thuộc nhóm "{category}".',
        "ambiguous": (
            "Gợi ý cho tôi sản phẩm hay.",
            "Tôi muốn mua một món quà.",
            "Có gì mới không?",
        ),
        "exclusion": "Tôi là user {user_id}. Gợi ý cho tôi {k} sản phẩm KHÔNG thuộc nhóm \"{exclude_categories}\" và KHÔNG bao gồm các sản phẩm {exclude_items}.",
        "unanswerable": "Tôi là user {user_id}. Tìm cho tôi sản phẩm giá dưới 1 đô thuộc nhóm \"NonExistentCategory999\".",
    },
    "en": {
        "similar": "I am user {user_id} and just bought {item_id}. Recommend {k} similar products.",
        "personalized": "I am user {user_id}. Recommend {k} products that fit my buying habits.",
        "constrained": 'I am user {user_id}. Find me {k} products in the "{category}" category under ${price_max}.',
        "cold_text": 'I am user {user_id}, a new customer with no purchases yet. I want {k} products in the "{category}" category.',
        "ambiguous": (
            "Recommend me something good.",
            "I want to buy a gift.",
            "Anything new?",
        ),
        "exclusion": "I am user {user_id}. Recommend {k} products that are NOT in the \"{exclude_categories}\" category and do NOT include items {exclude_items}.",
        "unanswerable": "I am user {user_id}. Find me products under $1 in the \"NonExistentCategory999\" category.",
    },
}
