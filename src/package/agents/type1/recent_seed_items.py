"""Select distinct recent fit items, matching the demo's stable timestamp rule."""


def recent_seed_items(history, id2item, count=1):
    if type(count) is not int or count < 1:
        raise ValueError("seed count must be a positive integer")
    if "timestamp" not in history:
        raise ValueError("Fit history requires timestamps to select the latest seed")
    recent=history.sort_values("timestamp",kind="stable").iloc[::-1].drop_duplicates("item_idx")
    return [id2item[int(i)] for i in recent.item_idx.iloc[:count] if int(i) in id2item]
