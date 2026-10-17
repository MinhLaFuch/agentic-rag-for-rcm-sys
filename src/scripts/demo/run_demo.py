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
    DemoRequest,
    MockBackend,
    LiveBackend,
    format_items,
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
    ap.add_argument("--host", default="127.0.0.1", help="Host to run server (default: 127.0.0.1)")
    ap.add_argument("--port", type=int, default=7860, help="Port to run server (default: 7860)")
    return ap.parse_args()


def build_ui(
    backend: MockBackend | LiveBackend,
    mock_mode: bool,
    sample_user_dict: dict[str, list[str]] | None = None,
) -> gr.Blocks:
    """Build Gradio UI."""

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
                user_id_input = gr.Textbox(label="User ID (optional)", placeholder="e.g., user123")
                if sample_user_dict:
                    with gr.Accordion("Select sample user", open=False):
                        for segment, users in sample_user_dict.items():
                            if users:
                                for user_id in users:
                                    gr.Button(
                                        f"{segment}: {user_id}",
                                        size="sm",
                                    ).click(
                                        lambda uid=user_id: uid,
                                        outputs=user_id_input,
                                    )

            with gr.Column(scale=3):
                request_input = gr.Textbox(
                    label="Request",
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

        # --- Toggles ---
        with gr.Row():
            memory_toggle = gr.Checkbox(label="Memory (use user history)", value=False)
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

        # --- Submit button ---
        submit_btn = gr.Button("Submit", variant="primary", size="lg")

        # --- Results ---
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

        with gr.Accordion("Execution trace (plan JSON, step logs, usage)", open=False):
            trace_output = gr.Markdown(label="Trace")

        # --- Event handler ---
        def on_submit(
            user_id: str,
            request_text: str,
            use_memory: bool,
            reflect_rounds: int,
            mode: str,
        ) -> tuple[str, str, list[list[str]], str]:
            """Handle submit button click."""
            if not request_text.strip():
                return (
                    "⚠️ Please enter a request.",
                    "",
                    [],
                    "",
                )

            demo_request = DemoRequest(
                user_id=user_id.strip() if user_id.strip() else None,
                text=request_text.strip(),
                reflect_rounds=reflect_rounds,
                use_memory=use_memory,
                mode=mode,
            )

            result = backend.respond(demo_request)

            # Format status
            status_md = f"### {status_badge(result.status)}"
            if result.error:
                status_md += f"\n\n*{result.error}*"

            # Format items
            items_rows = format_items(result.items)

            # Format trace
            trace_md = format_trace(result.trace) if result.trace else "No execution trace"

            return status_md, result.text, items_rows, trace_md

        submit_btn.click(
            fn=on_submit,
            inputs=[user_id_input, request_input, memory_toggle, reflect_toggle, mode_radio],
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
        sample_user_dict = None
        print("MockBackend initialized (no data loading needed)")
    else:
        print("Mode: LIVE (LiveBackend)")
        print(f"Tag: {args.tag or '(default)'}")
        print(f"Domain: {args.domain or '(all)'}")
        print(f"Eval-on: {args.eval_on}")

        # Load config cho sample users
        sparse_max = load_config("eval/segment_thresholds")["segment_thresholds"]["sparse_max_history"]

        print("Initializing LiveBackend...")
        backend = LiveBackend(tag=args.tag, domain=args.domain)
        try:
            backend.initialize()
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
            print("    PYTHONPATH=. python scripts/run_demo.py --mock")
            sys.exit(1)

        print("Getting sample users...")
        sample_user_dict = backend.get_sample_users(n_per_segment=3, sparse_max=sparse_max)

    init_elapsed = time.time() - start_time
    print(f"\nStartup time: {init_elapsed:.1f}s")

    print("\nBuilding Gradio UI...")
    demo = build_ui(backend, args.mock, sample_user_dict)

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
