"""Contracts of the Inference layer (fixed in code on purpose; tunables are in configs/agent/inference.yaml)."""

ITEM_FIELDS = (  # what an item carries into the answer; a value the tools did not return stays None (never filled in)
    "item_id", "domain", "title", "store", "price", "average_rating", "rating_number", "main_category",
)
STATUSES = ("ok", "ask_user", "no_result", "tool_error")
MODES = ("llm", "template")
COMPOSERS = ("llm", "template")

USAGE_KEYS = ("attempts", "prompt_tokens", "completion_tokens", "latency_seconds")

METADATA_ROW_KEYS = ("items", "candidates", "ranked")  # `data` keys of the tools that return rows with an `item_id`
