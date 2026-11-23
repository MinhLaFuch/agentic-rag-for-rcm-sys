# Agent Evaluation Report

**Generated**: 2026-11-18T19:31:15.467285+00:00

## Executive Summary

- **scored_rows**: 152
- **requests**: 152
- **agents**: planner
- **k**: 10

## Request Kind Analysis

| Request Kind | Metric | Mean | Std |
|--------------|--------|------|-----|
| planner/ambiguous | answer_status_ok | 0.0000 | 0.0000 |
| planner/ambiguous | asked_clarification | 1.0000 | 0.0000 |
| planner/ambiguous | first_attempt_ok | 1.0000 | 0.0000 |
| planner/ambiguous | invented_ids | 0.0000 | 0.0000 |
| planner/ambiguous | n_steps | 0.0000 | 0.0000 |
| planner/ambiguous | reflections | 0.0000 | 0.0000 |
| planner/ambiguous | task_success | 1.0000 | 0.0000 |
| planner/ambiguous | tool_selection_ok | 1.0000 | 0.0000 |
| planner/cold_text | answer_fallback | 0.0000 | 0.0000 |
| planner/cold_text | answer_grounded | 1.0000 | 0.0000 |
| planner/cold_text | answer_status_ok | 0.6000 | 0.4899 |
| planner/cold_text | asked_clarification | 0.0500 | 0.2179 |
| planner/cold_text | constraint_satisfaction | 0.5700 | 0.4776 |
| planner/cold_text | first_attempt_ok | 0.6500 | 0.4770 |
| planner/cold_text | hit_rate@10 | 0.0000 | 0.0000 |
| planner/cold_text | invented_ids | 0.0000 | 0.0000 |
| planner/cold_text | map@10 | 0.0000 | 0.0000 |
| planner/cold_text | mrr@10 | 0.0000 | 0.0000 |
| planner/cold_text | n_steps | 2.8500 | 0.6538 |
| planner/cold_text | ndcg@10 | 0.0000 | 0.0000 |
| planner/cold_text | precision@10 | 0.0000 | 0.0000 |
| planner/cold_text | recall@10 | 0.0000 | 0.0000 |
| planner/cold_text | reflections | 0.0000 | 0.0000 |
| planner/cold_text | task_success | 0.5000 | 0.5000 |
| planner/cold_text | tool_selection_ok | 0.9500 | 0.2179 |
| planner/exclusion | answer_fallback | 0.0000 | 0.0000 |
| planner/exclusion | answer_grounded | 1.0000 | 0.0000 |
| planner/exclusion | answer_status_ok | 0.2750 | 0.4465 |
| planner/exclusion | asked_clarification | 0.5000 | 0.5000 |
| planner/exclusion | exclusion_compliance | 0.8182 | 0.3157 |
| planner/exclusion | first_attempt_ok | 0.7750 | 0.4176 |
| planner/exclusion | hit_rate@10 | 0.0000 | 0.0000 |
| planner/exclusion | invented_ids | 0.0000 | 0.0000 |
| planner/exclusion | map@10 | 0.0000 | 0.0000 |
| planner/exclusion | mrr@10 | 0.0000 | 0.0000 |
| planner/exclusion | n_steps | 1.5000 | 1.5000 |
| planner/exclusion | ndcg@10 | 0.0000 | 0.0000 |
| planner/exclusion | precision@10 | 0.0000 | 0.0000 |
| planner/exclusion | recall@10 | 0.0000 | 0.0000 |
| planner/exclusion | reflections | 0.0000 | 0.0000 |
| planner/exclusion | task_success | 0.2000 | 0.4000 |
| planner/exclusion | tool_selection_ok | 0.2750 | 0.4465 |
| planner/personalized | answer_fallback | 0.0000 | 0.0000 |
| planner/personalized | answer_grounded | 1.0000 | 0.0000 |
| planner/personalized | answer_status_ok | 0.7750 | 0.4176 |
| planner/personalized | asked_clarification | 0.2250 | 0.4176 |
| planner/personalized | first_attempt_ok | 1.0000 | 0.0000 |
| planner/personalized | hit_rate@10 | 0.0000 | 0.0000 |
| planner/personalized | invented_ids | 0.0000 | 0.0000 |
| planner/personalized | map@10 | 0.0000 | 0.0000 |
| planner/personalized | mrr@10 | 0.0000 | 0.0000 |
| planner/personalized | n_steps | 2.3250 | 1.2527 |
| planner/personalized | ndcg@10 | 0.0000 | 0.0000 |
| planner/personalized | precision@10 | 0.0000 | 0.0000 |
| planner/personalized | recall@10 | 0.0000 | 0.0000 |
| planner/personalized | reflections | 0.0000 | 0.0000 |
| planner/similar | answer_fallback | 0.0000 | 0.0000 |
| planner/similar | answer_grounded | 1.0000 | 0.0000 |
| planner/similar | answer_status_ok | 0.9500 | 0.2179 |
| planner/similar | asked_clarification | 0.0000 | 0.0000 |
| planner/similar | first_attempt_ok | 0.9500 | 0.2179 |
| planner/similar | hit_rate@10 | 0.0000 | 0.0000 |
| planner/similar | invented_ids | 0.0000 | 0.0000 |
| planner/similar | map@10 | 0.0000 | 0.0000 |
| planner/similar | mrr@10 | 0.0000 | 0.0000 |
| planner/similar | n_steps | 3.0000 | 0.0000 |
| planner/similar | ndcg@10 | 0.0000 | 0.0000 |
| planner/similar | precision@10 | 0.0000 | 0.0000 |
| planner/similar | recall@10 | 0.0000 | 0.0000 |
| planner/similar | reflections | 0.0000 | 0.0000 |
| planner/similar | task_success | 0.9500 | 0.2179 |
| planner/similar | tool_selection_ok | 1.0000 | 0.0000 |
| planner/unanswerable | answer_status_ok | 0.0000 | 0.0000 |
| planner/unanswerable | asked_clarification | 0.3333 | 0.4714 |
| planner/unanswerable | first_attempt_ok | 0.3333 | 0.4714 |
| planner/unanswerable | invented_ids | 0.0000 | 0.0000 |
| planner/unanswerable | n_steps | 1.3333 | 1.2472 |
| planner/unanswerable | reflections | 0.0000 | 0.0000 |
| planner/unanswerable | task_success | 0.3333 | 0.4714 |
| planner/unanswerable | tool_selection_ok | 1.0000 | 0.0000 |

## Multi-turn Analysis

- **Turn Success Rate**: 95.83%
- **Conversation Success Rate**: 92.31%
- **Context Retention**: 1.0000

## Confidence Intervals

Confidence Level: 95.0%

| Metric | Mean | Lower CI | Upper CI |
|--------|------|----------|----------|
| answer_fallback | 0.0000 | 0.0000 | 0.0000 |
| answer_grounded | 1.0000 | 1.0000 | 1.0000 |
| answer_status_ok | 0.6053 | 0.5327 | 0.6776 |
| asked_clarification | 0.2500 | 0.1776 | 0.3224 |
| constraint_satisfaction | 0.5700 | 0.3500 | 0.7601 |
| exclusion_compliance | 0.8182 | 0.6180 | 1.0000 |
| first_attempt_ok | 0.8553 | 0.8026 | 0.9145 |
| hit_rate@10 | 0.0000 | 0.0000 | 0.0000 |
| invented_ids | 0.0000 | 0.0000 | 0.0000 |
| map@10 | 0.0000 | 0.0000 | 0.0000 |
| mrr@10 | 0.0000 | 0.0000 | 0.0000 |
| n_steps | 2.2237 | 2.0000 | 2.4278 |
| ndcg@10 | 0.0000 | 0.0000 | 0.0000 |
| precision@10 | 0.0000 | 0.0000 | 0.0000 |
| recall@10 | 0.0000 | 0.0000 | 0.0000 |
| reflections | 0.0000 | 0.0000 | 0.0000 |
| task_success | 0.5714 | 0.4732 | 0.6607 |
| tool_selection_ok | 0.7321 | 0.6518 | 0.8038 |

## Failure Analysis

**Total Failures**: 48

- **planner:similar-sparse-14**: task_success=False
- **planner:similar-warm-8**: task_success=False
- **planner:cold_text-cold-0**: task_success=False
- **planner:cold_text-cold-1**: task_success=False
- **planner:cold_text-cold-2**: task_success=False
- **planner:cold_text-cold-4**: task_success=False
- **planner:cold_text-cold-7**: task_success=False
- **planner:cold_text-cold-9**: task_success=False
- **planner:cold_text-cold-11**: task_success=False
- **planner:cold_text-cold-12**: task_success=False
- ... and 38 more failures
