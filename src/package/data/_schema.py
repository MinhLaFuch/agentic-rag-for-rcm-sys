"""Schema/protocol constants for the data package (changing them changes the data contract, so they stay in Python)."""

REQUIRED_COLUMNS = ["user_id", "parent_asin", "rating", "timestamp"]
OPTIONAL_COLUMNS = ["title", "text", "helpful_vote", "verified_purchase"]
ITEM_ID_SEPARATOR = "::"