# Failure Analysis Report

**Generated**: 2026-11-19T00:48:27.139407+00:00

**Total Failures**: 50

## Failures by Stage

### pool
**Count**: 7

**planner_memory:cold_text-cold-1**
- Error: task_success=False
- Trace: `campaign_005_metric_fixes_exp_11_agents_planner_memory_inference_mode_llm_reflect_rounds_0_multi_turn_True_run1_trajectories.jsonl`

**planner_memory:cold_text-cold-7**
- Error: task_success=False
- Trace: `campaign_005_metric_fixes_exp_11_agents_planner_memory_inference_mode_llm_reflect_rounds_0_multi_turn_True_run1_trajectories.jsonl`

**planner_memory:cold_text-cold-8**
- Error: task_success=False
- Trace: `campaign_005_metric_fixes_exp_11_agents_planner_memory_inference_mode_llm_reflect_rounds_0_multi_turn_True_run1_trajectories.jsonl`

**planner_memory:cold_text-cold-10**
- Error: task_success=False
- Trace: `campaign_005_metric_fixes_exp_11_agents_planner_memory_inference_mode_llm_reflect_rounds_0_multi_turn_True_run1_trajectories.jsonl`

**planner_memory:cold_text-cold-11**
- Error: task_success=False
- Trace: `campaign_005_metric_fixes_exp_11_agents_planner_memory_inference_mode_llm_reflect_rounds_0_multi_turn_True_run1_trajectories.jsonl`

... and 2 more failures in this stage

### retrieve
**Count**: 3

**planner_memory:similar-sparse-14**
- Error: task_success=False
- Trace: `campaign_005_metric_fixes_exp_11_agents_planner_memory_inference_mode_llm_reflect_rounds_0_multi_turn_True_run1_trajectories.jsonl`

**planner_memory:similar-warm-8**
- Error: task_success=False
- Trace: `campaign_005_metric_fixes_exp_11_agents_planner_memory_inference_mode_llm_reflect_rounds_0_multi_turn_True_run1_trajectories.jsonl`

**planner_memory:cold_text-cold-12**
- Error: task_success=False
- Trace: `campaign_005_metric_fixes_exp_11_agents_planner_memory_inference_mode_llm_reflect_rounds_0_multi_turn_True_run1_trajectories.jsonl`

### unknown
**Count**: 40

**planner_memory:personalized-warm-13**
- Error: task_success=False
- Trace: `campaign_005_metric_fixes_exp_11_agents_planner_memory_inference_mode_llm_reflect_rounds_0_multi_turn_True_run1_trajectories.jsonl`

**planner_memory:personalized-warm-18**
- Error: ValueError: LLM did not return valid JSON: {"steps":[{"tool":"MemoryTool","args":{"user_id":"AF4PCCO6H4GR7MQHGF76QJPE3FPQ"}},{"tool":"FilterTool","args":{"filters":{"categories_any":"$1.top_categories
- Trace: `campaign_005_metric_fixes_exp_11_agents_planner_memory_inference_mode_llm_reflect_rounds_0_multi_turn_True_run1_trajectories.jsonl`

**planner_memory:cold_text-cold-0**
- Error: task_success=False
- Trace: `campaign_005_metric_fixes_exp_11_agents_planner_memory_inference_mode_llm_reflect_rounds_0_multi_turn_True_run1_trajectories.jsonl`

**planner_memory:cold_text-cold-2**
- Error: task_success=False
- Trace: `campaign_005_metric_fixes_exp_11_agents_planner_memory_inference_mode_llm_reflect_rounds_0_multi_turn_True_run1_trajectories.jsonl`

**planner_memory:cold_text-cold-3**
- Error: task_success=False
- Trace: `campaign_005_metric_fixes_exp_11_agents_planner_memory_inference_mode_llm_reflect_rounds_0_multi_turn_True_run1_trajectories.jsonl`

... and 35 more failures in this stage
