# Agent Evaluation Report

**Generated**: 2026-11-06T06:52:49.370113+00:00

## Executive Summary

- **total_requests**: 100
- **task_success_rate**: 0.8500
- **grounded_answer_rate**: 0.9000
- **constraint_satisfaction**: 0.8200
- **avg_latency**: 1.5000
- **p95_latency**: 2.8000

## Layer Analysis

| Layer | Metric | Mean | Std | Min | Max |
|-------|--------|------|-----|-----|-----|
| L1 | precision_at_10 | 0.7500 | 0.0500 | 0.6500 | 0.8500 |
| L1 | recall_at_10 | 0.8000 | 0.0600 | 0.7000 | 0.9000 |
| L2 | task_success | 0.8500 | 0.0400 | 0.7800 | 0.9200 |
| L2 | constraint_ok | 0.8200 | 0.0700 | 0.7000 | 0.9400 |

## Request Kind Analysis

| Request Kind | Metric | Mean | Std |
|--------------|--------|------|-----|
| similar | task_success | 0.9000 | 0.0300 |
| similar | grounded_answer | 0.9200 | 0.0400 |
| personalized | task_success | 0.8800 | 0.0500 |
| personalized | grounded_answer | 0.9100 | 0.0500 |

## Component Analysis

| Component | Success Rate | Mean Latency (s) |
|-----------|--------------|------------------|
| planner | 95.00% | 0.5000 |
| executor | 92.00% | 0.8000 |
| memory | 98.00% | 0.3000 |

## Multi-turn Analysis

- **Turn Success Rate**: 93.00%
- **Conversation Success Rate**: 88.00%
- **Context Retention**: 0.9500

## Confidence Intervals

Confidence Level: 95.0%

| Metric | Mean | Lower CI | Upper CI |
|--------|------|----------|----------|
| task_success | 0.8570 | 0.8430 | 0.8700 |
| grounded_answer | 0.9000 | 0.8890 | 0.9100 |

## Failure Analysis

**Total Failures**: 3

- **req_001**: Constraint violation
- **req_005**: Retrieval timeout
- **req_012**: Tool execution error
