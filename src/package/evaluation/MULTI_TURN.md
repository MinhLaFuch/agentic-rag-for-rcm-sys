# Multi-turn Evaluation Documentation

This document explains how to use the multi-turn evaluation framework, including conversation schema, metrics, and session management.

## Overview

Multi-turn evaluation assesses agent performance across conversations with multiple turns. Unlike single-turn evaluation, multi-turn evaluation considers:
- Turn-level success and correctness
- Conversation-level success (all turns must succeed)
- Context retention across turns
- Session isolation between independent conversations
- Reference resolution to previous turns

## Conversation Schema

### Conversation
A conversation is defined with:
- `conversation_id`: Unique identifier
- `user_id`: User/session identity (if applicable)
- `turns`: List of turn inputs
- `initial_context`: Initial context before first turn
- `expected_outcome`: Expected overall conversation outcome
- `tags`: Tags for categorization
- `metadata`: Additional metadata (difficulty, tier, scenario)

### TurnInput
Each turn in a conversation includes:
- `turn_id`: Unique turn identifier
- `position`: Position in conversation (0-indexed)
- `user_request`: User's request text
- `expected_state`: Expected session state before this turn
- `expected_behavior`: Expected behavior description
- `expected_items`: Expected items to be recommended
- `expected_exclusions`: Expected items/categories to exclude
- `metadata`: Turn metadata

### ConversationResult
Result of evaluating a conversation includes:
- `conversation_id`: Conversation ID
- `turn_results`: List of individual turn results
- `conversation_success`: Whether entire conversation succeeded
- `failure_stage`: Stage where conversation failed (if applicable)
- `error`: Error message if conversation failed
- `metrics`: Conversation-level metrics
- `latency_seconds`: Total time for conversation
- `token_usage`: Token usage across all turns
- `timestamp`: ISO timestamp
- `git_sha`: Git commit SHA
- `provenance`: Additional provenance metadata

## Turn-Level Metrics

### turn_success
- **Formula**: 1 if turn executed without errors, else 0
- **Interpretation**: Execution reliability for this turn

### item_match_rate
- **Formula**: |expected_items ∩ actual_items| / |expected_items|
- **Denominator**: Number of expected items
- **Interpretation**: Fraction of expected items that were actually recommended

### exclusion_compliance
- **Formula**: 1 if all expected exclusions satisfied, else 0
- **Denominator**: None (binary metric)
- **Interpretation**: Whether exclusions were correctly applied

### reference_correctness
- **Formula**: 1 if references to previous turns resolved correctly, else 0
- **Denominator**: None (binary metric)
- **Interpretation**: Whether references (e.g., "the second one") were correctly resolved

## Conversation-Level Metrics

### turn_success_rate
- **Formula**: |successful_turns| / |total_turns|
- **Denominator**: Total number of turns
- **Interpretation**: Fraction of turns that executed successfully

### conversation_success
- **Formula**: 1 if all turns succeeded, else 0
- **Denominator**: None (binary metric)
- **Interpretation**: Whether entire conversation succeeded

### avg_item_match_rate
- **Formula**: Mean of item_match_rate across all turns
- **Denominator**: Number of turns
- **Interpretation**: Average item recommendation accuracy across conversation

### exclusion_compliance
- **Formula**: Mean of exclusion_compliance across all turns
- **Denominator**: Number of turns
- **Interpretation**: Average exclusion compliance across conversation

### context_retention
- **Formula**: 1 if session.shown_items grows monotonically, else 0
- **Denominator**: None (binary metric)
- **Interpretation**: Whether context is correctly retained (items not lost)

### reference_accuracy
- **Formula**: Mean of reference_correctness across all turns
- **Denominator**: Number of turns
- **Interpretation**: Average reference resolution accuracy

## Session Management

### Session Object
The framework uses `package.agents.session.Session` for managing conversation state:

- `turns`: List of turn history (limited by max_turns)
- `shown_items`: Items shown to user (limited by max_shown_items)
- `candidates`: Candidates from most recent turn (limited by max_candidates)
- `ranked`: Ranked candidates from most recent turn
- `constraints`: Current constraints (price, category, exclusions, etc.)
- `feedback`: User feedback on items (like/dislike)

### Session Methods
- `add_turn()`: Add a new turn to history
- `add_shown_items()`: Add items to shown list
- `set_candidates()`: Set candidates for current turn
- `update_constraints()`: Update session constraints
- `add_exclusions()`: Add items/categories to exclusion list
- `add_feedback()`: Record user feedback
- `get_valid_ids()`: Get all valid IDs for reference resolution
- `reset()`: Reset session to initial state

### Session Isolation
- Each conversation gets its own Session object
- Sessions do not share state between conversations
- Within a conversation, state persists across turns
- Session limits (max_turns, max_shown_items, max_candidates) are enforced automatically

## Multi-turn Scenarios

The framework includes predefined scenarios (M1-M7):

### M1: Price Refinement
- Turn 1: Initial request for items
- Turn 2: Refine with price constraint
- Tests: Constraint update, price filtering

### M2: Position Reference
- Turn 1: Initial request
- Turn 2: Reference item by position ("the second one")
- Tests: Reference resolution, position indexing

### M3: Exclusion Persistence
- Turn 1: Initial request
- Turn 2: Exclude an item from previous turn
- Tests: Exclusion persistence across turns

### M4: More Items
- Turn 1: Initial request
- Turn 2: Request more items without repetition
- Tests: No repeat of shown items, session.shown_items growth

### M5: Clarification Flow
- Turn 1: Ambiguous request → agent asks clarification
- Turn 2: User provides clarification → agent processes
- Tests: Clarification recognition, multi-step interaction

### M6: Topic Change
- Turn 1: Request with constraints
- Turn 2: Change topic → old constraints cleared
- Tests: Constraint clearing, topic switching

### M7: Long-term Memory
- Turn 1: Personalized request using memory
- Turn 2: Continue using memory profile
- Tests: Memory usage, profile persistence

## Running Multi-turn Evaluation

### CLI
```bash
python -m package.evaluation.multi_turn.run \
    --dataset package/evaluation/multi_turn/conversations.jsonl \
    --output experiments/agent_eval/multi_turn/results.json
```

### Programmatic
```python
from package.evaluation.multi_turn import Conversation, MultiTurnEvaluator

# Load conversation
conversation = Conversation.from_yaml("conversation.yaml")

# Create evaluator
evaluator = MultiTurnEvaluator(config={})

# Run evaluation
result = evaluator.evaluate_conversation(conversation, agent_runner, git_sha="abc123")
```

## Conversation Success vs Turn Success

A conversation succeeds only if:
1. All turns executed without errors (turn_success = 1 for all)
2. All turn-level metrics meet thresholds
3. No critical failures (e.g., session corruption)

A conversation may fail even if most turns succeed if:
- A critical turn fails (e.g., clarification turn)
- Context is lost mid-conversation
- Reference resolution fails in a critical turn

## Reporting

Multi-turn evaluation generates:
- Turn-by-turn breakdown in Markdown reports
- CSV exports with turn-level data
- Failure reports highlighting problematic turns
- Session state traces for debugging

## Testing

Multi-turn tests are in `tests/evaluation/multi_turn/`:
- `test_evaluator.py`: Schema and evaluator logic tests
- `test_with_session.py`: Integration tests with real Session objects
- Existing tests in `tests/agents/test_multi_turn.py`: M1-M7 scenario tests
