# Agent Evaluation Report

**Generated**: 2026-11-16T19:17:07.791765+00:00

## Executive Summary

- **scored_rows**: 180
- **requests**: 140
- **agents**: baseline, type1
- **k**: 10

## Request Kind Analysis

| Request Kind | Metric | Mean | Std |
|--------------|--------|------|-----|
| baseline/cold_text | constraint_satisfaction | 0.0150 | 0.0357 |
| baseline/cold_text | hit_rate@10 | 0.0000 | 0.0000 |
| baseline/cold_text | map@10 | 0.0000 | 0.0000 |
| baseline/cold_text | mrr@10 | 0.0000 | 0.0000 |
| baseline/cold_text | ndcg@10 | 0.0000 | 0.0000 |
| baseline/cold_text | precision@10 | 0.0000 | 0.0000 |
| baseline/cold_text | recall@10 | 0.0000 | 0.0000 |
| baseline/cold_text | task_success | 0.0000 | 0.0000 |
| baseline/exclusion | exclusion_compliance | 0.9625 | 0.1278 |
| baseline/exclusion | hit_rate@10 | 0.0000 | 0.0000 |
| baseline/exclusion | map@10 | 0.0000 | 0.0000 |
| baseline/exclusion | mrr@10 | 0.0000 | 0.0000 |
| baseline/exclusion | ndcg@10 | 0.0000 | 0.0000 |
| baseline/exclusion | precision@10 | 0.0000 | 0.0000 |
| baseline/exclusion | recall@10 | 0.0000 | 0.0000 |
| baseline/exclusion | task_success | 0.8750 | 0.3307 |
| baseline/personalized | hit_rate@10 | 0.0000 | 0.0000 |
| baseline/personalized | map@10 | 0.0000 | 0.0000 |
| baseline/personalized | mrr@10 | 0.0000 | 0.0000 |
| baseline/personalized | ndcg@10 | 0.0000 | 0.0000 |
| baseline/personalized | precision@10 | 0.0000 | 0.0000 |
| baseline/personalized | recall@10 | 0.0000 | 0.0000 |
| baseline/personalized | task_success | 1.0000 | 0.0000 |
| baseline/similar | hit_rate@10 | 0.0250 | 0.1561 |
| baseline/similar | map@10 | 0.0031 | 0.0195 |
| baseline/similar | mrr@10 | 0.0125 | 0.0781 |
| baseline/similar | ndcg@10 | 0.0062 | 0.0385 |
| baseline/similar | precision@10 | 0.0025 | 0.0156 |
| baseline/similar | recall@10 | 0.0063 | 0.0390 |
| baseline/similar | task_success | 1.0000 | 0.0000 |
| type1/similar | answer_fallback | 0.0000 | 0.0000 |
| type1/similar | answer_grounded | 1.0000 | 0.0000 |
| type1/similar | answer_status_ok | 1.0000 | 0.0000 |
| type1/similar | hit_rate@10 | 0.0250 | 0.1561 |
| type1/similar | map@10 | 0.0031 | 0.0195 |
| type1/similar | mrr@10 | 0.0125 | 0.0781 |
| type1/similar | n_steps | 3.0000 | 0.0000 |
| type1/similar | ndcg@10 | 0.0062 | 0.0385 |
| type1/similar | precision@10 | 0.0025 | 0.0156 |
| type1/similar | recall@10 | 0.0063 | 0.0390 |
| type1/similar | task_success | 1.0000 | 0.0000 |

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
| answer_status_ok | 1.0000 | 1.0000 | 1.0000 |
| constraint_satisfaction | 0.0150 | 0.0000 | 0.0300 |
| exclusion_compliance | 0.9625 | 0.9150 | 0.9950 |
| hit_rate@10 | 0.0124 | 0.0000 | 0.0311 |
| map@10 | 0.0016 | 0.0000 | 0.0039 |
| mrr@10 | 0.0062 | 0.0000 | 0.0155 |
| n_steps | 3.0000 | 3.0000 | 3.0000 |
| ndcg@10 | 0.0031 | 0.0000 | 0.0076 |
| precision@10 | 0.0012 | 0.0000 | 0.0031 |
| recall@10 | 0.0031 | 0.0000 | 0.0078 |
| task_success | 0.8611 | 0.8056 | 0.9111 |

## Failure Analysis

**Total Failures**: 25

- **baseline:cold_text-cold-0**: task_success=False
- **baseline:cold_text-cold-1**: task_success=False
- **baseline:cold_text-cold-2**: task_success=False
- **baseline:cold_text-cold-3**: task_success=False
- **baseline:cold_text-cold-4**: task_success=False
- **baseline:cold_text-cold-5**: task_success=False
- **baseline:cold_text-cold-6**: task_success=False
- **baseline:cold_text-cold-7**: task_success=False
- **baseline:cold_text-cold-8**: task_success=False
- **baseline:cold_text-cold-9**: task_success=False
- ... and 15 more failures
