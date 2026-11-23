# Agent Evaluation Report

**Generated**: 2026-11-16T18:59:25.265852+00:00

## Executive Summary

- **scored_rows**: 9
- **requests**: 9
- **agents**: baseline
- **k**: 10

## Request Kind Analysis

| Request Kind | Metric | Mean | Std |
|--------------|--------|------|-----|
| baseline/cold_text | constraint_satisfaction | 0.0333 | 0.0471 |
| baseline/cold_text | hit_rate@10 | 0.0000 | 0.0000 |
| baseline/cold_text | map@10 | 0.0000 | 0.0000 |
| baseline/cold_text | mrr@10 | 0.0000 | 0.0000 |
| baseline/cold_text | ndcg@10 | 0.0000 | 0.0000 |
| baseline/cold_text | precision@10 | 0.0000 | 0.0000 |
| baseline/cold_text | recall@10 | 0.0000 | 0.0000 |
| baseline/cold_text | task_success | 0.0000 | 0.0000 |
| baseline/exclusion | exclusion_compliance | 0.9333 | 0.1491 |
| baseline/exclusion | hit_rate@10 | 0.0000 | 0.0000 |
| baseline/exclusion | map@10 | 0.0000 | 0.0000 |
| baseline/exclusion | mrr@10 | 0.0000 | 0.0000 |
| baseline/exclusion | ndcg@10 | 0.0000 | 0.0000 |
| baseline/exclusion | precision@10 | 0.0000 | 0.0000 |
| baseline/exclusion | recall@10 | 0.0000 | 0.0000 |
| baseline/exclusion | task_success | 0.8333 | 0.3727 |

## Confidence Intervals

Confidence Level: 95.0%

| Metric | Mean | Lower CI | Upper CI |
|--------|------|----------|----------|
| constraint_satisfaction | 0.0333 | 0.0000 | 0.1000 |
| exclusion_compliance | 0.9333 | 0.8000 | 1.0000 |
| hit_rate@10 | 0.0000 | 0.0000 | 0.0000 |
| map@10 | 0.0000 | 0.0000 | 0.0000 |
| mrr@10 | 0.0000 | 0.0000 | 0.0000 |
| ndcg@10 | 0.0000 | 0.0000 | 0.0000 |
| precision@10 | 0.0000 | 0.0000 | 0.0000 |
| recall@10 | 0.0000 | 0.0000 | 0.0000 |
| task_success | 0.5556 | 0.2222 | 0.8889 |

## Failure Analysis

**Total Failures**: 4

- **baseline:cold_text-cold-0**: task_success=False
- **baseline:cold_text-cold-1**: task_success=False
- **baseline:cold_text-cold-2**: task_success=False
- **baseline:exclusion-sparse-2**: task_success=False
