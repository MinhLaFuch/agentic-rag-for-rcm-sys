from ..utils import parse_list


def join_description(value, max_sentences: int = 2) -> str:
    values = parse_list(value)
    return " ".join(str(item) for item in values[:max_sentences]) or "No description"