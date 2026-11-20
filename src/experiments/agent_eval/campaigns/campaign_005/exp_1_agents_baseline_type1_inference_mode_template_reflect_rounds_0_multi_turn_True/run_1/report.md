# Agent Evaluation Report

**Generated**: 2026-11-18T17:51:49.528243+00:00

## Executive Summary

- **scored_rows**: 180
- **requests**: 140
- **agents**: baseline, type1
- **k**: 10

## Request Kind Analysis

| Request Kind | Metric | Mean | Std |
|--------------|--------|------|-----|
| baseline/cold_text | constraint_satisfaction | 0.0050 | 0.0218 |
| baseline/cold_text | hit_rate@10 | 0.0000 | 0.0000 |
| baseline/cold_text | map@10 | 0.0000 | 0.0000 |
| baseline/cold_text | mrr@10 | 0.0000 | 0.0000 |
| baseline/cold_text | ndcg@10 | 0.0000 | 0.0000 |
| baseline/cold_text | precision@10 | 0.0000 | 0.0000 |
| baseline/cold_text | recall@10 | 0.0000 | 0.0000 |
| baseline/cold_text | task_success | 0.0000 | 0.0000 |
| baseline/exclusion | exclusion_compliance | 0.9775 | 0.0758 |
| baseline/exclusion | hit_rate@10 | 0.0000 | 0.0000 |
| baseline/exclusion | map@10 | 0.0000 | 0.0000 |
| baseline/exclusion | mrr@10 | 0.0000 | 0.0000 |
| baseline/exclusion | ndcg@10 | 0.0000 | 0.0000 |
| baseline/exclusion | precision@10 | 0.0000 | 0.0000 |
| baseline/exclusion | recall@10 | 0.0000 | 0.0000 |
| baseline/exclusion | task_success | 0.9000 | 0.3000 |
| baseline/personalized | hit_rate@10 | 0.0000 | 0.0000 |
| baseline/personalized | map@10 | 0.0000 | 0.0000 |
| baseline/personalized | mrr@10 | 0.0000 | 0.0000 |
| baseline/personalized | ndcg@10 | 0.0000 | 0.0000 |
| baseline/personalized | precision@10 | 0.0000 | 0.0000 |
| baseline/personalized | recall@10 | 0.0000 | 0.0000 |
| baseline/personalized | task_success | 1.0000 | 0.0000 |
| baseline/similar | hit_rate@10 | 0.0000 | 0.0000 |
| baseline/similar | map@10 | 0.0000 | 0.0000 |
| baseline/similar | mrr@10 | 0.0000 | 0.0000 |
| baseline/similar | ndcg@10 | 0.0000 | 0.0000 |
| baseline/similar | precision@10 | 0.0000 | 0.0000 |
| baseline/similar | recall@10 | 0.0000 | 0.0000 |
| baseline/similar | task_success | 1.0000 | 0.0000 |
| type1/similar | answer_fallback | 0.0000 | 0.0000 |
| type1/similar | answer_grounded | 1.0000 | 0.0000 |
| type1/similar | answer_status_ok | 0.9500 | 0.2179 |
| type1/similar | hit_rate@10 | 0.0000 | 0.0000 |
| type1/similar | map@10 | 0.0000 | 0.0000 |
| type1/similar | mrr@10 | 0.0000 | 0.0000 |
| type1/similar | n_steps | 2.9000 | 0.4359 |
| type1/similar | ndcg@10 | 0.0000 | 0.0000 |
| type1/similar | precision@10 | 0.0000 | 0.0000 |
| type1/similar | recall@10 | 0.0000 | 0.0000 |
| type1/similar | task_success | 0.9500 | 0.2179 |

## Multi-turn Analysis

- **Turn Success Rate**: 100.00%
- **Conversation Success Rate**: 100.00%
- **Context Retention**: 1.0000

## Confidence Intervals

Confidence Level: 95.0%

| Metric | Mean | Lower CI | Upper CI |
|--------|------|----------|----------|
| answer_fallback | 0.0000 | 0.0000 | 0.0000 |
| answer_grounded | 1.0000 | 1.0000 | 1.0000 |
| answer_status_ok | 0.9500 | 0.8750 | 1.0000 |
| constraint_satisfaction | 0.0050 | 0.0000 | 0.0150 |
| exclusion_compliance | 0.9775 | 0.9524 | 0.9975 |
| hit_rate@10 | 0.0000 | 0.0000 | 0.0000 |
| map@10 | 0.0000 | 0.0000 | 0.0000 |
| mrr@10 | 0.0000 | 0.0000 | 0.0000 |
| n_steps | 2.9000 | 2.7500 | 3.0000 |
| ndcg@10 | 0.0000 | 0.0000 | 0.0000 |
| precision@10 | 0.0000 | 0.0000 | 0.0000 |
| recall@10 | 0.0000 | 0.0000 | 0.0000 |
| task_success | 0.8556 | 0.8000 | 0.9056 |

## Failure Analysis

**Total Failures**: 26

- **type1:similar-sparse-14**: retrieve: no candidates returned
- **type1:similar-warm-8**: retrieve: no candidates returned
- **baseline:cold_text-cold-0**: task_success=False
- **baseline:cold_text-cold-1**: task_success=False
- **baseline:cold_text-cold-2**: task_success=False
- **baseline:cold_text-cold-3**: task_success=False
- **baseline:cold_text-cold-4**: task_success=False
- **baseline:cold_text-cold-5**: task_success=False
- **baseline:cold_text-cold-6**: task_success=False
- **baseline:cold_text-cold-7**: task_success=False
- ... and 16 more failures
