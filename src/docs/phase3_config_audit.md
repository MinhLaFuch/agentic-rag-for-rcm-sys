# Phase 3.7 — Config key traceability audit (report only)

Total leaf keys: 221. Status: used = read by schema/code/.sh; test-only/doc-only/dead? = no runtime reader found (verify manually before acting).

| config file | key | reader (file:line) | status |
|---|---|---|---|
| configs/agent/ablation.yaml | ablation.bootstrap_resamples | schema:package\config\_schemas.py:207; code:package\evaluation\ablation\_limits.py:28; md:experiments\test_logs\test_results_20261108_235155.md:28855 | used |
| configs/agent/ablation.yaml | ablation.confidence | schema:package\config\_schemas.py:208; code:package\evaluation\ablation\_limits.py:32; test:tests\evaluation\test_jev_reliability.py:30 | used |
| configs/agent/ablation.yaml | ablation.min_n_warn | schema:package\config\_schemas.py:209; code:package\evaluation\ablation\_limits.py:36; md:experiments\test_logs\test_results_20261108_235155.md:28857 | used |
| configs/agent/ablation.yaml | ablation.seed | schema:package\config\_schemas.py:210; code:package\evaluation\ablation\_limits.py:40; test:tests\data\test_diagnose_splits.py:259 | used |
| configs/agent/ablation.yaml | ablation.metrics | schema:package\config\_schemas.py:211; code:package\evaluation\ablation\_limits.py:42; test:tests\evaluation\component\test_run_all.py:21 | used |
| configs/agent/ablation.yaml | ablation.groups.reflect_0 | md:repo reading.md:705 | doc-only |
| configs/agent/ablation.yaml | ablation.groups.reflect_1 | md:repo reading.md:705 | doc-only |
| configs/agent/ablation.yaml | ablation.groups.infer_template | — | dead? |
| configs/agent/ablation.yaml | ablation.contrasts | schema:package\config\_schemas.py:213; code:package\evaluation\ablation\_limits.py:50; md:experiments\test_logs\test_results_20261108_235155.md:28861 | used |
| configs/agent/agent.yaml | agent.max_steps | schema:package\config\_schemas.py:30; code:package\agents\_limits.py:32; test:tests\config\test_config_loader.py:118 | used |
| configs/agent/agent.yaml | agent.plan_retries | schema:package\config\_schemas.py:31; code:package\agents\_limits.py:33; md:experiments\test_logs\test_results_20261108_235155.md:1910 | used |
| configs/agent/agent.yaml | agent.reflect_rounds | schema:package\config\_schemas.py:32; code:package\agents\_limits.py:34; test:tests\agents\test_plan_reflect.py:32 | used |
| configs/agent/agent.yaml | agent.reflect_error_chars | schema:package\config\_schemas.py:33; code:package\agents\_limits.py:39; test:tests\agents\test_plan_reflect.py:178 | used |
| configs/agent/agent.yaml | agent.max_tokens | schema:package\config\_schemas.py:34; code:package\agents\_limits.py:35; test:tests\agents\fakes\scripted_llm.py:59 | used |
| configs/agent/agent.yaml | agent.temperature | schema:package\config\_schemas.py:35; code:package\agents\_limits.py:36; test:tests\agents\fakes\scripted_llm.py:58 | used |
| configs/agent/agent.yaml | agent.type1.candidate_multiplier | schema:package\config\_schemas.py:51; code:package\agents\_limits.py:37; test:tests\evaluation\agent\test_config_resume_integration.py:40 | used |
| configs/agent/agent.yaml | agent.type1.min_candidates | schema:package\config\_schemas.py:52; code:package\agents\_limits.py:38; md:repo reading.md:309 | used |
| configs/agent/agent_eval.yaml | agent_eval.agents | schema:package\config\_schemas.py:60; code:package\config\_schemas.py:78; test:tests\evaluation\campaign\test_campaign.py:366 | used |
| configs/agent/agent_eval.yaml | agent_eval.k | schema:package\config\_schemas.py:61; code:package\data\pipeline\build_artifacts.py:48; test:tests\config\test_config_overlay.py:30 | used |
| configs/agent/agent_eval.yaml | agent_eval.per_segment | schema:package\config\_schemas.py:62; code:package\evaluation\ablation\_loader.py:116; test:tests\config\test_config_overlay.py:25 | used |
| configs/agent/agent_eval.yaml | agent_eval.n_ambiguous | schema:package\config\_schemas.py:63; code:scripts\evaluation\run_agent_eval.py:333; md:experiments\test_logs\test_results_20261108_235155.md:14763 | used |
| configs/agent/agent_eval.yaml | agent_eval.language | schema:package\config\_schemas.py:64; code:package\config\_schemas.py:86; test:tests\evaluation\ablation\test_integration.py:33 | used |
| configs/agent/agent_eval.yaml | agent_eval.price_slack | schema:package\config\_schemas.py:65; code:scripts\evaluation\run_agent_eval.py:334; md:experiments\test_logs\test_results_20261108_235155.md:14764 | used |
| configs/agent/agent_eval.yaml | agent_eval.price_round_to | schema:package\config\_schemas.py:66; code:scripts\evaluation\run_agent_eval.py:334; md:experiments\test_logs\test_results_20261108_235155.md:14764 | used |
| configs/agent/agent_eval.yaml | agent_eval.min_metadata_coverage | schema:package\config\_schemas.py:67; code:package\data\pipeline\build_artifacts.py:47; md:experiments\test_logs\test_results_20261108_235155.md:14764 | used |
| configs/agent/agent_eval.yaml | agent_eval.trajectory_error_chars | schema:package\config\_schemas.py:68; code:scripts\evaluation\run_agent_eval.py:135; test:tests\evaluation\agent\test_agent_eval.py:367 | used |
| configs/agent/agent_eval.yaml | agent_eval.max_consecutive_llm_errors | schema:package\config\_schemas.py:69; code:scripts\evaluation\run_agent_eval.py:413; md:experiments\test_logs\test_results_20261108_235155.md:14765 | used |
| configs/agent/agent_eval.yaml | agent_eval.trajectory_file | schema:package\config\_schemas.py:70; code:package\evaluation\campaign\campaign_runner.py:141; test:tests\evaluation\campaign\test_campaign.py:375 | used |
| configs/agent/agent_eval.yaml | agent_eval.request_scope | schema:package\config\_schemas.py:71; code:package\config\_schemas.py:93; md:repo reading.md:518 | used |
| configs/agent/agent_eval.yaml | agent_eval.enable_session | schema:package\config\_schemas.py:72; code:scripts\evaluation\run_agent_eval.py:227 | used |
| configs/agent/agent_eval.yaml | agent_eval.metadata_policy | schema:package\config\_schemas.py:73; code:package\config\_schemas.py:100; test:tests\evaluation\ablation\test_loader.py:208 | used |
| configs/agent/agent_eval.yaml | agent_eval.use_prebuilt_corpus | schema:package\config\_schemas.py:74; code:scripts\demo\run_demo.py:47; test:tests\tools\evaluation\test_ranking_streaming.py:52 | used |
| configs/agent/agent_eval.yaml | agent_eval.allow_missing_corpus_sources | schema:package\config\_schemas.py:75; code:package\evaluation\campaign\campaign_runner.py:217; test:tests\evaluation\campaign\test_campaign.py:391 | used |
| configs/agent/demo.yaml | demo.max_error_length | schema:package\config\_schemas.py:474; code:package\demo\_limits.py:25; md:experiments\test_logs\test_results_20261108_235155.md:26694 | used |
| configs/agent/demo.yaml | demo.max_items_display | schema:package\config\_schemas.py:475; code:package\demo\_limits.py:26; md:experiments\test_logs\test_results_20261108_235155.md:26695 | used |
| configs/agent/demo.yaml | demo.sample_users_per_segment | schema:package\config\_schemas.py:476; code:package\demo\_limits.py:27; md:experiments\test_logs\test_results_20261108_235155.md:26696 | used |
| configs/agent/demo.yaml | demo.default_language | schema:package\config\_schemas.py:477; code:package\config\_schemas.py:484; md:experiments\test_logs\test_results_20261108_235155.md:26697 | used |
| configs/agent/demo.yaml | demo.max_recent_items_display | schema:package\config\_schemas.py:478; code:package\demo\_limits.py:29; md:experiments\test_logs\test_results_20261108_235155.md:26703 | used |
| configs/agent/demo.yaml | demo.max_turn_history_rows | schema:package\config\_schemas.py:479; code:package\demo\_limits.py:30; md:experiments\test_logs\test_results_20261108_235155.md:26703 | used |
| configs/agent/demo.yaml | demo.eval_on | schema:package\config\_schemas.py:480; code:package\config\_schemas.py:491; test:tests\evaluation\ablation\test_integration.py:37 | used |
| configs/agent/demo.yaml | demo.use_prebuilt_corpus | schema:package\config\_schemas.py:74; code:scripts\demo\run_demo.py:47; test:tests\tools\evaluation\test_ranking_streaming.py:52 | used |
| configs/agent/demo.yaml | demo.allow_missing_corpus_sources | schema:package\config\_schemas.py:75; code:package\evaluation\campaign\campaign_runner.py:217; test:tests\evaluation\campaign\test_campaign.py:391 | used |
| configs/agent/demo_profiles.yaml | demo_profiles.pinned | code:package\demo\_profile_builder.py:38; md:experiments\test_logs\test_results_20261108_235155.md:26534 | used |
| configs/agent/inference.yaml | inference.mode | schema:package\config\_schemas.py:184; code:package\config\_schemas.py:194; test:tests\config\test_config_overlay.py:64 | used |
| configs/agent/inference.yaml | inference.max_items | schema:package\config\_schemas.py:185; code:package\inference\_limits.py:33; test:tests\agents\inference\test_limits.py:19 | used |
| configs/agent/inference.yaml | inference.max_tokens | schema:package\config\_schemas.py:34; code:package\agents\_limits.py:35; test:tests\agents\fakes\scripted_llm.py:59 | used |
| configs/agent/inference.yaml | inference.temperature | schema:package\config\_schemas.py:35; code:package\agents\_limits.py:36; test:tests\agents\fakes\scripted_llm.py:58 | used |
| configs/agent/inference.yaml | inference.llm_retries | schema:package\config\_schemas.py:188; code:package\inference\_limits.py:36; test:tests\agents\inference\test_compose.py:93 | used |
| configs/agent/inference.yaml | inference.check_numbers | schema:package\config\_schemas.py:189; code:package\inference\_limits.py:37; test:tests\agents\inference\test_compose.py:206 | used |
| configs/agent/inference.yaml | inference.title_chars | schema:package\config\_schemas.py:190; code:package\inference\_limits.py:39; test:tests\agents\inference\test_limits.py:23 | used |
| configs/agent/inference.yaml | inference.reason_chars | schema:package\config\_schemas.py:191; code:package\inference\_limits.py:40; test:tests\agents\inference\test_limits.py:23 | used |
| configs/agent/inference.yaml | inference.price_tolerance | schema:package\config\_schemas.py:192; code:package\inference\_limits.py:38; test:tests\agents\inference\test_compose.py:204 | used |
| configs/agent/llm.yaml | provider | schema:package\config\_schemas.py:113; code:package\api\build_judgment_provider.py:27; test:tests\agents\test_llm_provider.py:18 | used |
| configs/agent/llm.yaml | model | schema:package\config\_schemas.py:114; code:package\api\build_judgment_provider.py:31; test:tests\agents\test_end_to_end.py:38 | used |
| configs/agent/llm.yaml | base_url | schema:package\config\_schemas.py:115; code:package\api\build_judgment_provider.py:32; test:tests\agents\test_llm_provider.py:30 | used |
| configs/agent/llm.yaml | api_key | schema:package\config\_schemas.py:116; code:package\api\build_judgment_provider.py:30; test:tests\config\test_config_loader.py:57 | used |
| configs/agent/llm.yaml | timeout_seconds | schema:package\config\_schemas.py:117; code:package\api\build_judgment_provider.py:33; test:tests\agents\test_llm_provider.py:32 | used |
| configs/agent/memory.yaml | memory.love_min_rating | schema:package\config\_schemas.py:125; code:package\memory\get_memory_limits.py:17; md:experiments\test_logs\test_results_20261108_235155.md:7766 | used |
| configs/agent/memory.yaml | memory.hate_max_rating | schema:package\config\_schemas.py:126; code:package\memory\get_memory_limits.py:18; md:experiments\test_logs\test_results_20261108_235155.md:7766 | used |
| configs/agent/memory.yaml | memory.top_n_loved_items | schema:package\config\_schemas.py:127; code:package\memory\get_memory_limits.py:19; md:experiments\test_logs\test_results_20261108_235155.md:7766 | used |
| configs/agent/memory.yaml | memory.top_n_hated_items | schema:package\config\_schemas.py:128; code:package\memory\get_memory_limits.py:20; md:experiments\test_logs\test_results_20261108_235155.md:7766 | used |
| configs/agent/memory.yaml | memory.top_n_categories | schema:package\config\_schemas.py:129; code:package\memory\get_memory_limits.py:21; md:repo reading.md:324 | used |
| configs/agent/memory.yaml | memory.recent_items | schema:package\config\_schemas.py:130; code:package\memory\get_memory_limits.py:22; test:tests\agents\test_end_to_end.py:97 | used |
| configs/agent/memory.yaml | memory.session.max_turns | schema:package\config\_schemas.py:139; md:experiments\test_logs\test_results_20261108_235155.md:8752 | used |
| configs/agent/memory.yaml | memory.session.max_shown_items | schema:package\config\_schemas.py:140; md:experiments\test_logs\test_results_20261108_235155.md:8752 | used |
| configs/agent/memory.yaml | memory.session.max_candidates | schema:package\config\_schemas.py:141; code:package\tools\_limits.py:36; test:tests\config\test_tool_limits.py:20 | used |
| configs/agent/memory.yaml | memory.session.max_turn_chars | schema:package\config\_schemas.py:142; md:experiments\test_logs\test_results_20261108_235155.md:8752 | used |
| configs/agent/reference_plans.yaml | reference_plans.similar | code:package\agents\_schema.py:6; test:tests\demo\test_demo_backend.py:132; md:repo reading.md:225 | used |
| configs/agent/reference_plans.yaml | reference_plans.personalized | code:package\agents\_schema.py:7; test:tests\demo\test_demo_backend.py:132; md:repo reading.md:313 | used |
| configs/agent/reference_plans.yaml | reference_plans.constrained | code:package\agents\_schema.py:8; test:tests\demo\test_demo_backend.py:132; md:repo reading.md:929 | used |
| configs/agent/reference_plans.yaml | reference_plans.cold_text | code:package\agents\_schema.py:9; test:tests\demo\test_demo_backend.py:132; md:repo reading.md:929 | used |
| configs/agent/reference_plans.yaml | reference_plans.ambiguous | code:package\agents\_schema.py:10; test:tests\demo\test_demo_backend.py:132; md:repo reading.md:1005 | used |
| configs/agent/reference_plans.yaml | reference_plans.exclusion | code:package\agents\_schema.py:15; md:repo reading.md:413 | used |
| configs/agent/reference_plans.yaml | reference_plans.unanswerable | code:package\agents\_schema.py:16; md:repo reading.md:1005 | used |
| configs/agent/tools.yaml | tools.max_candidates | schema:package\config\_schemas.py:141; code:package\tools\_limits.py:36; test:tests\config\test_tool_limits.py:20 | used |
| configs/agent/tools.yaml | tools.max_query_rows | schema:package\config\_schemas.py:151; code:package\corpus\item_corpus.py:49; test:tests\config\test_tool_limits.py:21 | used |
| configs/agent/tools.yaml | tools.sql_time_budget_seconds | schema:package\config\_schemas.py:152; code:package\corpus\item_corpus.py:49; test:tests\config\test_tool_limits.py:22 | used |
| configs/agent/tools.yaml | tools.max_output_summary_chars | schema:package\config\_schemas.py:153; code:package\tools\_limits.py:39; md:experiments\test_logs\test_results_20261108_235155.md:11228 | used |
| configs/agent/tools.yaml | tools.defaults.sql_limit | schema:package\config\_schemas.py:163; code:package\tools\_limits.py:40; md:experiments\test_logs\test_results_20261108_235155.md:16157 | used |
| configs/agent/tools.yaml | tools.defaults.item_cf_top_k | schema:package\config\_schemas.py:164; code:package\tools\_limits.py:41; md:experiments\test_logs\test_results_20261108_235155.md:1197 | used |
| configs/agent/tools.yaml | tools.defaults.query_max_rows | schema:package\config\_schemas.py:165; code:package\tools\_limits.py:42; md:experiments\test_logs\test_results_20261108_235155.md:877 | used |
| configs/agent/tools.yaml | tools.defaults.memory_top_n_categories | schema:package\config\_schemas.py:166; code:package\tools\_limits.py:43; md:experiments\test_logs\test_results_20261108_235155.md:16157 | used |
| configs/agent/tools.yaml | tools.defaults.memory_recent_items | schema:package\config\_schemas.py:167; code:package\tools\_limits.py:44; md:experiments\test_logs\test_results_20261108_235155.md:16157 | used |
| configs/agent/tools.yaml | tools.semantic_search.default_limit | schema:package\config\_schemas.py:175; code:package\tools\_limits.py:45; test:tests\config\test_tool_limits.py:23 | used |
| configs/agent/tools.yaml | tools.semantic_search.max_query_tokens | schema:package\config\_schemas.py:176; code:package\tools\_limits.py:46; test:tests\config\test_tool_limits.py:24 | used |
| configs/data/cleaning.yaml | cleaning.chunk_size | code:package\data\pipeline\clean_domain.py:44; test:tests\config\test_config_loader.py:21; md:experiments\test_logs\test_results_20261108_235155.md:14381 | used |
| configs/data/filtering.yaml | filtering.min_user_interactions | code:package\data\pipeline\merge_filter_domains.py:38; md:experiments\test_logs\test_results_20261108_235155.md:23282 | used |
| configs/data/filtering.yaml | filtering.min_item_interactions | code:package\data\pipeline\merge_filter_domains.py:39; md:experiments\test_logs\test_results_20261108_235155.md:23282 | used |
| configs/data/split.yaml | split.train_ratio | schema:package\config\_schemas.py:448; code:package\data\pipeline\map_split.py:28; md:experiments\test_logs\test_results_20261108_235155.md:25868 | used |
| configs/data/split.yaml | split.validation_ratio | schema:package\config\_schemas.py:449; code:package\data\pipeline\map_split.py:29; md:experiments\test_logs\test_results_20261108_235155.md:25868 | used |
| configs/data/split.yaml | split.test_ratio | schema:package\config\_schemas.py:450; code:package\data\pipeline\map_split.py:30; md:experiments\test_logs\test_results_20261108_235155.md:25868 | used |
| configs/data/split.yaml | split.item_knn_splits | schema:package\config\_schemas.py:451; code:package\config\_schemas.py:453 | used |
| configs/eval/baselines.yaml | baselines.seed | schema:package\config\_schemas.py:210; code:package\evaluation\ablation\_limits.py:40; test:tests\data\test_diagnose_splits.py:259 | used |
| configs/eval/baselines.yaml | baselines.models | schema:package\config\_schemas.py:232; code:benchmarks\run_baselines.py:37; md:experiments\test_logs\test_results_20261108_235155.md:1141 | used |
| configs/eval/baselines.yaml | baselines.popularity_fallback | schema:package\config\_schemas.py:233; code:package\recommenders\shared\build_model.py:31; test:tests\recommenders\test_contract_recommenders.py:233 | used |
| configs/eval/baselines.yaml | baselines.item_knn.k | schema:package\config\_schemas.py:61; code:package\data\pipeline\build_artifacts.py:48; test:tests\config\test_config_overlay.py:30 | used |
| configs/eval/baselines.yaml | baselines.item_knn.block_elements | schema:package\config\_schemas.py:244; code:tests\tools\utilities\test_contract_utilities.py:18; test:tests\tools\utilities\test_contract_utilities.py:18 | used |
| configs/eval/baselines.yaml | baselines.bpr_mf.embedding_dim | schema:package\config\_schemas.py:252; code:tests\recommenders\test_contract_recommenders.py:213; test:tests\recommenders\test_contract_recommenders.py:213 | used |
| configs/eval/baselines.yaml | baselines.bpr_mf.learning_rate | schema:package\config\_schemas.py:253; code:tests\recommenders\test_contract_recommenders.py:243; test:tests\recommenders\test_contract_recommenders.py:243 | used |
| configs/eval/baselines.yaml | baselines.bpr_mf.reg | schema:package\config\_schemas.py:254; sh:tests\agents\run_tests.sh:6; md:AGENTS.md:11 | used |
| configs/eval/baselines.yaml | baselines.bpr_mf.epochs | schema:package\config\_schemas.py:255; code:tests\recommenders\test_contract_recommenders.py:213; test:tests\recommenders\test_contract_recommenders.py:213 | used |
| configs/eval/baselines.yaml | baselines.bpr_mf.batch_size | schema:package\config\_schemas.py:256; code:scripts\evaluation\ranking_eval.py:136; test:tests\recommenders\test_contract_recommenders.py:213 | used |
| configs/eval/candidate_recall.yaml | candidate_recall.budgets | schema:package\config\_schemas.py:312; code:scripts\evaluation\candidate_recall.py:147; md:repo reading.md:727 | used |
| configs/eval/candidate_recall.yaml | candidate_recall.per_segment | schema:package\config\_schemas.py:62; code:package\evaluation\ablation\_loader.py:116; test:tests\config\test_config_overlay.py:25 | used |
| configs/eval/candidate_recall.yaml | candidate_recall.seed_items | schema:package\config\_schemas.py:266; code:scripts\evaluation\candidate_recall.py:153; md:experiments\test_logs\test_results_20261108_235155.md:60799 | used |
| configs/eval/candidate_recall.yaml | candidate_recall.query_items | schema:package\config\_schemas.py:267; code:scripts\evaluation\candidate_recall.py:154; md:experiments\test_logs\test_results_20261108_235155.md:60799 | used |
| configs/eval/candidate_recall.yaml | candidate_recall.query_modes | schema:package\config\_schemas.py:316; code:package\config\_schemas.py:323; md:experiments\test_logs\test_results_20261108_235155.md:875 | used |
| configs/eval/candidate_recall.yaml | candidate_recall.metadata_policy | schema:package\config\_schemas.py:73; code:package\config\_schemas.py:100; test:tests\evaluation\ablation\test_loader.py:208 | used |
| configs/eval/candidate_recall.yaml | candidate_recall.query_normalization | schema:package\config\_schemas.py:271; code:package\config\_schemas.py:285; test:tests\tools\evaluation\test_ranking_streaming.py:52 | used |
| configs/eval/candidate_recall.yaml | candidate_recall.use_prebuilt_corpus | schema:package\config\_schemas.py:74; code:scripts\demo\run_demo.py:47; test:tests\tools\evaluation\test_ranking_streaming.py:52 | used |
| configs/eval/candidate_recall.yaml | candidate_recall.allow_missing_corpus_sources | schema:package\config\_schemas.py:75; code:package\evaluation\campaign\campaign_runner.py:217; test:tests\evaluation\campaign\test_campaign.py:391 | used |
| configs/eval/candidate_recall.yaml | candidate_recall.min_metadata_coverage | schema:package\config\_schemas.py:67; code:package\data\pipeline\build_artifacts.py:47; md:experiments\test_logs\test_results_20261108_235155.md:14764 | used |
| configs/eval/categories_any_benchmark.yaml | categories_any_benchmark.iterations | schema:package\config\_schemas.py:418; code:benchmarks\benchmark_categories_any.py:150; md:experiments\test_logs\test_results_20261108_235155.md:23317 | used |
| configs/eval/categories_any_benchmark.yaml | categories_any_benchmark.limit | schema:package\config\_schemas.py:419; code:package\agents\planner\_prompt.py:35; test:tests\agents\test_end_to_end.py:130 | used |
| configs/eval/categories_any_benchmark.yaml | categories_any_benchmark.queries | schema:package\config\_schemas.py:420; code:benchmarks\benchmark_categories_any.py:180; md:repo reading.md:248 | used |
| configs/eval/component_benchmarks.yaml | component_benchmarks.runs | schema:package\config\_schemas.py:428; code:package\evaluation\campaign\_schema.py:336; md:repo reading.md:520 | used |
| configs/eval/component_benchmarks.yaml | component_benchmarks.configs.executor.reflect_rounds | schema:package\config\_schemas.py:32; code:package\agents\_limits.py:34; test:tests\agents\test_plan_reflect.py:32 | used |
| configs/eval/component_benchmarks.yaml | component_benchmarks.configs.grounding.use_jev | code:package\evaluation\component\benchmarks\grounding_benchmark.py:26; test:tests\evaluation\component\benchmarks\test_grounding_benchmark.py:36; md:experiments\test_logs\test_results_20261108_235155.md:35818 | used |
| configs/eval/component_benchmarks.yaml | component_benchmarks.configs.memory.thresholds.min.all_fields_match_mean | md:repo reading.md:426 | doc-only |
| configs/eval/component_benchmarks.yaml | component_benchmarks.configs.memory.thresholds.min.success_rate | code:package\evaluation\campaign\campaign_runner.py:414; test:tests\evaluation\component\test_memory_correctness.py:117; md:repo reading.md:32 | used |
| configs/eval/component_benchmarks.yaml | component_benchmarks.configs.memory.thresholds.max.future_leakage_max | code:tests\evaluation\component\test_memory_correctness.py:139; test:tests\evaluation\component\test_memory_correctness.py:139; md:repo reading.md:426 | used |
| configs/eval/judge.yaml | provider | schema:package\config\_schemas.py:113; code:package\api\build_judgment_provider.py:27; test:tests\agents\test_llm_provider.py:18 | used |
| configs/eval/judge.yaml | api_key | schema:package\config\_schemas.py:116; code:package\api\build_judgment_provider.py:30; test:tests\config\test_config_loader.py:57 | used |
| configs/eval/judge.yaml | model | schema:package\config\_schemas.py:114; code:package\api\build_judgment_provider.py:31; test:tests\agents\test_end_to_end.py:38 | used |
| configs/eval/judge.yaml | base_url | schema:package\config\_schemas.py:115; code:package\api\build_judgment_provider.py:32; test:tests\agents\test_llm_provider.py:30 | used |
| configs/eval/judge.yaml | timeout_seconds | schema:package\config\_schemas.py:117; code:package\api\build_judgment_provider.py:33; test:tests\agents\test_llm_provider.py:32 | used |
| configs/eval/judge.yaml | enable_long_context | code:package\evaluation\product_reply\evaluate_product_reply_with_jev.py:240; test:tests\evaluation\test_judge_error_handling.py:28; md:experiments\test_logs\test_results_20261108_235155.md:39635 | used |
| configs/eval/judge.yaml | evaluation.faithfulness.claim_extraction | code:tests\evaluation\test_judge_error_handling.py:31; test:tests\evaluation\test_judge_error_handling.py:31 | used |
| configs/eval/judge.yaml | evaluation.faithfulness.support_threshold | code:package\evaluation\product_reply\evaluate_product_reply_with_jev.py:238; test:tests\evaluation\test_judge_error_handling.py:32; md:experiments\test_logs\test_results_20261109_003136.md:253 | used |
| configs/eval/judge.yaml | evaluation.faithfulness.instructions | code:package\api\jev_provider.py:85; test:tests\evaluation\test_judge_error_handling.py:33; md:experiments\test_logs\test_results_20261108_235155.md:7286 | used |
| configs/eval/judge.yaml | evaluation.communication.criteria.relevance.instructions | code:package\api\jev_provider.py:85; test:tests\evaluation\test_judge_error_handling.py:33; md:experiments\test_logs\test_results_20261108_235155.md:7286 | used |
| configs/eval/judge.yaml | evaluation.communication.criteria.relevance.rubric | code:package\evaluation\product_reply\evaluate_product_reply_with_jev.py:379; test:tests\evaluation\test_judge_error_handling.py:37; md:experiments\test_logs\test_results_20261109_003136.md:255 | used |
| configs/eval/judge.yaml | evaluation.communication.criteria.clarity.instructions | code:package\api\jev_provider.py:85; test:tests\evaluation\test_judge_error_handling.py:33; md:experiments\test_logs\test_results_20261108_235155.md:7286 | used |
| configs/eval/judge.yaml | evaluation.communication.criteria.clarity.rubric | code:package\evaluation\product_reply\evaluate_product_reply_with_jev.py:379; test:tests\evaluation\test_judge_error_handling.py:37; md:experiments\test_logs\test_results_20261109_003136.md:255 | used |
| configs/eval/judge.yaml | evaluation.communication.criteria.language.instructions | code:package\api\jev_provider.py:85; test:tests\evaluation\test_judge_error_handling.py:33; md:experiments\test_logs\test_results_20261108_235155.md:7286 | used |
| configs/eval/judge.yaml | evaluation.communication.criteria.language.rubric | code:package\evaluation\product_reply\evaluate_product_reply_with_jev.py:379; test:tests\evaluation\test_judge_error_handling.py:37; md:experiments\test_logs\test_results_20261109_003136.md:255 | used |
| configs/eval/judge.yaml | evaluation.communication.criteria.honesty_about_gaps.instructions | code:package\api\jev_provider.py:85; test:tests\evaluation\test_judge_error_handling.py:33; md:experiments\test_logs\test_results_20261108_235155.md:7286 | used |
| configs/eval/judge.yaml | evaluation.communication.criteria.honesty_about_gaps.rubric | code:package\evaluation\product_reply\evaluate_product_reply_with_jev.py:379; test:tests\evaluation\test_judge_error_handling.py:37; md:experiments\test_logs\test_results_20261109_003136.md:255 | used |
| configs/eval/memory_utility.yaml | memory_utility.baseline_agent | schema:package\config\_schemas.py:369; code:package\evaluation\component\benchmarks\memory_utility.py:50 | used |
| configs/eval/memory_utility.yaml | memory_utility.memory_agent | schema:package\config\_schemas.py:370; code:package\evaluation\component\benchmarks\memory_utility.py:51 | used |
| configs/eval/memory_utility.yaml | memory_utility.k | schema:package\config\_schemas.py:61; code:package\data\pipeline\build_artifacts.py:48; test:tests\config\test_config_overlay.py:30 | used |
| configs/eval/memory_utility.yaml | memory_utility.resamples | schema:package\config\_schemas.py:372; code:package\evaluation\component\benchmarks\memory_utility.py:46; test:tests\evaluation\component\test_memory_utility.py:104 | used |
| configs/eval/memory_utility.yaml | memory_utility.confidence | schema:package\config\_schemas.py:208; code:package\evaluation\ablation\_limits.py:32; test:tests\evaluation\test_jev_reliability.py:30 | used |
| configs/eval/memory_utility.yaml | memory_utility.min_n | schema:package\config\_schemas.py:374; code:package\evaluation\component\benchmarks\memory_utility.py:48; md:experiments\test_logs\test_results_20261108_235155.md:28857 | used |
| configs/eval/memory_utility.yaml | memory_utility.seed | schema:package\config\_schemas.py:210; code:package\evaluation\ablation\_limits.py:40; test:tests\data\test_diagnose_splits.py:259 | used |
| configs/eval/memory_utility.yaml | memory_utility.dirs | schema:package\config\_schemas.py:376; code:package\evaluation\component\benchmarks\memory_utility.py:59; test:tests\evaluation\component\test_memory_utility.py:104 | used |
| configs/eval/memory_utility.yaml | memory_utility.baseline_dirs | schema:package\config\_schemas.py:377; code:package\evaluation\component\benchmarks\memory_utility.py:59 | used |
| configs/eval/memory_utility.yaml | memory_utility.memory_dirs | schema:package\config\_schemas.py:378; code:package\evaluation\component\benchmarks\memory_utility.py:60 | used |
| configs/eval/memory_utility.yaml | memory_utility.metrics | schema:package\config\_schemas.py:211; code:package\evaluation\ablation\_limits.py:42; test:tests\evaluation\component\test_run_all.py:21 | used |
| configs/eval/ranking_diagnostics.yaml | ranking_diagnostics.seed | schema:package\config\_schemas.py:210; code:package\evaluation\ablation\_limits.py:40; test:tests\data\test_diagnose_splits.py:259 | used |
| configs/eval/ranking_diagnostics.yaml | ranking_diagnostics.bootstrap_samples | schema:package\config\_schemas.py:440; code:scripts\evaluation\analyze_ranking_bottlenecks.py:80; md:repo reading.md:1045 | used |
| configs/eval/ranking_eval.yaml | ranking_eval.per_segment | schema:package\config\_schemas.py:62; code:package\evaluation\ablation\_loader.py:116; test:tests\config\test_config_overlay.py:25 | used |
| configs/eval/ranking_eval.yaml | ranking_eval.candidate_budget | schema:package\config\_schemas.py:265; code:scripts\evaluation\ranking_eval.py:126; test:tests\tools\evaluation\test_ranking_streaming.py:50 | used |
| configs/eval/ranking_eval.yaml | ranking_eval.seed_items | schema:package\config\_schemas.py:266; code:scripts\evaluation\candidate_recall.py:153; md:experiments\test_logs\test_results_20261108_235155.md:60799 | used |
| configs/eval/ranking_eval.yaml | ranking_eval.query_items | schema:package\config\_schemas.py:267; code:scripts\evaluation\candidate_recall.py:154; md:experiments\test_logs\test_results_20261108_235155.md:60799 | used |
| configs/eval/ranking_eval.yaml | ranking_eval.ks | schema:package\config\_schemas.py:268; code:package\config\_schemas.py:292; test:tests\tools\evaluation\test_ranking_streaming.py:50 | used |
| configs/eval/ranking_eval.yaml | ranking_eval.popularity_weights | schema:package\config\_schemas.py:269; code:package\config\_schemas.py:299; test:tests\tools\evaluation\test_ranking_streaming.py:51 | used |
| configs/eval/ranking_eval.yaml | ranking_eval.metadata_policy | schema:package\config\_schemas.py:73; code:package\config\_schemas.py:100; test:tests\evaluation\ablation\test_loader.py:208 | used |
| configs/eval/ranking_eval.yaml | ranking_eval.query_normalization | schema:package\config\_schemas.py:271; code:package\config\_schemas.py:285; test:tests\tools\evaluation\test_ranking_streaming.py:52 | used |
| configs/eval/ranking_eval.yaml | ranking_eval.use_prebuilt_corpus | schema:package\config\_schemas.py:74; code:scripts\demo\run_demo.py:47; test:tests\tools\evaluation\test_ranking_streaming.py:52 | used |
| configs/eval/ranking_eval.yaml | ranking_eval.allow_missing_corpus_sources | schema:package\config\_schemas.py:75; code:package\evaluation\campaign\campaign_runner.py:217; test:tests\evaluation\campaign\test_campaign.py:391 | used |
| configs/eval/ranking_eval.yaml | ranking_eval.batch_size | schema:package\config\_schemas.py:256; code:scripts\evaluation\ranking_eval.py:136; test:tests\recommenders\test_contract_recommenders.py:213 | used |
| configs/eval/ranking_eval.yaml | ranking_eval.progress_every | schema:package\config\_schemas.py:275; code:scripts\evaluation\ranking_eval.py:137; test:tests\tools\evaluation\test_ranking_streaming.py:53 | used |
| configs/eval/recommendation_metrics.yaml | recommendation_metrics.k_values | code:package\evaluation\recommender\experiment\ranking_stream_summary.py:137; md:experiments\test_logs\test_results_20261108_235155.md:1117 | used |
| configs/eval/segment_thresholds.yaml | segment_thresholds.sparse_max_history | code:scripts\evaluation\candidate_recall.py:173 | used |
| configs/eval/tool_validation.yaml | tool_validation.model | schema:package\config\_schemas.py:114; code:package\api\build_judgment_provider.py:31; test:tests\agents\test_end_to_end.py:38 | used |
| configs/eval/tool_validation.yaml | tool_validation.eval_users | schema:package\config\_schemas.py:352; code:scripts\tools\run_tools.py:100 | used |
| configs/eval/tool_validation.yaml | tool_validation.negatives | schema:package\config\_schemas.py:353; code:scripts\tools\run_tools.py:101; md:experiments\test_logs\test_results_20261108_235155.md:784 | used |
| configs/eval/tool_validation.yaml | tool_validation.seed | schema:package\config\_schemas.py:210; code:package\evaluation\ablation\_limits.py:40; test:tests\data\test_diagnose_splits.py:259 | used |
| configs/eval/tuning.yaml | tuning.selection_metric | schema:package\config\_schemas.py:400; code:benchmarks\tune_baselines.py:39 | used |
| configs/eval/tuning.yaml | tuning.run_final_test | schema:package\config\_schemas.py:401; code:benchmarks\tune_baselines.py:51 | used |
| configs/eval/tuning.yaml | tuning.models | schema:package\config\_schemas.py:232; code:benchmarks\run_baselines.py:37; md:experiments\test_logs\test_results_20261108_235155.md:1141 | used |
| configs/eval/tuning.yaml | tuning.item_knn.k | schema:package\config\_schemas.py:61; code:package\data\pipeline\build_artifacts.py:48; test:tests\config\test_config_overlay.py:30 | used |
| configs/eval/tuning.yaml | tuning.bpr_mf.embedding_dim | schema:package\config\_schemas.py:252; code:tests\recommenders\test_contract_recommenders.py:213; test:tests\recommenders\test_contract_recommenders.py:213 | used |
| configs/eval/tuning.yaml | tuning.bpr_mf.learning_rate | schema:package\config\_schemas.py:253; code:tests\recommenders\test_contract_recommenders.py:243; test:tests\recommenders\test_contract_recommenders.py:243 | used |
| configs/eval/tuning.yaml | tuning.bpr_mf.reg | schema:package\config\_schemas.py:254; sh:tests\agents\run_tests.sh:6; md:AGENTS.md:11 | used |
| configs/eval/tuning.yaml | tuning.bpr_mf.epochs | schema:package\config\_schemas.py:255; code:tests\recommenders\test_contract_recommenders.py:213; test:tests\recommenders\test_contract_recommenders.py:213 | used |
| configs/evaluation/campaign.yaml | campaign_id | schema:package\config\_schemas.py:76; code:package\evaluation\campaign\campaign_runner.py:219; test:tests\evaluation\campaign\test_campaign.py:458 | used |
| configs/evaluation/campaign.yaml | description | schema:package\config\_schemas.py:222; code:package\demo\_profile_builder.py:51; test:tests\results_report.py:348 | used |
| configs/evaluation/campaign.yaml | dataset.tag | code:package\config\get_data_paths.py:14; test:tests\config\test_config_loader.py:19; md:repo reading.md:35 | used |
| configs/evaluation/campaign.yaml | dataset.split | schema:package\config\_schemas.py:534; code:package\config\_schemas.py:534; test:tests\tools\utilities\test_contract_utilities.py:73 | used |
| configs/evaluation/campaign.yaml | dataset.filters.domains | code:package\config\get_domains.py:10; test:tests\agents\test_phase1_smoke.py:86; md:repo reading.md:10 | used |
| configs/evaluation/campaign.yaml | parameter_grid.agents | schema:package\config\_schemas.py:60; code:package\config\_schemas.py:78; test:tests\evaluation\campaign\test_campaign.py:366 | used |
| configs/evaluation/campaign.yaml | parameter_grid.inference_mode | code:package\demo\backend\live_backend.py:264; test:tests\demo\fakes\offline_backend.py:136; md:repo reading.md:1040 | used |
| configs/evaluation/campaign.yaml | parameter_grid.reflect_rounds | schema:package\config\_schemas.py:32; code:package\agents\_limits.py:34; test:tests\agents\test_plan_reflect.py:32 | used |
| configs/evaluation/campaign.yaml | evaluation_config.per_segment | schema:package\config\_schemas.py:62; code:package\evaluation\ablation\_loader.py:116; test:tests\config\test_config_overlay.py:25 | used |
| configs/evaluation/campaign.yaml | default_agents | code:package\evaluation\campaign\_schema.py:141; md:experiments\test_logs\test_results_20261108_235155.md:34806 | used |
| configs/evaluation/campaign.yaml | allow_missing_corpus_sources | schema:package\config\_schemas.py:75; code:package\evaluation\campaign\campaign_runner.py:217; test:tests\evaluation\campaign\test_campaign.py:391 | used |
| configs/evaluation/campaign.yaml | experiment_timeout_seconds | code:package\evaluation\campaign\_schema.py:143; md:experiments\test_logs\test_results_20261108_235155.md:34806 | used |
| configs/evaluation/campaign.yaml | comparison_pairs | code:package\evaluation\campaign\_schema.py:29; md:repo reading.md:31 | used |
| configs/evaluation/campaign.yaml | statistical_settings.confidence_level | code:tests\evaluation\campaign\test_campaign.py:52; test:tests\evaluation\campaign\test_campaign.py:52; md:repo reading.md:1045 | used |
| configs/evaluation/campaign.yaml | statistical_settings.bootstrap_samples | schema:package\config\_schemas.py:440; code:scripts\evaluation\analyze_ranking_bottlenecks.py:80; md:repo reading.md:1045 | used |
| configs/evaluation/campaign.yaml | statistical_settings.paired_comparison | md:repo reading.md:1045 | doc-only |
| configs/evaluation/campaign.yaml | output_dir | code:package\evaluation\campaign\_schema.py:26; md:repo reading.md:502 | used |
| configs/evaluation/campaign.yaml | metadata.author | md:repo reading.md:954 | doc-only |
| configs/evaluation/campaign.yaml | metadata.created | md:repo reading.md:2 | doc-only |
| configs/evaluation/campaign.yaml | metadata.purpose | md:repo reading.md:358 | doc-only |
| configs/path/data_paths.yaml | paths.src_root | code:package\config\get_data_paths.py:36; test:tests\data\test_pipeline.py:61; md:repo reading.md:461 | used |
| configs/path/data_paths.yaml | paths.config_dir | code:package\config\get_data_paths.py:37; test:tests\data\test_pipeline.py:62; md:repo reading.md:461 | used |
| configs/path/data_paths.yaml | paths.raw_dir | code:package\config\get_data_paths.py:38; test:tests\config\test_config_loader.py:20; md:repo reading.md:479 | used |
| configs/path/data_paths.yaml | paths.cleaned_dir | code:package\config\get_data_paths.py:39; test:tests\data\test_pipeline.py:64; md:repo reading.md:480 | used |
| configs/path/data_paths.yaml | paths.filtered_dir | code:package\config\get_data_paths.py:40; test:tests\data\test_pipeline.py:65; md:repo reading.md:481 | used |
| configs/path/data_paths.yaml | paths.mapped_dir | code:package\config\get_data_paths.py:41; test:tests\data\test_pipeline.py:66; md:repo reading.md:482 | used |
| configs/path/data_paths.yaml | paths.splits_dir | code:package\config\get_data_paths.py:42; test:tests\data\test_pipeline.py:67; md:repo reading.md:483 | used |
| configs/path/data_paths.yaml | paths.item_knn_dir | code:package\config\get_data_paths.py:43; test:tests\data\test_pipeline.py:68; md:repo reading.md:484 | used |
| configs/path/data_paths.yaml | paths.corpus_dir | code:package\config\get_data_paths.py:44; test:tests\data\test_pipeline.py:69; md:repo reading.md:485 | used |
| configs/path/data_paths.yaml | paths.log_dir | code:package\config\get_data_paths.py:45; test:tests\data\test_pipeline.py:70; md:repo reading.md:486 | used |
| configs/path/data_paths.yaml | paths.experiments_dir | code:package\config\get_data_paths.py:46; test:tests\data\test_pipeline.py:71; md:repo reading.md:487 | used |
| configs/path/data_paths.yaml | outputs.baselines | schema:package\config\_schemas.py:525; code:package\config\_schemas.py:525; test:tests\evaluation\campaign\test_campaign.py:378 | used |
| configs/path/data_paths.yaml | outputs.agent_eval | schema:package\config\_schemas.py:517; code:package\config\_schemas.py:517; test:tests\config\test_config_loader.py:140 | used |
| configs/path/data_paths.yaml | outputs.candidate_recall | schema:package\config\_schemas.py:527; code:package\config\_schemas.py:527; md:repo reading.md:121 | used |
| configs/path/data_paths.yaml | outputs.ranking_eval | schema:package\config\_schemas.py:526; code:package\config\_schemas.py:526; test:tests\tools\evaluation\test_ranking_streaming.py:49 | used |
| configs/path/data_paths.yaml | outputs.ranking_diagnostics | schema:package\config\_schemas.py:533; code:package\config\_schemas.py:533; md:repo reading.md:494 | used |
| configs/path/data_paths.yaml | outputs.ablation | schema:package\config\_schemas.py:523; code:package\config\_schemas.py:523; md:repo reading.md:96 | used |
| configs/path/data_paths.yaml | outputs.component_benchmarks | schema:package\config\_schemas.py:532; code:package\config\_schemas.py:532; md:repo reading.md:34 | used |
| configs/path/data_paths.yaml | outputs.memory_utility | schema:package\config\_schemas.py:529; code:package\config\_schemas.py:529; test:tests\evaluation\component\test_memory_utility.py:104 | used |
| configs/path/data_paths.yaml | outputs.multi_turn | code:package\evaluation\reporting\_generator.py:95; test:tests\evaluation\multi_turn\test_evaluator.py:56; md:repo reading.md:98 | used |
| configs/path/data_paths.yaml | outputs.example_report | code:scripts\evaluation\generate_example_report.py:101; md:repo reading.md:1070 | used |
| configs/path/data_paths.yaml | outputs.test_logs | code:tests\results_report.py:50; test:tests\results_report.py:50; sh:tests\run_all_tests.sh:16 | used |
| configs/path/domains.yaml | domains | code:package\config\get_domains.py:10; test:tests\agents\test_phase1_smoke.py:86; md:repo reading.md:10 | used |
| configs/path/run_tag.yaml | tag | code:package\config\get_data_paths.py:14; test:tests\config\test_config_loader.py:19; md:repo reading.md:35 | used |

## Verified findings (manual check of suspected keys)

Automated leaf-key matching has false positives (generic names like `reg`, `k`,
group names iterated as dict keys). The following were verified by reading the
actual consumers:

| key | verdict | evidence |
|---|---|---|
| `path/domains.yaml` → `domains[].role` | **dead** (documentation only) | `package/config/get_domains.py:10` reads only `d["name"]`; no other reader of `role` |
| `eval/judge.yaml` → `evaluation.faithfulness.claim_extraction` | **dead** | `evaluate_product_reply_with_jev.py:238-240` reads only `support_threshold`, `instructions`, `enable_long_context`; `_extract_claims` (line 153) is a fixed function with no mode switch; only a test fixture mentions the key |
| `evaluation/campaign.yaml` → `statistical_settings.*` (confidence_level, bootstrap_samples, paired_comparison) | **dead config** | `campaign/_schema.py:120` stores it as a plain dict; nothing consumes it — campaign comparisons compute plain deltas only (Phase 4.1) |
| `evaluation/campaign.yaml` → `metadata.*` | **stored, unused** | `campaign/_schema.py:121` keeps it; never read downstream |
| `eval/component_benchmarks.yaml` → `configs.executor.reflect_rounds` | **dead (pending D1)** | executor benchmark removed in `89116e8`; `_run_all.py` lists executor only to report `not_implemented`; config unreachable |
| `agent/memory.yaml` → `memory.session.*` (max_turns, max_shown_items, max_candidates, max_turn_chars) | **dead** | schema-validated (`_schemas.py:139-142`) but every production call site uses `Session()` defaults (`run_agent_eval.py:160`, `multi_turn_evaluator.py:128`); yaml comment itself says "TODO: sẽ implement trong P2" |
| `eval/tuning.yaml` → `tuning.*` | **USED** | `benchmarks/tune_baselines.py:36` loads `eval/tuning` and iterates the grids — earlier suspicion resolved |
| `path/data_paths.yaml` → `outputs.multi_turn` | **dormant** | referenced by `reporting/_generator.py:95` and multi_turn tests, but multi_turn runner is not implemented (D3) |
| `path/data_paths.yaml` → `outputs.example_report` | **demo-only** | only `scripts/evaluation/generate_example_report.py` (synthetic demo, not a pipeline) |
| `agent/ablation.yaml` → `ablation.groups.*` | **USED** (false positive) | group names are dict keys consumed by `package/evaluation/ablation/_limits.py` validation + contrasts |

### campaign.yaml bypasses load_config — consequences

`configs/evaluation/campaign.yaml` is parsed directly by
`package/evaluation/campaign/_schema.py` (`CampaignConfig.from_yaml`), NOT via
`package.config.load_config`. Consequences:

- No `extra="forbid"` Pydantic validation — unknown/misspelled top-level keys
  are silently ignored (the runner does reject unknown keys inside
  `agent_config`/`evaluation_config`, but not at campaign level).
- No `${VAR:-default}` env expansion — values are literal.
- No config-overlay (`CONFIG_OVERLAY_PATH`) support for campaign-level settings.
- Recommendation: either route campaign.yaml through `load_config` with a
  schema, or add explicit unknown-key rejection in `CampaignConfig.from_yaml`.
  Decision deferred — report only.
