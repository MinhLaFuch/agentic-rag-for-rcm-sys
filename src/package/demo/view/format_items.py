"""Format danh sách DemoItem thành bảng cho UI."""

from __future__ import annotations

from ._dataclass import DemoItem


def format_items(items: list[DemoItem]) -> list[list[str]]:
    """Format danh sách item thành bảng (cột: tên, domain, giá, rating, store)."""
    rows = []
    for item in items:
        price_str = f"${item.price:.2f}" if item.price is not None else "—"
        rating_str = f"{item.average_rating:.1f}" if item.average_rating is not None else "—"
        rows.append([
            item.title,
            item.domain,
            price_str,
            rating_str,
            item.store or "—",
        ])
    return rows
