"""
Evaluate product recommendation assistant replies using Jev (TypeSafe AI) for judgments.

This evaluator uses Jev's structured decision capabilities (Noul/Score) instead of
generating free-form text. It separates concerns:
- Claim extraction: rule-based heuristics (or LLM-based if configured)
- Faithfulness: Jev Noul questions for each claim
- Communication: Jev Score questions for each criterion
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from ..judge import JevClient


def evaluate_product_reply_with_jev(
    request: str,
    items: list[dict[str, Any]],
    answer: str,
    config_path: Path | None = None,
) -> dict[str, Any]:
    """
    Evaluate a product recommendation reply using Jev for judgments.

    Args:
        request: The user's request (any language).
        items: List of selected products, each with fields: item_id, domain, title, store, price,
               average_rating, rating_number, main_category. Null fields mean information unavailable.
        answer: The assistant's reply to evaluate.
        config_path: Path to judge.yaml config. If None, uses default configs/agent/judge.yaml.

    Returns:
        JSON object with evaluation results containing:
        - claims: list of claim evaluations with Jev's noul probability and confidence
        - unsupported_count: number of unsupported claims (noul < threshold)
        - total_claims: total number of claims
        - lists_all_items_in_order: whether all items appear exactly once in order
        - communication: scores from Jev Score questions
        - summary: brief summary of main strength and flaw
        - usage: Jev API token usage
    """
    # Load config
    if config_path is None:
        config_path = Path(__file__).parent.parent.parent / "configs" / "agent" / "judge.yaml"

    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # Initialize Jev client
    jev = JevClient(
        api_key=config.get("api_key"),
        model=config.get("model", "jev-latest"),
        base_url=config.get("base_url", "https://api.typesafe.ai"),
        timeout=config.get("timeout_seconds", 30.0),
    )

    try:
        # Extract claims (rule-based for now)
        claims = _extract_claims(answer, items)

        # Evaluate faithfulness with Jev
        evaluated_claims, faithfulness_usage = _evaluate_faithfulness_with_jev(
            claims, items, jev, config
        )

        unsupported_count = sum(
            1 for c in evaluated_claims
            if c["verdict"] == "unsupported"
        )
        total_claims = len(evaluated_claims)

        # Check if all items are listed in order
        lists_all_items_in_order = _check_items_in_order(answer, items)

        # Evaluate communication with Jev
        communication, communication_usage = _evaluate_communication_with_jev(
            request, answer, jev, config
        )

        # Generate summary
        summary = _generate_summary(evaluated_claims, communication)

        # Combine usage
        total_usage = {
            "input_tokens": faithfulness_usage.get("input_tokens", 0) + communication_usage.get("input_tokens", 0),
            "output_tokens": faithfulness_usage.get("output_tokens", 0) + communication_usage.get("output_tokens", 0),
        }

        return {
            "claims": evaluated_claims,
            "unsupported_count": unsupported_count,
            "total_claims": total_claims,
            "lists_all_items_in_order": lists_all_items_in_order,
            "communication": communication,
            "summary": summary,
            "usage": total_usage,
        }
    finally:
        jev.close()


def _extract_claims(answer: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Split answer into individual factual claims about products using rule-based heuristics.
    """
    sentences = re.split(r'[.!?]+', answer)

    claims = []
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        if _is_generic_phrase(sentence):
            continue

        item_id = _find_item_for_claim(sentence, items)

        if item_id is not None or _contains_product_reference(sentence):
            claims.append({
                "text": sentence[:100],
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
    return len(overlap) >= 2


def _evaluate_faithfulness_with_jev(
    claims: list[dict[str, Any]],
    items: list[dict[str, Any]],
    jev: JevClient,
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """
    Evaluate each claim using Jev Noul questions.

    Batches all claims into a single Jev call for efficiency.
    State = list of {item fields, claim}, questions = one Noul per claim.
    """
    support_threshold = config.get("evaluation", {}).get("faithfulness", {}).get("support_threshold", 0.7)
    instructions = config.get("evaluation", {}).get("faithfulness", {}).get("instructions", "")
    enable_long_context = config.get("enable_long_context", False)

    # Build evaluated_claims with preliminary verdicts for items without data
    evaluated_claims = []
    batch_claims = []  # Claims to batch for Jev
    claim_indices = []  # Map batch index back to original claim index

    for i, claim in enumerate(claims):
        item_id = claim["item_id"]
        claim_text = claim["text"]

        if item_id is None:
            evaluated_claims.append({
                "text": claim_text,
                "item_id": None,
                "verdict": "unsupported",
                "why": "No item_id matched",
                "noul": 0.0,
                "confidence": 0.0,
            })
            continue

        # Find the item
        item = None
        for it in items:
            if it.get("item_id") == item_id:
                item = it
                break

        if item is None:
            evaluated_claims.append({
                "text": claim_text,
                "item_id": item_id,
                "verdict": "unsupported",
                "why": "Item not found",
                "noul": 0.0,
                "confidence": 0.0,
            })
            continue

        # Add to batch
        batch_claims.append({
            "item": item,
            "claim": claim_text,
            "item_id": item_id,
        })
        claim_indices.append(i)
        # Placeholder in evaluated_claims
        evaluated_claims.append(None)

    # Batch evaluate with Jev
    if batch_claims:
        try:
            # Build state as list of claim contexts
            state = batch_claims

            # Build one Noul question per claim
            questions = {}
            for i, claim_context in enumerate(batch_claims):
                questions[f"claim_{i}"] = {
                    "type": "noul",
                    "instructions": instructions,
                }

            result = jev.evaluate(
                state=state,
                questions=questions,
                enable_long_context=enable_long_context,
            )

            # Extract results and fill evaluated_claims
            answers = result.get("answers", {})
            usage = result.get("usage", {"input_tokens": 0, "output_tokens": 0})

            for i, claim_context in enumerate(batch_claims):
                answer_key = f"claim_{i}"
                answer_data = answers.get(answer_key, {})
                noul = answer_data.get("noul", 0.0)
                confidence = answer_data.get("confidence", 0.0)

                verdict = "supported" if noul >= support_threshold else "unsupported"
                why = f"Jev noul={noul:.2f}, threshold={support_threshold}"

                original_index = claim_indices[i]
                evaluated_claims[original_index] = {
                    "text": claim_context["claim"],
                    "item_id": claim_context["item_id"],
                    "verdict": verdict,
                    "why": why,
                    "noul": noul,
                    "confidence": confidence,
                }

        except Exception as e:
            # Fallback: mark all batched claims as unsupported
            for i, claim_context in enumerate(batch_claims):
                original_index = claim_indices[i]
                evaluated_claims[original_index] = {
                    "text": claim_context["claim"],
                    "item_id": claim_context["item_id"],
                    "verdict": "unsupported",
                    "why": f"Jev error: {str(e)}",
                    "noul": 0.0,
                    "confidence": 0.0,
                }
            usage = {"input_tokens": 0, "output_tokens": 0}
    else:
        usage = {"input_tokens": 0, "output_tokens": 0}

    return evaluated_claims, usage


def _evaluate_communication_with_jev(
    request: str,
    answer: str,
    jev: JevClient,
    config: dict[str, Any],
) -> tuple[dict[str, int], dict[str, int]]:
    """
    Evaluate communication quality using Jev Score questions.

    Evaluates 4 criteria: relevance, clarity, language, honesty_about_gaps.
    """
    criteria_config = config.get("evaluation", {}).get("communication", {}).get("criteria", {})
    enable_long_context = config.get("enable_long_context", False)

    state = {
        "request": request,
        "answer": answer,
    }

    # Build questions for all 4 criteria in one call
    questions = {}
    for criterion, criterion_config in criteria_config.items():
        questions[criterion] = {
            "type": "score",
            "instructions": criterion_config.get("instructions", ""),
            "criteria": criterion_config.get("rubric", []),
        }

    try:
        result, usage = jev.evaluate(
            state=state,
            questions=questions,
            enable_long_context=enable_long_context,
        )

        # Extract scores (convert from float 0-4 to int 1-5)
        communication = {}
        for criterion, answer_data in result.get("answers", {}).items():
            score = answer_data.get("score", 0)
            # Jev Score returns 0-indexed, convert to 1-5
            communication[criterion] = int(score) + 1

        return communication, usage
    except Exception as e:
        # Fallback to simple scoring if Jev fails
        print(f"Jev communication evaluation failed: {e}")
        return {
            "relevance": 3,
            "clarity": 3,
            "language": 3,
            "honesty_about_gaps": 3,
        }, {"input_tokens": 0, "output_tokens": 0}


def _check_items_in_order(answer: str, items: list[dict[str, Any]]) -> bool:
    """Check if every item appears exactly once in the given order."""
    mentioned_items = []
    for item in items:
        title = item.get("title", "")
        if title and title.lower() in answer.lower():
            mentioned_items.append(item["item_id"])

    if len(mentioned_items) != len(items):
        return False

    for i, item in enumerate(items):
        if mentioned_items[i] != item["item_id"]:
            return False

    return True


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
