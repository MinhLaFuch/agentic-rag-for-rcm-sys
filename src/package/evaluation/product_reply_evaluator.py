"""Evaluate product recommendation assistant replies for faithfulness and communication quality."""

from __future__ import annotations

import json
import re
from typing import Any


def evaluate_product_reply(request: str, items: list[dict[str, Any]], answer: str) -> dict[str, Any]:
    """
    Evaluate a product recommendation reply on two axes: faithfulness and communication.

    Args:
        request: The user's request (any language).
        items: List of selected products, each with fields: item_id, domain, title, store, price,
               average_rating, rating_number, main_category. Null fields mean information unavailable.
        answer: The assistant's reply to evaluate.

    Returns:
        JSON object with evaluation results containing:
        - claims: list of claim evaluations
        - unsupported_count: number of unsupported claims
        - total_claims: total number of claims
        - lists_all_items_in_order: whether all items appear exactly once in order
        - communication: scores for relevance, clarity, language, honesty_about_gaps
        - summary: brief summary of main strength and flaw
    """
    # Extract factual claims about products
    claims = _extract_claims(answer, items)

    # Evaluate each claim
    evaluated_claims = []
    for claim in claims:
        verdict, why = _evaluate_claim(claim["text"], claim["item_id"], items)
        evaluated_claims.append({
            "text": claim["text"],
            "item_id": claim["item_id"],
            "verdict": verdict,
            "why": why
        })

    unsupported_count = sum(1 for c in evaluated_claims if c["verdict"] == "unsupported")
    total_claims = len(evaluated_claims)

    # Check if all items are listed in order
    lists_all_items_in_order = _check_items_in_order(answer, items)

    # Score communication quality
    communication = _score_communication(request, items, answer)

    # Generate summary
    summary = _generate_summary(evaluated_claims, communication)

    return {
        "claims": evaluated_claims,
        "unsupported_count": unsupported_count,
        "total_claims": total_claims,
        "lists_all_items_in_order": lists_all_items_in_order,
        "communication": communication,
        "summary": summary
    }


def _extract_claims(answer: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Split answer into individual factual claims about products.

    Ignores greetings, formatting, and generic phrases that assert nothing about a product.
    """
    # Simple heuristic: split by sentences, then filter for product-related claims
    # This is a basic implementation; could be enhanced with NLP
    sentences = re.split(r'[.!?]+', answer)

    claims = []
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        # Skip generic phrases
        if _is_generic_phrase(sentence):
            continue

        # Try to associate with an item_id based on title matches
        item_id = _find_item_for_claim(sentence, items)

        if item_id is not None or _contains_product_reference(sentence):
            claims.append({
                "text": sentence[:100],  # Max 25 words approx
                "item_id": item_id
            })

    return claims


def _is_generic_phrase(text: str) -> bool:
    """Check if text is a generic phrase with no product claim."""
    generic_patterns = [
        r'^(here|the following|these are|below) (are|is|you can find)',
        r'^(i|we) (recommend|suggest)',
        r'^(please|feel free to)',
        r'^(hope|this helps)',
        r'^(let me know)',
        r'^(based on your request)',
        r'^(thank you|thanks)',
        r'^(sure|of course)',
    ]
    text_lower = text.lower()
    for pattern in generic_patterns:
        if re.match(pattern, text_lower):
            return True
    return False


def _contains_product_reference(text: str) -> bool:
    """Check if text contains words that might refer to product attributes."""
    product_keywords = [
        'price', 'rating', 'review', 'star', 'category', 'store', 'cheap', 'expensive',
        'wireless', 'wire', 'cable', 'feature', 'best', 'popular', 'suitable', 'good', 'great',
        'dollar', 'cents', '$', 'rated', 'rated at'
    ]
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in product_keywords)


def _find_item_for_claim(text: str, items: list[dict[str, Any]]) -> str | None:
    """Try to find which item a claim refers to based on title matching."""
    # Simple approach: check if item title words appear in the claim
    for item in items:
        title = item.get("title", "")
        if title and _has_significant_overlap(text, title):
            return item.get("item_id")
    return None


def _has_significant_overlap(text: str, title: str) -> bool:
    """Check if text and title share significant words."""
    text_words = set(text.lower().split())
    title_words = set(title.lower().split())
    overlap = text_words & title_words
    return len(overlap) >= 2  # At least 2 words in common


def _evaluate_claim(claim_text: str, item_id: str | None, items: list[dict[str, Any]]) -> tuple[str, str]:
    """
    Evaluate if a claim is supported by the item's fields.

    Returns (verdict, why) where verdict is "supported" or "unsupported".
    """
    if item_id is None:
        return "unsupported", "No item_id matched"

    # Find the item
    item = None
    for it in items:
        if it.get("item_id") == item_id:
            item = it
            break

    if item is None:
        return "unsupported", "Item not found"

    # Check if claim is supported by item fields
    claim_lower = claim_text.lower()

    # Check for price claims
    if _is_price_claim(claim_lower):
        if item.get("price") is None:
            return "unsupported", "Price field is null"
        # If the claim mentions a specific price, check if it matches
        price_match = re.search(r'\$?(\d+\.?\d*)', claim_text)
        if price_match:
            claimed_price = float(price_match.group(1))
            actual_price = float(item["price"])
            if abs(claimed_price - actual_price) > 0.01:
                return "unsupported", f"Price mismatch: {claimed_price} vs {actual_price}"
        return "supported", "Price in data"

    # Check for rating claims
    if _is_rating_claim(claim_lower):
        if item.get("average_rating") is None:
            return "unsupported", "Rating field is null"
        rating_match = re.search(r'(\d\.?\d*)\s*(star|rating|/|out of)', claim_lower)
        if rating_match:
            claimed_rating = float(rating_match.group(1))
            actual_rating = float(item["average_rating"])
            if abs(claimed_rating - actual_rating) > 0.1:
                return "unsupported", f"Rating mismatch: {claimed_rating} vs {actual_rating}"
        return "supported", "Rating in data"

    # Check for review count claims
    if _is_review_count_claim(claim_lower):
        if item.get("rating_number") is None:
            return "unsupported", "Review count field is null"
        count_match = re.search(r'(\d+)\s*(review|rating)', claim_lower)
        if count_match:
            claimed_count = int(count_match.group(1))
            actual_count = int(item["rating_number"])
            if claimed_count != actual_count:
                return "unsupported", f"Review count mismatch: {claimed_count} vs {actual_count}"
        return "supported", "Review count in data"

    # Check for store claims
    if _is_store_claim(claim_lower):
        if item.get("store") is None:
            return "unsupported", "Store field is null"
        if item["store"].lower() not in claim_lower:
            return "unsupported", "Store not in claim"
        return "supported", "Store in data"

    # Check for category claims
    if _is_category_claim(claim_lower):
        if item.get("main_category") is None:
            return "unsupported", "Category field is null"
        if item["main_category"].lower() not in claim_lower:
            return "unsupported", "Category not in claim"
        return "supported", "Category in data"

    # Check for title-based claims (what the product is)
    title = item.get("title", "")
    if title and _has_significant_overlap(claim_text, title):
        return "supported", "Supported by title"

    # Check for unsupported features/adjectives
    unsupported_features = [
        'wireless', 'best seller', 'great for kids', 'cheap', 'expensive',
        'popular', 'suitable', 'excellent', 'amazing', 'perfect'
    ]
    for feature in unsupported_features:
        if feature in claim_lower and not _supported_by_title(feature, title):
            return "unsupported", f"Feature '{feature}' not in data"

    # Default: unsupported if we can't verify
    return "unsupported", "Cannot verify from fields"


def _is_price_claim(text: str) -> bool:
    return any(word in text for word in ['price', 'cost', '$', 'dollar', 'cheap', 'expensive'])


def _is_rating_claim(text: str) -> bool:
    return any(word in text for word in ['rating', 'star', 'rated', '/5', 'out of 5'])


def _is_review_count_claim(text: str) -> bool:
    return any(word in text for word in ['review', 'reviews'])


def _is_store_claim(text: str) -> bool:
    return any(word in text for word in ['store', 'sold by', 'available at'])


def _is_category_claim(text: str) -> bool:
    return any(word in text for word in ['category', 'type', 'belongs to'])


def _supported_by_title(feature: str, title: str) -> bool:
    """Check if a feature is mentioned in the title."""
    return feature.lower() in title.lower()


def _check_items_in_order(answer: str, items: list[dict[str, Any]]) -> bool:
    """
    Check if every item appears exactly once in the given order, and no product outside items is mentioned.
    """
    # Extract item mentions from answer
    mentioned_items = []
    for item in items:
        title = item.get("title", "")
        if title and title.lower() in answer.lower():
            mentioned_items.append(item["item_id"])

    # Check if all items are mentioned exactly once
    if len(mentioned_items) != len(items):
        return False

    # Check order
    for i, item in enumerate(items):
        if mentioned_items[i] != item["item_id"]:
            return False

    return True


def _score_communication(request: str, items: list[dict[str, Any]], answer: str) -> dict[str, int]:
    """Score communication quality on four criteria (1-5 scale)."""
    return {
        "relevance": _score_relevance(request, items, answer),
        "clarity": _score_clarity(answer),
        "language": _score_language(request, answer),
        "honesty_about_gaps": _score_honesty(items, answer)
    }


def _score_relevance(request: str, items: list[dict[str, Any]], answer: str) -> int:
    """Score if reply addresses what the request asked."""
    # Basic check: do the items match the request type?
    # This is a simplified version
    request_lower = request.lower()
    answer_lower = answer.lower()

    # Check for category mentions
    for item in items:
        category = item.get("main_category", "")
        if category and category.lower() in request_lower:
            if category.lower() in answer_lower:
                return 5
            return 3

    # Check for price constraints
    if any(word in request_lower for word in ['under', 'below', 'less than', 'cheap', 'budget']):
        if any(word in answer_lower for word in ['price', '$', 'dollar']):
            return 5
        return 3

    return 4  # Default to good if no obvious issues


def _score_clarity(answer: str) -> int:
    """Score if reply is easy to read, short, uncluttered."""
    lines = answer.split('\n')
    avg_line_length = sum(len(line) for line in lines) / len(lines) if lines else 0

    # Prefer shorter lines (1-2 lines per product)
    if avg_line_length < 100:
        return 5
    elif avg_line_length < 200:
        return 4
    elif avg_line_length < 300:
        return 3
    else:
        return 2


def _score_language(request: str, answer: str) -> int:
    """Score if reply is in the same language as request."""
    # Very basic check: if request is English, answer should be English
    # This is a placeholder; real implementation would use language detection
    if request.isascii() and answer.isascii():
        return 5
    elif not request.isascii() and not answer.isascii():
        return 5
    return 3  # Default to acceptable


def _score_honesty(items: list[dict[str, Any]], answer: str) -> int:
    """Score if reply acknowledges unavailable information instead of guessing."""
    answer_lower = answer.lower()

    # Check if answer mentions unavailable info for null fields
    has_null_fields = any(
        item.get("price") is None or
        item.get("average_rating") is None or
        item.get("rating_number") is None
        for item in items
    )

    if not has_null_fields:
        return 5  # No null fields, nothing to hide

    # Check if answer acknowledges unavailability
    if any(phrase in answer_lower for phrase in ['unavailable', 'not available', 'no data', 'unknown']):
        return 5

    # Check if answer tries to guess null values
    if any(item.get("price") is None and '$' in answer_lower for item in items):
        return 1

    return 3  # Default to acceptable


def _generate_summary(claims: list[dict[str, Any]], communication: dict[str, int]) -> str:
    """Generate a brief summary of main strength and flaw (max 40 words)."""
    supported_count = sum(1 for c in claims if c["verdict"] == "supported")
    total_claims = len(claims)

    if total_claims == 0:
        return "No product claims made"

    if supported_count == total_claims:
        strength = "All claims supported"
    elif supported_count > total_claims / 2:
        strength = "Most claims supported"
    else:
        strength = "Many claims unsupported"

    avg_comm = sum(communication.values()) / len(communication)
    if avg_comm >= 4:
        flaw = "Minor communication issues"
    elif avg_comm >= 3:
        flaw = "Acceptable communication"
    else:
        flaw = "Poor communication"

    return f"{strength}; {flaw}"
