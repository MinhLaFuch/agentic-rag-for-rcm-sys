"""Contracts of the agent evaluation (fixed in code on purpose; tunables are in configs/agent/agent_eval.yaml)."""

EVAL_SCHEMA_VERSION = 2

SEGMENTS = ("cold", "sparse", "warm")
AGENTS = ("baseline", "type1", "planner", "planner_memory")
PLANNER_AGENTS = ("planner", "planner_memory")
INFERENCE_AGENTS = ("type1", "planner", "planner_memory")  # agents whose result is turned into an answer (the baseline has none)
# Statuses of an Inference answer. Same as package.inference._schema.STATUSES (a test keeps them equal); duplicated because
# package.inference imports this package, so importing it back would be a cycle.
ANSWER_STATUSES = ("ok", "ask_user", "no_result", "tool_error")

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
