# Agent Evaluation Report

**Generated**: 2026-11-24T05:40:15.881269+00:00

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
| planner/cold_text | answer_status_ok | 0.8000 | 0.4000 |
| planner/cold_text | asked_clarification | 0.0500 | 0.2179 |
| planner/cold_text | constraint_satisfaction | 0.6950 | 0.3930 |
| planner/cold_text | first_attempt_ok | 0.8500 | 0.3571 |
| planner/cold_text | hit_rate@10 | 0.0500 | 0.2179 |
| planner/cold_text | invented_ids | 0.0000 | 0.0000 |
| planner/cold_text | map@10 | 0.0125 | 0.0545 |
| planner/cold_text | mrr@10 | 0.0125 | 0.0545 |
| planner/cold_text | n_steps | 2.8500 | 0.6538 |
| planner/cold_text | ndcg@10 | 0.0215 | 0.0939 |
| planner/cold_text | precision@10 | 0.0050 | 0.0218 |
| planner/cold_text | recall@10 | 0.0500 | 0.2179 |
| planner/cold_text | reflections | 0.0000 | 0.0000 |
| planner/cold_text | task_success | 0.5000 | 0.5000 |
| planner/cold_text | tool_selection_ok | 0.9500 | 0.2179 |
| planner/exclusion | answer_fallback | 0.0000 | 0.0000 |
| planner/exclusion | answer_grounded | 1.0000 | 0.0000 |
| planner/exclusion | answer_status_ok | 0.4500 | 0.4975 |
| planner/exclusion | asked_clarification | 0.3000 | 0.4583 |
| planner/exclusion | exclusion_compliance | 0.6889 | 0.4095 |
| planner/exclusion | first_attempt_ok | 0.5750 | 0.4943 |
| planner/exclusion | hit_rate@10 | 0.0000 | 0.0000 |
| planner/exclusion | invented_ids | 0.0000 | 0.0000 |
| planner/exclusion | map@10 | 0.0000 | 0.0000 |
| planner/exclusion | mrr@10 | 0.0000 | 0.0000 |
| planner/exclusion | n_steps | 2.1750 | 1.5634 |
| planner/exclusion | ndcg@10 | 0.0000 | 0.0000 |
| planner/exclusion | precision@10 | 0.0000 | 0.0000 |
| planner/exclusion | recall@10 | 0.0000 | 0.0000 |
| planner/exclusion | reflections | 0.0000 | 0.0000 |
| planner/exclusion | task_success | 0.1500 | 0.3571 |
| planner/exclusion | tool_selection_ok | 0.5000 | 0.5000 |
| planner/personalized | answer_fallback | 0.0000 | 0.0000 |
| planner/personalized | answer_grounded | 1.0000 | 0.0000 |
| planner/personalized | answer_status_ok | 0.5500 | 0.4975 |
| planner/personalized | asked_clarification | 0.4250 | 0.4943 |
| planner/personalized | first_attempt_ok | 0.9750 | 0.1561 |
| planner/personalized | hit_rate@10 | 0.0250 | 0.1561 |
| planner/personalized | invented_ids | 0.0000 | 0.0000 |
| planner/personalized | map@10 | 0.0063 | 0.0390 |
| planner/personalized | mrr@10 | 0.0063 | 0.0390 |
| planner/personalized | n_steps | 1.7500 | 1.5124 |
| planner/personalized | ndcg@10 | 0.0108 | 0.0672 |
| planner/personalized | precision@10 | 0.0025 | 0.0156 |
| planner/personalized | recall@10 | 0.0250 | 0.1561 |
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
| planner/unanswerable | asked_clarification | 0.1667 | 0.3727 |
| planner/unanswerable | first_attempt_ok | 0.1667 | 0.3727 |
| planner/unanswerable | invented_ids | 0.0000 | 0.0000 |
| planner/unanswerable | n_steps | 2.5000 | 1.1180 |
| planner/unanswerable | reflections | 0.0000 | 0.0000 |
| planner/unanswerable | task_success | 0.1667 | 0.3727 |
| planner/unanswerable | tool_selection_ok | 1.0000 | 0.0000 |

## Confidence Intervals

Confidence Level: 95.0%

| Metric | Mean | Lower CI | Upper CI |
|--------|------|----------|----------|
| answer_fallback | 0.0000 | 0.0000 | 0.0000 |
| answer_grounded | 1.0000 | 1.0000 | 1.0000 |
| answer_status_ok | 0.6184 | 0.5395 | 0.6974 |
| asked_clarification | 0.2434 | 0.1776 | 0.3158 |
| constraint_satisfaction | 0.6950 | 0.5149 | 0.8550 |
| exclusion_compliance | 0.6889 | 0.4944 | 0.8722 |
| first_attempt_ok | 0.8158 | 0.7500 | 0.8750 |
| hit_rate@10 | 0.0172 | 0.0000 | 0.0431 |
| invented_ids | 0.0000 | 0.0000 | 0.0000 |
| map@10 | 0.0043 | 0.0000 | 0.0108 |
| mrr@10 | 0.0043 | 0.0000 | 0.0108 |
| n_steps | 2.2961 | 2.0788 | 2.5002 |
| ndcg@10 | 0.0074 | 0.0000 | 0.0186 |
| precision@10 | 0.0017 | 0.0000 | 0.0043 |
| recall@10 | 0.0172 | 0.0000 | 0.0431 |
| reflections | 0.0000 | 0.0000 | 0.0000 |
| task_success | 0.5446 | 0.4464 | 0.6342 |
| tool_selection_ok | 0.8125 | 0.7411 | 0.8842 |

## Failure Analysis

**Total Failures**: 51

- **planner:similar-sparse-14**: task_success=False
- **planner:similar-warm-8**: task_success=False
- **planner:cold_text-cold-0**: task_success=False
- **planner:cold_text-cold-2**: task_success=False
- **planner:cold_text-cold-6**: task_success=False
- **planner:cold_text-cold-7**: task_success=False
- **planner:cold_text-cold-10**: task_success=False
- **planner:cold_text-cold-11**: task_success=False
- **planner:cold_text-cold-16**: task_success=False
- **planner:cold_text-cold-17**: task_success=False
- ... and 41 more failures
