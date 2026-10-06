"""Contracts of the agent evaluation (fixed in code on purpose; tunables are in configs/agent_eval.yaml)."""

SEGMENTS = ("cold", "sparse", "warm")
AGENTS = ("baseline", "type1", "planner", "planner_memory")
PLANNER_AGENTS = ("planner", "planner_memory")

# request kind -> user segments it is drawn from ("none" = no user in the request)
KIND_SEGMENTS = {
    "similar": ("sparse", "warm"),       # "I just bought X, suggest similar"         (history only, honest)
    "personalized": ("sparse", "warm"),  # "suggest things that fit my buying habits" (history only, honest; isolates MemoryTool)
    "constrained": ("sparse", "warm"),   # category + price ceiling built from a held-out item   (ORACLE constraints)
    "cold_text": ("cold",),              # new user who only says what they want                 (ORACLE category)
    "ambiguous": ("none",),              # missing information: the right move is to ask back
}
KINDS = tuple(KIND_SEGMENTS)
ORACLE_KINDS = ("constrained", "cold_text")  # built from held-out items: an upper-bound scenario, not a real query log

# Ordered groups of tools a good plan visits (any tool of a group counts, groups in this order).
# Groups are filtered by the tools the agent actually has, so a planner without MemoryTool is not penalised for it.
REFERENCE_PLANS = {
    "similar": (("ItemCFTool",), ("RecoModelTool",)),
    "personalized": (("MemoryTool",), ("SemanticSearchTool", "SQLTool"), ("RecoModelTool",)),
    "constrained": (("SemanticSearchTool", "SQLTool"), ("RecoModelTool",)),
    "cold_text": (("SemanticSearchTool", "SQLTool"), ("RecoModelTool",)),
    "ambiguous": (),
}

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
    },
}
