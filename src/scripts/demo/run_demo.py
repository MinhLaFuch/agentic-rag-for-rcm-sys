"""
Demo UI với Gradio cho hệ gợi ý sản phẩm bằng LLM agent.

Cách chạy:
    PYTHONPATH=. python scripts/demo/run_demo.py --mock               # Chế độ mẫu (không cần dữ liệu/LLM)
    PYTHONPATH=. python scripts/demo/run_demo.py --tag v1 --domain Video_Games  # Chế độ thật
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Any

try:
    import gradio as gr
except ImportError:
    print("ERROR: gradio not installed")
    print("Please install with: pip install gradio")
    sys.exit(1)

from package.config import get_data_paths, get_domains, load_config
from package.demo import (
    DemoProfile,
    DemoRequest,
    MockBackend,
    LiveBackend,
    format_items,
    format_memory,
    format_trace,
    status_badge,
    sample_requests,
)
from package.utils import ensure_utf8_stdout


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Demo UI for LLM agent recommender system")
    ap.add_argument("--mock", action="store_true", help="Run in mock mode (no data/LLM/network needed)")
    ap.add_argument("--tag", help="Data tag (default: tag from run_tag.yaml)")
    ap.add_argument("--eval-on", choices=["validation", "test"], default="validation", help="Split to load data from")
    ap.add_argument("--domain", action="append", help="Domain to load (repeatable; default: all)")
    ap.add_argument("--no-prebuilt", action="store_true", help="Build corpus and ItemKNN in RAM instead of loading from prebuilt files (for debug or small tags)")
    ap.add_argument(
        "--allow-missing-corpus-sources",
        action="store_true",
        help="Load a prebuilt corpus when raw metadata files are unavailable; schema and item mapping are still validated.",
    )
    ap.add_argument("--host", default="127.0.0.1", help="Host to run server (default: 127.0.0.1)")
    ap.add_argument("--port", type=int, default=7860, help="Port to run server (default: 7860)")
    ap.add_argument("--inference-mode", choices=["llm", "template"], default="llm", help="Inference mode: llm (LLM writes answer) or template (deterministic, no LLM)")
    return ap.parse_args()


def build_ui(
    backend: MockBackend | LiveBackend,
    mock_mode: bool,
    profiles: list[DemoProfile] | None = None,
    default_inference_mode: str = "llm",
) -> gr.Blocks:
    """Build Gradio UI."""

    # Prepare profile choices
    if profiles is None:
        profiles = []
    profile_choices = [(p.label, p.profile_id) for p in profiles]
    default_profile_id = profiles[0].profile_id if profiles else "blank"

    # --- Main container ---
    with gr.Blocks(title="Demo LLM Agent Recommender System") as demo:
        gr.Markdown("# Demo LLM Agent Recommender System")

        # --- Warnings ---
        if mock_mode:
            gr.Markdown("⚠️ **MOCK MODE (fake data)** - For demo without real data/LLM/network")
        gr.Markdown("⚠️ **Single-turn demo**: No follow-up questions; send new request for clarification.")

        # --- Input ---
        with gr.Row():
            with gr.Column(scale=1):
                profile_dropdown = gr.Dropdown(
                    label="Profile",
                    choices=profile_choices,
                    value=default_profile_id,
                    interactive=True,
                )
                profile_card = gr.Markdown(label="Profile Card")

            with gr.Column(scale=3):
                request_input = gr.Textbox(
                    label="Request (Planner: mô tả tự do; Type1: dùng lịch sử hoặc trường tìm kiếm bên dưới)",
                    placeholder="e.g., Recommend 5 products similar to Video_Games::B00...",
                    lines=3,
                )
                with gr.Accordion("Sample requests", open=False):
                    for kind, text in sample_requests("vi").items():
                        gr.Button(
                            f"{kind}",
                            size="sm",
                        ).click(
                            lambda t=text: t,
                            outputs=request_input,
                        )

                with gr.Accordion("Type1: tìm theo nhu cầu (không cần lịch sử)", open=False):
                    gr.Markdown("Chọn Type1 và điền từ khóa tiếng Anh theo catalog. Giá dùng USD; sản phẩm không có giá sẽ bị loại khi lọc giá. Từ khóa được ưu tiên thay cho gợi ý từ lịch sử. Mô tả tự do dùng Planner.")
                    intent_query_input = gr.Textbox(label="Từ khóa sản phẩm", placeholder="e.g., wireless keyboard")
                    intent_domain_input = gr.Dropdown(choices=["", *get_domains()],value="",label="Domain (để trống: tất cả)")
                    with gr.Row():
                        intent_min_input = gr.Number(value=None,label="Giá tối thiểu (USD, tùy chọn)")
                        intent_max_input = gr.Number(value=None,label="Giá tối đa (USD, tùy chọn)")

        # --- Toggles ---
        with gr.Row():
            memory_toggle = gr.Checkbox(label="Memory (agent can read profile memory)", value=False)
            reflect_toggle = gr.Radio(
                choices=[("Off (0)", 0), ("On (1)", 1)],
                value=0,
                label="Reflect (fix plan on error)",
            )
            mode_radio = gr.Radio(
                choices=[("Planner (LLM)", "planner"), ("Type1 (no LLM)", "type1")],
                value="planner",
                label="Agent mode",
            )
            inference_radio = gr.Radio(
                choices=[("LLM", "llm"), ("Template", "template")],
                value=default_inference_mode,
                label="Inference",
                interactive=not mock_mode,
            )

        # --- Submit button ---
        submit_btn = gr.Button("Submit", variant="primary", size="lg")

        # --- Results (tabs) ---
        with gr.Tabs():
            with gr.TabItem("Response"):
                with gr.Row():
                    status_output = gr.Markdown(label="Status")
                with gr.Row():
                    text_output = gr.Markdown(label="Response")
                with gr.Row():
                    items_table = gr.Dataframe(
                        label="Recommended items",
                        headers=["Name", "Domain", "Price", "Rating", "Store"],
                        datatype=["str", "str", "str", "str", "str"],
                    )

            with gr.TabItem("Memory"):
                memory_output = gr.Markdown(label="Memory")

            with gr.TabItem("Trace"):
                with gr.Accordion("Execution trace (plan JSON, step logs, usage)", open=True):
                    trace_output = gr.Markdown(label="Trace")

        # --- Turn history ---
        with gr.Row():
            clear_history_btn = gr.Button("Clear history", size="sm")
        turn_history = gr.Dataframe(
            label="Turn history",
            headers=["Turn", "Profile", "Memory", "MemoryTool called?", "Tool sequence", "Status", "#Items"],
            datatype=["number", "str", "str", "str", "str", "str", "number"],
            row_count=5,
            column_count=7,
        )
        turn_history_state = gr.State(value=[])  # Store history as list of dicts

        # --- Event handlers ---
        def on_profile_change(profile_id: str) -> str:
            """Handle profile dropdown change."""
            profile = next((p for p in profiles if p.profile_id == profile_id), None)
            if profile:
                lines = [f"**{profile.label}**", profile.description]
                if profile.user_id:
                    lines.append(f"User ID: {profile.user_id}")
                else:
                    lines.append("User ID: (none - new user)")
                return "\n".join(lines)
            return "Profile not found"

        def on_clear_history() -> list:
            """Clear turn history."""
            return []

        def on_submit(
            profile_id: str,
            request_text: str,
            use_memory: bool,
            reflect_rounds: int,
            mode: str,
            intent_query: str,
            intent_domain: str,
            intent_min: float | None,
            intent_max: float | None,
        ) -> tuple[str, str, list[list[str]], str]:
            """Handle submit button click."""
            structured=bool((intent_query or "").strip() or intent_domain or intent_min is not None or intent_max is not None)
            if structured and mode != "type1":
                return ("⚠️ Chọn Type1 để dùng các trường tìm kiếm này, hoặc xóa chúng và mô tả yêu cầu trong Planner.","",[],"")
            if not request_text.strip() and not structured and not (mode=="type1" and user_id.strip()):
                return (
                    "⚠️ Please enter a request.",
                    "",
                    [],
                    "",
                    "No memory data",
                    history,
                )

            filters={}
            if intent_domain: filters["domain"]=intent_domain
            if intent_min is not None: filters["price_min"]=intent_min
            if intent_max is not None: filters["price_max"]=intent_max
            demo_request = DemoRequest(
                user_id=user_id,
                text=request_text.strip(),
                reflect_rounds=reflect_rounds,
                use_memory=use_memory,
                mode=mode,
                intent_query=(intent_query or "").strip() or None,
                intent_filters=filters or None,
            )

            result = backend.respond(demo_request)

            # Format status
            status_md = f"### {status_badge(result.status)}"
            if result.error:
                status_md += f"\n\n*{result.error}*"

            # Thêm badge cho inference composer và fallback
            if result.trace and result.trace.inference:
                composer = result.trace.inference.get("composer", "unknown")
                fallback = result.trace.inference.get("fallback_reason")
                status_md += f"\n\n**Inference:** {composer}"
                if fallback:
                    status_md += f" (fallback: {fallback})"

            # Format items
            items_rows = format_items(result.items)

            # Format trace
            trace_md = format_trace(result.trace) if result.trace else "No execution trace"

            # Format memory
            memory_md = format_memory(result.memory) if result.memory else "No memory data"
            if mode == "type1":
                memory_md = "Memory not used in Type1 mode"

            # Update turn history
            tool_sequence = " → ".join([s.get("tool", "?") for s in result.trace.steps]) if result.trace else ""
            memory_called = "✓" if (result.memory and result.memory.called) else "✗"
            new_row = [
                len(history) + 1,
                profile.label if profile else profile_id,
                "ON" if use_memory else "OFF",
                memory_called,
                tool_sequence,
                result.status,
                len(result.items),
            ]
            updated_history = history + [new_row]

            return status_md, result.text, items_rows, trace_md, memory_md, updated_history

        profile_dropdown.change(
            fn=on_profile_change,
            inputs=[profile_dropdown],
            outputs=[profile_card],
        )

        profile_dropdown.change(
            fn=on_clear_history,
            inputs=[],
            outputs=[turn_history_state],
        )

        clear_history_btn.click(
            fn=on_clear_history,
            inputs=[],
            outputs=[turn_history_state],
        )

        submit_btn.click(
            fn=on_submit,
            inputs=[user_id_input, request_input, memory_toggle, reflect_toggle, mode_radio,
                    intent_query_input,intent_domain_input,intent_min_input,intent_max_input],
            outputs=[status_output, text_output, items_table, trace_output],
        )

    return demo


def main() -> None:
    ensure_utf8_stdout()
    args = parse_args()

    print("=" * 60)
    print("Demo UI cho He Goi Y San Pham LLM Agent")
    print("=" * 60)

    start_time = time.time()

    if args.mock:
        print("Mode: MOCK (MockBackend)")
        backend = MockBackend()
        profiles = backend.get_profiles()
        print("MockBackend initialized (no data loading needed)")
    else:
        print("Mode: LIVE (LiveBackend)")
        print(f"Tag: {args.tag or '(default)'}")
        print(f"Domain: {args.domain or '(all)'}")
        print(f"Eval-on: {args.eval_on}")

        print("Initializing LiveBackend...")
        backend = LiveBackend(
            tag=args.tag,
            domain=args.domain,
            eval_on=args.eval_on,
            use_prebuilt=not args.no_prebuilt,
            allow_missing_corpus_sources=args.allow_missing_corpus_sources,
        )
        try:
            backend.initialize(initialize_planner=False)
        except Exception as exc:
            print("\n" + "=" * 60)
            print("ERROR: LIVEBACKEND INITIALIZATION FAILED")
            print("=" * 60)
            print(f"Reason: {type(exc).__name__}: {exc}")
            print("\nSuggestion:")
            print("  - Check data has been processed (resource/...)")
            print("  - Check tag and domain")
            print("  - Check LLM_API_KEY environment variable")
            print("  - Run with --mock to demo without real data:")
            print("    PYTHONPATH=. python scripts/demo/run_demo.py --mock")
            sys.exit(1)

        print("Getting profiles...")
        profiles = backend.get_profiles()

    init_elapsed = time.time() - start_time
    print(f"\nStartup time: {init_elapsed:.1f}s")

    print("\nBuilding Gradio UI...")
    demo = build_ui(backend, args.mock, profiles, default_inference_mode=args.inference_mode)

    print(f"\nStarting server at http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop.")
    print("=" * 60)

    demo.launch(
        server_name=args.host,
        server_port=args.port,
        share=False,  # Không share ra Internet
        show_error=True,
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nĐã dừng demo.")
        sys.exit(0)
