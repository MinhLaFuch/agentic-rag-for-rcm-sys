"""Canonical catalog text shared by the resource pilot and full builder."""


def format_catalog_text(title, store, main_category, categories) -> str:
    title = title or ""
    cats = ", ".join(sorted(categories))
    return (f"{title}. " + (f"Store: {store}. " if store else "")
            + (f"Main: {main_category}. " if main_category else "")
            + (f"Categories: {cats}. " if cats else "")).strip()
