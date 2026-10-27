"""LiveBackend: backend thật dùng PlanExecutor và Type1Agent với dữ liệu thật."""

from __future__ import annotations

import threading
import time
from typing import Any

import pandas as pd

from package.agents import PlanExecutor, Type1Agent, build_tools
from package.agents.type1.recommend_from_intent import recommend_from_intent
from package.agents.type1.recent_seed_items import recent_seed_items
from package.api import build_llm_provider
from package.api import LLMProviderError
from package.config import get_data_paths, load_config
from package.data import ITEM_ID_SEPARATOR
from package.data.mapping import load_mappings
from package.data.pipeline import build_meta_files
from package.data.split import load_splits
from package.inference import compose_answer, get_inference_limits, MODES, outcome_from_plan_results, outcome_from_type1
from package.tools import BaselineScorer, ItemCorpus, ToolCallLogger
from package.tools.corpus import build_corpus
from package.tools.corpus.load_corpus import load_corpus
from package.tools.evaluation import select_fit_target
from package.tools.recommenders import ItemKNNRecommender
from package.tools.recommenders.load_item_knn import load_item_knn
from package.tools.recommenders.fit_provenance import fit_provenance
from package.tools.recommenders.item_knn_data_hash import item_knn_data_hash
from ..adapter import adapt_from_plan_executor
from ..adapter import adapt_from_plan_executor_error
from ..view import DemoItem, DemoRequest, DemoResult, DemoTrace


class LiveBackend:
    """Backend thật: tải dữ liệu một lần, xử lý request tuần tự."""

    def __init__(
        self,
        tag: str | None = None,
        domain: list[str] | None = None,
        eval_on: str = "validation",
        use_prebuilt: bool = True,
        allow_missing_corpus_sources: bool = False,
    ) -> None:
        self._lock = threading.Lock()
        self._tag = tag
        self._domain = domain
        self._eval_on = eval_on
        self._use_prebuilt = use_prebuilt
        self._allow_missing_corpus_sources = allow_missing_corpus_sources
        self._executor_planner: PlanExecutor | None = None
        self._executor_planner_memory: PlanExecutor | None = None
        self._type1_agent: Type1Agent | None = None
        self._llm: Any = None
        self._item_id_to_metadata: dict[str, dict[str, Any]] = {}
        self._user_id_to_internal_id: dict[str, int] = {}
        self._internal_id_to_user_id: dict[int, str] = {}
        self._item_id_to_internal_id: dict[str, int] = {}
        self._internal_id_to_item_id: dict[int, str] = {}
        self._fit_df: pd.DataFrame | None = None
        self._initialized = False
        self._planner_tools = None
        self._intent_search = None
        self._intent_query = None
        self._knn_provenance = {"status": "not_initialized"}
        self._memory_tool: Any = None  # Store MemoryTool for snapshots

    def initialize(self, *, initialize_planner: bool = True) -> None:
        """Tải dữ liệu và dựng executor (chạy một lần khi khởi động)."""
        if self._initialized:
            if initialize_planner:
                self._ensure_planner()
            return

        print("Đang tải dữ liệu...")
        start_time = time.time()

        # Load config
        agent_eval_cfg = load_config("agent/agent_eval")["agent_eval"]
        baselines_cfg = load_config("eval/baselines")["baselines"]
        k = int(agent_eval_cfg["k"])

        # Load paths
        data_paths = get_data_paths(self._tag)
        meta_files = build_meta_files(data_paths, self._domain)

        # Load splits
        train, val, test = load_splits(data_paths.splits_dir, ("user_idx", "item_idx", "timestamp"))
        fit_df = select_fit_target(train, val, test, self._eval_on)[0]
        # Đơn giản hóa: bỏ qua check_profile_snapshot cho demo (không cần leakage check nghiêm ngặt)
        as_of = None  # demo không cần chống leakage

        # Load mappings
        user2id, item2id = load_mappings(data_paths.mapped_dir)
        if not any(ITEM_ID_SEPARATOR in key for key in list(item2id.keys())[:1000]):
            raise RuntimeError("Mapping has plain item ids; need namespaced 'Domain::asin' ids")
        id2item = {v: k for k, v in item2id.items()}
        id2user = {v: k for k, v in user2id.items()}

        # Build corpus
        print("Đang nạp corpus...")
        if self._use_prebuilt:
            corpus_path = data_paths.corpus_path
            if not corpus_path.exists():
                raise RuntimeError(
                    f"Corpus file not found: {corpus_path}\n"
                    f"Run: python scripts/data_pipeline/run_pipeline.py --stages 4 --tag {data_paths.tag}\n"
                    f"Or use --no-prebuilt to build in RAM (slower, for debug or small tags)"
                )
            print(f"Load corpus from {corpus_path}")
            corpus, coverage = load_corpus(
                corpus_path, meta_files, item2id, float(agent_eval_cfg["min_metadata_coverage"]),
                allow_missing_sources=self._allow_missing_corpus_sources,
            )
            file_size_mb = corpus_path.stat().st_size / (1024 * 1024)
            print(f"Corpus: loaded from {corpus_path} in (see backup time above) ({file_size_mb:.1f} MB)")
        else:
            print("Build corpus in RAM (--no-prebuilt)")
            corpus, meta, coverage, build_times = build_corpus(meta_files, item2id, float(agent_eval_cfg["min_metadata_coverage"]), timing=True)
            print(f"Corpus: built in {sum(build_times.values()):.2f}s")

        # Build item_id_to_metadata từ corpus
        self._item_id_to_metadata = {}
        sample_item_ids = list(item2id.keys())[:10000]  # giới hạn để demo nhanh hơn
        if sample_item_ids:
            marks = ",".join("?" for _ in sample_item_ids)
            rows, _ = corpus.select(
                f"SELECT item_id, domain, title, store, price, average_rating, rating_number, main_category "
                f"FROM items WHERE item_id IN ({marks})",
                sample_item_ids,
                max_rows=len(sample_item_ids),
            )
            self._item_id_to_metadata = {row["item_id"]: row for row in rows}

        # Fit ItemKNN
        print("Đang nạp ItemKNN...")
        knn_k = int(baselines_cfg["item_knn"]["k"])
        fit_pairs = fit_df[["user_idx", "item_idx"]]
        if self._use_prebuilt:
            item_knn_path = data_paths.item_knn_path(self._eval_on)
            if not item_knn_path.exists():
                raise RuntimeError(
                    f"ItemKNN file not found: {item_knn_path}\n"
                    f"Run: python scripts/data_pipeline/run_pipeline.py --stages 4 --tag {data_paths.tag} --eval-on {self._eval_on}\n"
                    f"Or use --no-prebuilt to fit in RAM (slower, for debug or small tags)"
                )
            print(f"Load ItemKNN from {item_knn_path}")
            try:
                knn = load_item_knn(item_knn_path, knn_k, fit_pairs, user2id=user2id,
                                     item2id=item2id, eval_on=self._eval_on, tag=data_paths.tag)
                self._knn_provenance = {"status": "validated_cache", **knn._provenance}
                fit_time = getattr(knn, "_fit_time", None)
                print(f"ItemKNN: loaded from {item_knn_path} (fit took {fit_time:.1f}s when saved)" if fit_time else f"ItemKNN: loaded from {item_knn_path}")
            except ValueError as exc:
                print(f"  ItemKNN cache rejected ({exc}); fitting from current fit split and mappings")
                self._knn_provenance = {"status": "refit_cache_rejected", "reason": str(exc)}
                t0 = time.perf_counter()
                knn = ItemKNNRecommender(knn_k).fit(fit_pairs)
                knn._fit_time = time.perf_counter() - t0
                print(f"ItemKNN: fitted in {knn._fit_time:.1f}s")
        else:
            self._knn_provenance = {"status": "refit_requested"}
            print("Fit ItemKNN on fit data (--no-prebuilt)")
            t0 = time.perf_counter()
            knn = ItemKNNRecommender(knn_k).fit(fit_pairs)
            knn._fit_time = time.perf_counter() - t0
            print(f"ItemKNN: fitted in {knn._fit_time:.1f}s")

        if not hasattr(knn, "_fit_data_hash"):
            knn._fit_data_hash = item_knn_data_hash(fit_pairs)
        self._knn_provenance.update(
            fit_provenance(fit_pairs, user2id=user2id, item2id=item2id,
                           eval_on=self._eval_on, tag=data_paths.tag))
        self._knn_provenance.update(data_hash=knn._fit_data_hash, neighbors=knn_k)

        # Build tools
        logger = ToolCallLogger()
        tools = build_tools(
            knn, BaselineScorer(knn), user2id, item2id, fit_df, corpus, logger=logger, as_of_timestamp=None
        )

        self._planner_tools = tools
        self._intent_search = tools.search
        self._intent_query = tools.query
        if initialize_planner:
            self._ensure_planner()
        self._type1_agent = Type1Agent(tools.item_cf, tools.reco, tools.query)

        # Store mappings
        self._user_id_to_internal_id = user2id
        self._internal_id_to_user_id = id2user
        self._item_id_to_internal_id = item2id
        self._internal_id_to_item_id = id2item
        self._fit_df = fit_df

        self._initialized = True
        elapsed = time.time() - start_time
        print(f"Khởi động hoàn tất ({elapsed:.1f}s)")

    def _ensure_planner(self) -> None:
        if self._executor_planner is not None and self._executor_planner_memory is not None:
            return
        if self._planner_tools is None:
            raise RuntimeError("Planner tools not initialized")
        llm = build_llm_provider(load_config("agent/llm"))
        if not llm.health_check():
            raise RuntimeError("LLM health check failed: check configs/agent/llm.yaml và LLM_API_KEY")
        self._executor_planner = PlanExecutor(llm, self._planner_tools.for_planner())
        self._executor_planner_memory = PlanExecutor(llm, self._planner_tools.for_planner_memory())

    def get_sample_users(self, n_per_segment: int = 3, sparse_max: int | None = None) -> dict[str, list[str]]:
        """Lấy sample users theo segment (cold/sparse/warm)."""
        from ..samples import sample_users
        return sample_users(self._fit_df, self._user_id_to_internal_id, n_per_segment=n_per_segment, sparse_max=sparse_max)

    def get_profiles(self) -> list[DemoProfile]:
        """Lấy danh sách profiles (blank, pinned, auto)."""
        if not self._initialized:
            raise RuntimeError("Backend not initialized. Call initialize() first.")
        return build_profiles(self._fit_df, self._user_id_to_internal_id)

    def respond(self, request: DemoRequest) -> DemoResult:
        """Xử lý request với locking (chạy tuần tự)."""
        with self._lock:
            if request.mode not in ("type1","planner"):
                return DemoResult("tool_error","Chế độ xử lý không hợp lệ.",[],None,{},"Unknown agent mode")
            if request.mode=="planner" and (request.intent_query is not None or request.intent_filters is not None):
                question="Chọn Type1 để dùng từ khóa và bộ lọc riêng, hoặc chuyển các điều kiện vào mô tả tự do của Planner."
                return DemoResult("ask_user",question,[],DemoTrace([],[],question,0,False,False,{}),{},None)
            if not self._initialized:
                try:
                    self.initialize(initialize_planner=request.mode != "type1")
                except Exception as exc:
                    return DemoResult(
                        status="tool_error",
                        text="Lỗi khi khởi động backend.",
                        items=[],
                        trace=None,
                        usage={},
                        error=f"Init error: {type(exc).__name__}: {str(exc)[:200]}",
                    )

            try:
                if request.mode == "type1":
                    return self._respond_type1(request)
                else:  # planner
                    return self._respond_planner(request)
            except (ValueError, LLMProviderError) as exc:
                return adapt_from_plan_executor_error(exc, request)
            except Exception as exc:
                return DemoResult(
                    status="tool_error",
                    text="Có lỗi không mong muốn xảy ra.",
                    items=[],
                    trace=None,
                    usage={},
                    error=f"{type(exc).__name__}: {str(exc)[:200]}",
                )

    def _respond_planner(self, request: DemoRequest) -> DemoResult:
        """Xử lý request với PlanExecutor."""
        self._ensure_planner()
        executor = (
            self._executor_planner_memory if request.use_memory else self._executor_planner
        )
        if executor is None:
            raise RuntimeError("Executor not initialized")

        # Validate inference_mode
        inference_mode = getattr(request, "inference_mode", get_inference_limits().mode)
        if inference_mode not in MODES:
            raise ValueError(f"inference_mode must be one of {list(MODES)}, got {inference_mode!r}")

        # Identity injection
        user_id = getattr(request, "user_id", None)
        effective_text = request.text
        if user_id and user_id not in request.text:
            # Inject identity sentence (vi by default)
            injection = IDENTITY_INJECTION_VI.format(user_id=user_id)
            effective_text = f"{injection} {request.text}"

        # Cập nhật reflect_rounds từ request
        original_reflect = executor.reflect_rounds
        executor.reflect_rounds = request.reflect_rounds

        # Memory snapshots (before and after)
        memory_before = take_memory_snapshot(self._memory_tool, user_id) if request.use_memory else None

        try:
            results = executor.run(effective_text)
            plan_error = None
        except (ValueError, LLMProviderError) as exc:
            # Lỗi từ executor.run -> chuyển thành plan_error cho Inference
            plan_error = f"{type(exc).__name__}: {exc}"
            results = []
        finally:
            executor.reflect_rounds = original_reflect

        memory_after = take_memory_snapshot(self._memory_tool, user_id) if request.use_memory else None

        # Dựng trace từ executor (tái sử dụng logic từ adapt_from_plan_executor)
        trace = DemoTrace(
            plan=executor.last_plan,
            steps=[
                {
                    "tool": r.get("tool"),
                    "ok": r.get("ok"),
                    "error": None if r.get("error") is None else str(r["error"])[:get_demo_limits().max_error_length],
                    "latency_seconds": r.get("latency_seconds"),
                    "args": r.get("args"),
                    "output_summary": r.get("output_summary"),
                }
                for r in results
            ],
            ask_user=executor.last_question,
            reflections=executor.last_reflections,
            first_attempt_ok=executor.last_first_attempt_ok,
            truncated=executor.last_truncated,
            usage=dict(executor.last_usage),
        )

        # Build MemoryView
        memory_view = self._build_memory_view(
            request.use_memory, results, memory_before, memory_after
        )

        # Dựng AgentOutcome và gọi Inference
        outcome = outcome_from_plan_results(effective_text, results, question=executor.last_question, plan_error=plan_error)

        try:
            answer = compose_answer(outcome, self._llm, mode=inference_mode)
        except Exception as exc:
            # Lỗi bất ngờ từ compose_answer (không nên xảy ra vì đã có fallback)
            return DemoResult(
                status="tool_error",
                text="Có lỗi không mong muốn xảy ra khi tạo câu trả lời.",
                items=[],
                trace=trace,
                usage={},
                error=f"{type(exc).__name__}: {str(exc)[:200]}",
                memory=memory_view,
            )

        result = adapt_from_inference(answer, request=request, item_id_to_metadata=self._item_id_to_metadata, trace=trace)
        result.memory = memory_view
        return result

    def _build_memory_view(
        self,
        use_memory: bool,
        results: list[dict[str, Any]],
        memory_before: dict[str, Any] | None,
        memory_after: dict[str, Any] | None,
    ) -> MemoryView | None:
        """Build MemoryView từ executor results và memory snapshots."""
        if not use_memory:
            # Memory off: show profile data but label as not visible to agent
            return MemoryView(
                enabled=False,
                called=False,
                n_calls=0,
                before=memory_before,
                after=memory_after,
                agent_calls=[],
                consumed_by=[],
            )

        # Memory on: analyze executor results
        memory_step_indices = [
            i for i, r in enumerate(results) if r.get("tool") == "MemoryTool"
        ]
        agent_calls = [
            {
                "tool": r.get("tool"),
                "ok": r.get("ok"),
                "error": r.get("error"),
                "args": r.get("args"),
                "data": r.get("data"),
            }
            for r in results
            if r.get("tool") == "MemoryTool"
        ]
        consumed_by = detect_consumed_by(results, memory_step_indices)

        return MemoryView(
            enabled=True,
            called=len(memory_step_indices) > 0,
            n_calls=len(memory_step_indices),
            before=memory_before,
            after=memory_after,
            agent_calls=agent_calls,
            consumed_by=consumed_by,
        )

    def _respond_type1(self, request: DemoRequest) -> DemoResult:
        """Xử lý request với Type1Agent và Inference."""
        agent = self._type1_agent
        if agent is None:
            raise RuntimeError("Type1Agent not initialized")

        # Lấy seed item từ lịch sử user (đơn giản hóa: lấy item cuối cùng)
        user_internal_id = self._user_id_to_internal_id.get(request.user_id)
        user_history = self._fit_df[self._fit_df["user_idx"] == user_internal_id]
        if request.intent_query is not None or request.intent_filters is not None or user_history.empty:
            return self._respond_intent(request, user_history)

        seeds = recent_seed_items(user_history,self._internal_id_to_item_id,count=1)
        if not seeds:
            return DemoResult(
                status="tool_error",
                text="Không tìm thấy item seed.",
                items=[],
                trace=None,
                usage={},
                error="Seed item not found",
            )

        out = agent.recommend(request.user_id, seeds, top_k=10)
        if not out["ok"]:
            if out.get("stage")=="retrieve" and out.get("error")=="no candidates returned":
                return self._respond_intent(request,user_history)
            return DemoResult(
                status="tool_error",
                text=f"Lỗi Type1Agent: {out.get('stage')}",
                items=[],
                trace=None,
                usage={},
                error=f"{out.get('stage')}: {out.get('error')}",
            )

        # Convert sang DemoItem
        items = []
        for item in out["items"]:
            item_id = item.get("item_id", "")
            meta = {**self._item_id_to_metadata.get(item_id, {}), **item}
            items.append(
                DemoItem(
                    item_id=item_id,
                    domain=meta.get("domain", ""),
                    title=meta.get("title", ""),
                    store=meta.get("store"),
                    price=meta.get("price"),
                    average_rating=meta.get("average_rating"),
                    rating_number=meta.get("rating_number"),
                    main_category=meta.get("main_category"),
                )
            )

        return DemoResult(
            status="ok" if items else "no_result",
            text=f"Dựa trên lịch sử mua hàng của bạn, đây là {len(items)} sản phẩm tương tự.",
            items=items,
            trace=None,  # Type1Agent không có trace chi tiết
            usage={},
            error=None,
            recommendation_source="history_itemcf",
        )

    def _respond_intent(self, request: DemoRequest, history: pd.DataFrame) -> DemoResult:
        if not request.intent_query or not request.intent_query.strip():
            question="Bạn muốn tìm sản phẩm gì? Hãy điền từ khóa sản phẩm và bộ lọc giá; nếu muốn mô tả tự do, chọn Planner."
            return DemoResult("ask_user",question,[],DemoTrace([],[],question,0,False,False,{}),{},None)
        if self._intent_search is None or self._intent_query is None:
            raise RuntimeError("Intent tools not initialized")
        seen=[self._internal_id_to_item_id[int(i)] for i in history.item_idx.unique()
              if int(i) in self._internal_id_to_item_id]
        out=recommend_from_intent(self._intent_search,self._intent_query,request.intent_query,
                                  filters=request.intent_filters,seen_items=seen,top_k=10)
        items=[DemoItem(item_id=r["item_id"],domain=r.get("domain", ""),title=r.get("title") or "",
                        store=r.get("store"),price=r.get("price"),average_rating=r.get("average_rating"),
                        rating_number=r.get("rating_number"),main_category=r.get("main_category")) for r in out["items"]]
        text={"ok":f"Tìm thấy {len(items)} sản phẩm theo từ khóa và bộ lọc bạn cung cấp.",
              "no_result":"Không tìm thấy sản phẩm phù hợp; bạn có thể đổi từ khóa hoặc bộ lọc.",
              "tool_error":"Không thể hoàn tất tìm kiếm. Hãy kiểm tra từ khóa tiếng Anh và bộ lọc hoặc thử lại.",
              "ask_user":out["question"]}[out["status"]]
        trace=DemoTrace(out["plan"],out["steps"],out["question"],0,out["status"]=="ok",False,{})
        return DemoResult(out["status"],text,items,trace,{},out["error"],recommendation_source=out["source"])
