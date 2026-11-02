# Metrics and Formulas

This document defines all metrics used in the Agent Evaluation Framework, including their formulas, denominators, and interpretation.

## Layer 1: Recommendation Quality Metrics

### Precision@K
- **Formula**: |recommended ∩ relevant| / |recommended|
- **Denominator**: Number of recommended items
- **Interpretation**: Fraction of recommended items that are relevant

### Recall@K
- **Formula**: |recommended ∩ relevant| / |relevant|
- **Denominator**: Number of relevant items in candidate universe
- **Interpretation**: Fraction of relevant items that are recommended

### Hit Rate@K
- **Formula**: 1 if at least one relevant item in top K, else 0
- **Denominator**: None (binary metric)
- **Interpretation**: Whether at least one relevant item appears in top K

### NDCG@K
- **Formula**: DCG@K / IDCG@K
- **DCG@K**: Σ (2^relevance - 1) / log2(i + 1)
- **IDCG@K**: DCG@K for ideal ranking
- **Denominator**: IDCG@K
- **Interpretation**: Normalized discounted cumulative gain

### MRR@K
- **Formula**: 1 / rank(first_relevant) if relevant in top K, else 0
- **Denominator**: None (based on rank)
- **Interpretation**: Reciprocal rank of first relevant item

### MAP@K
- **Formula**: Mean of AP@K across all queries
- **AP@K**: Σ (precision at relevant positions) / number of relevant items
- **Denominator**: Number of queries
- **Interpretation**: Mean average precision

### Seen Item Rate
- **Formula**: |recommended ∩ user_history| / |recommended|
- **Denominator**: Number of recommended items
- **Interpretation**: Fraction of recommended items user has seen before

### Seed-in-Result
- **Formula**: 1 if any seed item in results, else 0
- **Denominator**: None (binary metric)
- **Interpretation**: Whether seed items appear in recommendations

### Distinct Domains
- **Formula**: Number of distinct domains in recommendations
- **Denominator**: None (count metric)
- **Interpretation**: Diversity of recommendations across domains

## Layer 2: Task Success Metrics

### Task Success
- **Formula**: 1 if all task constraints satisfied, else 0
- **Denominator**: None (binary metric)
- **Interpretation**: Whether the agent successfully completed the task

### Constraint Satisfaction
- **Formula**: |satisfied_constraints| / |required_constraints|
- **Denominator**: Number of required constraints
- **Interpretation**: Fraction of constraints satisfied

### Price Unknown Rate
- **Formula**: |requests_with_unknown_price| / |total_requests|
- **Denominator**: Total number of requests
- **Interpretation**: Fraction of requests where price could not be determined

### Clarification Tracking
- **Formula**: 1 if agent asked clarification, else 0
- **Denominator**: None (binary metric)
- **Interpretation**: Whether agent recognized ambiguity and asked for clarification

### Grounded Answer Condition
- **Formula**: 1 if answer has evidence support, else 0
- **Denominator**: None (binary metric)
- **Interpretation**: Whether answer is grounded in retrieved evidence

### Preference Alignment (love_alignment)
- **Formula**: |recommended ∩ loved_items| / |recommended|
- **Denominator**: Number of recommended items
- **Interpretation**: Fraction of recommendations that match user's loved items

### Negative Preference Violation (hate_violation_rate)
- **Formula**: |recommended ∩ hated_items| / |recommended|
- **Denominator**: Number of recommended items
- **Interpretation**: Fraction of recommendations that violate user's dislikes

### Exclusion Compliance
- **Formula**: 1 if all exclusions respected, else 0
- **Denominator**: None (binary metric)
- **Interpretation**: Whether excluded items/categories were correctly excluded

## Layer 3: Retrieval and Grounding Metrics

### Target in Pool
- **Formula**: 1 if target in initial candidate universe, else 0
- **Denominator**: None (binary metric)
- **Interpretation**: Whether target is available in the data

### Retrieved by Stage
- **Formula**: For each stage S_i: 1 if target retrieved at S_i, else 0
- **Denominator**: None (binary per stage)
- **Interpretation**: At which stage target was retrieved

### Query Hit Any Title Token
- **Formula**: 1 if query matches any token in item title, else 0
- **Denominator**: None (binary metric)
- **Interpretation**: Whether query has lexical match with item title

### Rank in Pool
- **Formula**: Position of target in candidate ranking
- **Denominator**: None (position metric)
- **Interpretation**: Where target appears in ranking

## Layer 4: Planning and Execution Metrics

### Plan Validity
- **Formula**: 1 if plan is valid, else 0
- **Denominator**: None (binary metric)
- **Interpretation**: Whether plan structure is correct

### Planning Attempts
- **Formula**: Number of planning attempts
- **Denominator**: None (count metric)
- **Interpretation**: How many times planner was invoked

### Truncation
- **Formula**: 1 if plan was truncated, else 0
- **Denominator**: None (binary metric)
- **Interpretation**: Whether plan exceeded token limits

### Step Count
- **Formula**: Number of steps in plan
- **Denominator**: None (count metric)
- **Interpretation**: Plan complexity

### Step Success Rate
- **Formula**: |successful_steps| / |total_steps|
- **Denominator**: Total number of steps
- **Interpretation**: Fraction of steps that executed successfully

### Reflection Count
- **Formula**: Number of reflection attempts
- **Denominator**: None (count metric)
- **Interpretation**: How many times reflection was triggered

### First-Attempt Success
- **Formula**: 1 if first attempt succeeded, else 0
- **Denominator**: None (binary metric)
- **Interpretation**: Whether plan succeeded on first try

### Tool Selection
- **Formula**: |correct_tools| / |total_tools|
- **Denominator**: Total number of tools in plan
- **Interpretation**: Fraction of correct tool selections

### Argument Validity
- **Formula**: |valid_arguments| / |total_arguments|
- **Denominator**: Total number of tool arguments
- **Interpretation**: Fraction of valid tool arguments

## Layer 5: Efficiency and Cost Metrics

### Prompt Tokens
- **Formula**: Total input tokens across all LLM calls
- **Denominator**: None (count metric)
- **Interpretation**: Total input token usage

### Completion Tokens
- **Formula**: Total output tokens across all LLM calls
- **Denominator**: None (count metric)
- **Interpretation**: Total output token usage

### LLM Latency
- **Formula**: Total time spent waiting for LLM responses
- **Denominator**: None (time metric, seconds)
- **Interpretation**: Total LLM inference time

### Tool Latency
- **Formula**: Total time spent executing tools
- **Denominator**: None (time metric, seconds)
- **Interpretation**: Total tool execution time

### Wall Time
- **Formula**: Total end-to-end execution time
- **Denominator**: None (time metric, seconds)
- **Interpretation: Total request processing time

### Cost per Request
- **Formula**: Token cost / number of requests
- **Denominator**: Number of requests
- **Interpretation**: Average cost per request

### Cost per Successful Request
- **Formula**: Token cost / number of successful requests
- **Denominator**: Number of successful requests
- **Interpretation**: Average cost per successful request

## Component-Level Metrics

### Execution Reliability
- **Formula**: |successful_executions| / |total_executions|
- **Denominator**: Total number of component executions
- **Interpretation**: Fraction of times component ran without errors

### Functional Correctness
- Component-specific metrics measured only when execution succeeds
- **Interpretation**: Whether component behavior is correct

## Multi-turn Metrics

### Turn Success Rate
- **Formula**: |successful_turns| / |total_turns|
- **Denominator**: Total number of turns
- **Interpretation**: Fraction of turns that executed successfully

### Conversation Success Rate
- **Formula**: 1 if all turns succeeded, else 0
- **Denominator**: None (binary metric)
- **Interpretation**: Whether entire conversation succeeded

### Context Retention
- **Formula**: 1 if session state grows monotonically, else 0
- **Denominator**: None (binary metric)
- **Interpretation**: Whether context is correctly retained across turns

### Reference Resolution Accuracy
- **Formula**: |correct_references| / |total_references|
- **Denominator**: Total number of references to previous turns
- **Interpretation**: Fraction of references correctly resolved

## Statistical Metrics

### Bootstrap Confidence Interval
- **Formula**: Percentile of bootstrap sample means
- **Denominator**: None (statistical estimate)
- **Interpretation**: Range containing true mean with specified confidence

### P-value
- **Formula**: Probability of observing data if null hypothesis is true
- **Denominator**: None (statistical estimate)
- **Interpretation**: Evidence against null hypothesis

### Standard Deviation
- **Formula**: sqrt(Σ(x - mean)² / (n - 1))
- **Denominator**: Number of samples
- **Interpretation**: Variability of metric values
