# Jev (TypeSafe AI) Evaluator for Product Recommendation Replies

This module integrates Jev, TypeSafe AI's System One model, as an LLM-as-a-judge for evaluating product recommendation assistant replies.

## What is Jev?

Jev is a "System One" model that returns **structured decisions** (Choice/Score/Noul) rather than free-form text. It takes a state (JSON/string/array) and typed questions, returning answers with probabilities and confidence. Unlike traditional LLMs, Jev does not generate explanatory text.

- **API**: https://docs.typesafe.ai/api
- **Model**: `jev-latest` (or specific versions like `jev-1.14.0`)
- **Auth**: Requires `TYPESAFE_API_KEY` environment variable

## Architecture

The evaluator separates concerns:

1. **Claim Extraction**: Rule-based heuristics (configurable to use LLM later)
   - Extracts factual claims from the assistant's reply
   - Associates claims with item IDs via title matching

2. **Faithfulness Evaluation**: Jev Noul questions
   - For each claim: state = `{item fields, claim}`
   - Question: "Is this claim supported by the item's fields?"
   - Returns: `noul` (0-1 probability) + `confidence`
   - Verdict: "supported" if noul >= threshold (default 0.7)

3. **Communication Evaluation**: Jev Score questions
   - 4 criteria: relevance, clarity, language, honesty_about_gaps
   - Each scored 1-5 using a rubric
   - All 4 questions batched in a single Jev call

## Installation

Add `httpx` to dependencies (already added in pyproject.toml):

```bash
pip install httpx
```

## Configuration

Edit `configs/agent/judge.yaml`:

```yaml
api_key: ${TYPESAFE_API_KEY:-}  # Set via env var
model: "jev-latest"
base_url: "https://api.typesafe.ai"
timeout_seconds: 30.0

evaluation:
  faithfulness:
    support_threshold: 0.7  # Noul >= this = supported
    instructions: "..."     # Prompt for faithfulness judgment

  communication:
    criteria:
      relevance:
        instructions: "..."
        rubric: ["Poor", "Fair", "Good", "Very good", "Excellent"]
      # ... same for clarity, language, honesty_about_gaps
```

## Usage

### Python API

```python
from package.evaluation import evaluate_product_reply_with_jev

result = evaluate_product_reply_with_jev(
    request="I need a wireless mouse under $30",
    items=[
        {
            "item_id": "B001",
            "domain": "electronics",
            "title": "Logitech Wireless Mouse M185",
            "store": "Amazon",
            "price": 19.99,
            "average_rating": 4.5,
            "rating_number": 1234,
            "main_category": "Electronics"
        }
    ],
    answer="Here's a great wireless mouse: Logitech M185 for $19.99 with 4.5 stars from 1234 reviews."
)

print(result)
# {
#   "claims": [
#     {
#       "text": "Here's a great wireless mouse...",
#       "item_id": "B001",
#       "verdict": "unsupported",  # "great" not in data
#       "why": "Jev noul=0.45, threshold=0.7",
#       "noul": 0.45,
#       "confidence": 0.8
#     }
#   ],
#   "unsupported_count": 1,
#   "total_claims": 1,
#   "lists_all_items_in_order": true,
#   "communication": {
#     "relevance": 5,
#     "clarity": 4,
#     "language": 5,
#     "honesty_about_gaps": 5
#   },
#   "summary": "Many claims unsupported; Acceptable communication",
#   "usage": {"input_tokens": 120, "output_tokens": 24}
# }
```

### Command Line

```bash
# Single evaluation
PYTHONPATH=. python scripts/evaluation/evaluate_with_jev.py \
  --request "I need a wireless mouse under $30" \
  --items-file items.json \
  --answer "Here's a great wireless mouse: Logitech M185 for $19.99..."

# Batch evaluation from JSONL
PYTHONPATH=. python scripts/evaluation/evaluate_with_jev.py \
  --input-file evaluations.jsonl \
  --output-file results.json

# With custom config
PYTHONPATH=. python scripts/evaluation/evaluate_with_jev.py \
  --input-file evaluations.jsonl \
  --config-file custom_judge.yaml
```

## Input Format

### Single Request

JSONL file (one line per evaluation):
```json
{"request": "...", "items": [...], "answer": "..."}
{"request": "...", "items": [...], "answer": "..."}
```

### Items Array

```json
[
  {
    "item_id": "B001",
    "domain": "electronics",
    "title": "Logitech Wireless Mouse M185",
    "store": "Amazon",
    "price": 19.99,
    "average_rating": 4.5,
    "rating_number": 1234,
    "main_category": "Electronics"
  }
]
```

Null fields indicate unavailable information.

## Output Format

```json
{
  "claims": [
    {
      "text": "claim text",
      "item_id": "B001",
      "verdict": "supported|unsupported",
      "why": "Jev noul=0.85, threshold=0.7",
      "noul": 0.85,
      "confidence": 0.9
    }
  ],
  "unsupported_count": 1,
  "total_claims": 5,
  "lists_all_items_in_order": true,
  "communication": {
    "relevance": 5,
    "clarity": 4,
    "language": 5,
    "honesty_about_gaps": 5
  },
  "summary": "Most claims supported; Minor communication issues",
  "usage": {
    "input_tokens": 250,
    "output_tokens": 48
  }
}
```

## Confidence Calibration

Jev returns `confidence` scores alongside its decisions. To calibrate:

1. Create a test set with 10 known-good claims and 10 known-bad claims
2. Run the evaluator
3. Plot Jev's `noul` probabilities vs ground truth
4. Adjust `support_threshold` in config if needed

## Cost

Jev pricing (as of Oct 2026):
- $42 per billion input tokens (Btok)
- $0.042 per million input tokens (Mtok)
- Output tokens are free

Typical evaluation:
- Faithfulness: ~50-100 input tokens per claim (batched)
- Communication: ~100-200 input tokens total (4 questions in one call)

## Comparison with Rule-Based Evaluator

The original `product_reply_evaluator.py` uses rule-based heuristics:
- **Pros**: Fast, no API cost, deterministic
- **Cons**: Limited claim detection, rigid matching

Jev-based evaluator:
- **Pros**: More nuanced judgment, handles edge cases better
- **Cons**: API cost, requires network access

Choose based on your needs:
- Use rule-based for fast iteration/local testing
- Use Jev for production evaluation/research

## Troubleshooting

**Error: TYPESAFE_API_KEY not set**
```bash
export TYPESAFE_API_KEY=your_key_here
```

**Jev API timeout**
Increase `timeout_seconds` in `judge.yaml`.

**Batch evaluation fails for large state**
Set `enable_long_context: true` in `judge.yaml` (requires TypeSafe-Danger-Zone-Long-Context header).

## Future Enhancements

- LLM-based claim extraction (using the planner LLM)
- Streaming evaluation for large batches
- Caching to avoid re-evaluating identical claims
- Integration with existing agent evaluation pipeline
