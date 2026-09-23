REQUIRED_COLUMNS = ["user_id", "parent_asin", "rating", "timestamp"]
OPTIONAL_COLUMNS = ["title", "text", "helpful_vote", "verified_purchase"]

def get_config() -> tuple[list, list]:
    return (REQUIRED_COLUMNS, OPTIONAL_COLUMNS)