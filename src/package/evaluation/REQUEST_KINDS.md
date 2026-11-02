# Request Kinds Documentation

This document defines the seven request kinds used in the Agent Evaluation Framework, including their expected behavior and success criteria.

## Request Kinds

### 1. Similar

**Description**: Request for items similar to seed items.

**Example**: "Show me games similar to the ones I've played before."

**Expected Behavior**:
- Agent should use collaborative filtering or similarity search
- Recommendations should be similar to provided seed items
- Should leverage item features or user interaction history

**Success Criteria**:
- Recommendations are semantically similar to seed items
- Uses appropriate similarity mechanism (ItemCF, semantic search, etc.)
- Returns items with high similarity scores

**Failure Modes**:
- Returns unrelated items
- Does not use seed information
- Returns empty results when similar items exist

---

### 2. Personalized

**Description**: Request for personalized recommendations based on user's long-term preferences.

**Example**: "Recommend games based on my preferences."

**Expected Behavior**:
- Agent should access user's profile/history
- Should use memory tool to retrieve user preferences
- Recommendations should align with user's liked categories, price range, etc.

**Success Criteria**:
- Uses memory/profile information
- Recommendations match user's top categories
- Respects user's price range preferences
- Excludes user's hated items/categories

**Failure Modes**:
- Does not access memory
- Returns generic/unpersonalized recommendations
- Ignores user's constraints or preferences

---

### 3. Constrained

**Description**: Request with explicit constraints (price, category, domain, etc.).

**Example**: "Show me games under $50 in the Action category."

**Expected Behavior**:
- Agent should parse and apply all constraints
- Should use filters appropriately in tool arguments
- All returned items must satisfy constraints

**Success Criteria**:
- All constraints are correctly applied
- No items violate constraints
- Constraint syntax is correctly parsed

**Failure Modes**:
- Ignores some constraints
- Incorrectly applies constraints (e.g., wrong operator)
- Returns items that violate constraints

---

### 4. Cold Text

**Description**: Request based only on text description, no seed items or user history.

**Example**: "I want a fun puzzle game with good graphics."

**Expected Behavior**:
- Agent should use semantic search or text-based retrieval
- Should match text description to item metadata
- May use vector similarity or keyword matching

**Success Criteria**:
- Matches semantic intent of text description
- Returns items relevant to text query
- Does not hallucinate items that don't match description

**Failure Modes**:
- Returns items unrelated to text description
- Requires seed items when none provided
- Ignores text description entirely

---

### 5. Ambiguous

**Description**: Request that is ambiguous and may require clarification.

**Example**: "Recommend something" (without specifying product type, domain, etc.)

**Expected Behavior**:
- Agent should recognize ambiguity
- Should ask clarification question rather than guessing
- After clarification, should process the clarified request

**Success Criteria**:
- Asks appropriate clarification question
- Does not make unsupported assumptions
- After clarification, processes request correctly

**Failure Modes**:
- Guesses user intent without clarification
- Provides irrelevant recommendations
- Does not ask clarification when request is ambiguous

---

### 6. Exclusion

**Description**: Request with explicit exclusion of items or categories.

**Example**: "Show me games but exclude anything I've played before" or "No sports games."

**Expected Behavior**:
- Agent should respect exclusions throughout retrieval, ranking, and final answer
- Exclusions should persist across conversation turns
- Should use exclude_item_ids or exclude_categories in tool arguments

**Success Criteria**:
- Excluded items do not appear in recommendations
- Excluded categories are filtered out
- Exclusions persist across multi-turn conversations

**Failure Modes**:
- Excluded items appear in results
- Exclusions are lost after first turn
- Does not parse exclusion syntax correctly

---

### 7. Unanswerable

**Description**: Request that cannot be answered from available information or resources.

**Example**: "Show me games released in 2050" (future date) or "What's the weather like?" (outside domain)

**Expected Behavior**:
- Agent should recognize that request cannot be answered
- Should provide explanation of limitations
- May refuse or explain why information is unavailable

**Success Criteria**:
- Recognizes impossibility or out-of-domain request
- Provides appropriate explanation
- Does not hallucinate false information

**Failure Modes**:
- Attempts to answer with fabricated information
- Does not recognize out-of-domain request
- Provides incorrect/incomplete information

---

## Scoring Guidelines

### Ambiguous Requests
- **Success**: Agent asks clarification OR provides reasonable default with acknowledgment
- **Failure**: Agent guesses without clarification and provides wrong results

### Exclusion Requests
- **Success**: All excluded items/categories are absent from results
- **Failure**: Excluded items appear in recommendations

### Unanswerable Requests
- **Success**: Agent explains limitation and refuses or provides partial valid answer
- **Failure**: Agent hallucinates or provides false information

### General Scoring
- Different request kinds should not be forced into identical scoring criteria
- Evaluate according to kind-specific success criteria
- Distinguish between "agent recognized X" and "agent did X correctly"
