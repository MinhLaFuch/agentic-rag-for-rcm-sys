"""Canonical catalog text shared by the resource pilot and full builder."""


def format_catalog_text(
    title,
    store,
    main_category,
    categories,
    *,
    brand=None,
    release_date=None,
    features=None,
) -> str:
    title = title or ""
    cats = ", ".join(sorted(categories))
    return (
        f"{title}. "
        + (f"Store: {store}. " if store else "")
        + (f"Brand: {brand}. " if brand else "")
        + (f"Release Date: {release_date}. " if release_date else "")
        + (f"Main: {main_category}. " if main_category else "")
        + (f"Categories: {cats}. " if cats else "")
        + (f"Features: {features}. " if features else "")
    ).strip()
