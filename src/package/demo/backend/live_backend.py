"""LiveBackend: backend thật dùng PlanExecutor và Type1Agent với dữ liệu thật."""

from __future__ import annotations

import threading
import time
from typing import Any

import pandas as pd

from package.agents import PlanExecutor, Type1Agent, build_tools
from package.api import build_llm_provider
from package.api import LLMProviderError
from package.config import get_data_paths, load_config
from package.data import ITEM_ID_SEPARATOR
from package.data.mapping import load_mappings
from package.data.split import load_splits
from package.tools import BaselineScorer, ItemCorpus, ToolCallLogger
from package.tools.corpus import build_corpus
from package.tools.recommenders import ItemKNNRecommender
from ..adapter import adapt_from_plan_executor
from ..adapter import adapt_from_plan_executor_error
from ..view import DemoItem, DemoRequest, DemoResult


class LiveBackend:
    """Backend thật: tải dữ liệu một lần, xử lý request tuần tự."""

    def __init__(self, tag: str | None = None, domain: list[str] | None = None) -> None:
        self._lock = threading.Lock()
        self._tag = tag
        self._domain = domain
        self._executor_planner: PlanExecutor | None = None
        self._executor_planner_memory: PlanExecutor | None = None
        self._type1_agent: Type1Agent | None = None
        self._item_id_to_metadata: dict[str, dict[str, Any]] = {}
        self._user_id_to_internal_id: dict[str, int] = {}
        self._internal_id_to_user_id: dict[int, str] = {}
        self._item_id_to_internal_id: dict[str, int] = {}
        self._internal_id_to_item_id: dict[int, str] = {}
        self._fit_df: pd.DataFrame | None = None
        self._initialized = False

    def initialize(self) -> None:
        """Tải dữ liệu và dựng executor (chạy một lần khi khởi động)."""
        if self._initialized:
            return

        print("Đang tải dữ liệu...")
        start_time = time.time()

        # Load config
        agent_eval_cfg = load_config("agent/agent_eval")["agent_eval"]
        baselines_cfg = load_config("eval/baselines")["baselines"]
        k = int(agent_eval_cfg["k"])

        # Load paths
        data_paths = get_data_paths(self._tag)
        meta_files = [(d, str(data_paths.meta_path(d))) for d in (self._domain or [])]

        # Load splits
        train, val, test = load_splits(data_paths.splits_dir, ("user_idx", "item_idx", "timestamp"))
        fit_df = train  # đơn giản hóa: dùng train cho fit
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
        corpus, _, _ = build_corpus(meta_files, item2id, float(agent_eval_cfg["min_metadata_coverage"]))

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
        print("Đang fit ItemKNN...")
        knn = ItemKNNRecommender(int(baselines_cfg["item_knn"]["k"])).fit(fit_df[["user_idx", "item_idx"]])

        # Build tools
        logger = ToolCallLogger()
        tools = build_tools(
            knn, BaselineScorer(knn), user2id, item2id, fit_df, corpus, logger=logger, as_of_timestamp=None
        )

        # Build LLM provider
        print("Đang kiểm tra LLM...")
        llm = build_llm_provider(load_config("agent/llm"))
        if not llm.health_check():
            raise RuntimeError("LLM health check failed: check configs/agent/llm.yaml và LLM_API_KEY")

        # Build executors
        self._executor_planner = PlanExecutor(llm, tools.for_planner())
        self._executor_planner_memory = PlanExecutor(llm, tools.for_planner_memory())
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

    def get_sample_users(self, n_per_segment: int = 3, sparse_max: int = 5) -> dict[str, list[str]]:
        """Lấy sample users theo segment (cold/sparse/warm)."""
        from ..samples import sample_users
        return sample_users(self._fit_df, self._user_id_to_internal_id, n_per_segment=n_per_segment, sparse_max=sparse_max)

    def respond(self, request: DemoRequest) -> DemoResult:
        """Xử lý request với locking (chạy tuần tự)."""
        with self._lock:
            if not self._initialized:
                try:
                    self.initialize()
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
        executor = (
            self._executor_planner_memory if request.use_memory else self._executor_planner
        )
        if executor is None:
            raise RuntimeError("Executor not initialized")

        # Cập nhật reflect_rounds từ request
        original_reflect = executor.reflect_rounds
        executor.reflect_rounds = request.reflect_rounds

        try:
            results = executor.run(request.text)
            result = adapt_from_plan_executor(
                results=results,
                executor_last_plan=executor.last_plan,
                executor_last_question=executor.last_question,
                executor_last_reflections=executor.last_reflections,
                executor_last_first_attempt_ok=executor.last_first_attempt_ok,
                executor_last_truncated=executor.last_truncated,
                executor_last_usage=executor.last_usage,
                request=request,
                item_id_to_metadata=self._item_id_to_metadata,
            )
            return result
        finally:
            executor.reflect_rounds = original_reflect

    def _respond_type1(self, request: DemoRequest) -> DemoResult:
        """Xử lý request với Type1Agent."""
        agent = self._type1_agent
        if agent is None:
            raise RuntimeError("Type1Agent not initialized")

        if request.user_id is None:
            return DemoResult(
                status="tool_error",
                text="Type1Agent cần user_id.",
                items=[],
                trace=None,
                usage={},
                error="Type1Agent requires user_id",
            )

        # Lấy seed item từ lịch sử user (đơn giản hóa: lấy item cuối cùng)
        user_internal_id = self._user_id_to_internal_id.get(request.user_id)
        if user_internal_id is None:
            return DemoResult(
                status="tool_error",
                text=f"Không tìm thấy user {request.user_id}.",
                items=[],
                trace=None,
                usage={},
                error=f"User not found: {request.user_id}",
            )

        user_history = self._fit_df[self._fit_df["user_idx"] == user_internal_id]
        if user_history.empty:
            return DemoResult(
                status="no_result",
                text="User này chưa có lịch sử mua hàng.",
                items=[],
                trace=None,
                usage={},
                error=None,
            )

        last_item_internal_id = user_history.iloc[-1]["item_idx"]
        seed_item_id = self._internal_id_to_item_id.get(last_item_internal_id)
        if seed_item_id is None:
            return DemoResult(
                status="tool_error",
                text="Không tìm thấy item seed.",
                items=[],
                trace=None,
                usage={},
                error="Seed item not found",
            )

        out = agent.recommend(request.user_id, [seed_item_id], top_k=10)
        if not out["ok"]:
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
            meta = self._item_id_to_metadata.get(item_id, {})
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
            status="ok",
            text=f"Dựa trên lịch sử mua hàng của bạn, đây là {len(items)} sản phẩm tương tự.",
            items=items,
            trace=None,  # Type1Agent không có trace chi tiết
            usage={},
            error=None,
        )
