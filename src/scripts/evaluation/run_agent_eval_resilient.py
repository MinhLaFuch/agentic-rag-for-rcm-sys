"""Resilient wrapper for run_agent_eval.py — auto-resume on transient failures.

The eval aborts after 5 consecutive LLM errors (HTTP 5xx gateway flakiness is
common on reseller endpoints). Trajectories are appended per-request, so a
simple retry with --resume continues where it stopped. This wrapper loops
until the run exits 0 or --max-attempts is hit, with a fixed backoff between
attempts so a dead gateway doesn't burn retries instantly.

Usage (same env vars as run_agent_eval.py):

    PYTHONPATH=. CONFIG_OVERLAY_PATH="..." LLM_API_KEY=... \
        .venv/Scripts/python scripts/evaluation/run_agent_eval_resilient.py \
        --eval-on validation            # add --resume to continue an old run

Extra args: --max-attempts N (default 8), --backoff-seconds S (default 120).
All other args are forwarded to run_agent_eval.py verbatim.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

SRC = Path(__file__).resolve().parents[2]
TARGET = SRC / "scripts" / "evaluation" / "run_agent_eval.py"


def main() -> int:
    # Child output contains non-ASCII request text; cp1252 consoles crash on print.
    if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max-attempts", type=int, default=8)
    ap.add_argument("--backoff-seconds", type=float, default=120.0)
    ap.add_argument("forwarded", nargs=argparse.REMAINDER,
                    help="args forwarded to run_agent_eval.py")
    args = ap.parse_args()

    fwd = list(args.forwarded)
    if fwd and fwd[0] == "--":
        fwd = fwd[1:]

    env = dict(**__import__("os").environ)
    env.setdefault("PYTHONPATH", str(SRC))

    # Deterministic failures that retrying can never fix — abort immediately
    # instead of burning attempts (e.g. protocol-hash mismatch on --resume
    # after a code change invalidates the partial trajectory log).
    FATAL_MARKERS = (
        "protocol mismatch", "Trajectory already exists",
        "must be a simple .jsonl filename", "Schema",
    )

    for attempt in range(1, args.max_attempts + 1):
        cmd = [sys.executable, str(TARGET), *fwd]
        if attempt > 1 and "--resume" not in fwd:
            cmd.append("--resume")
        print(f"[resilient] attempt {attempt}/{args.max_attempts}: {' '.join(cmd)}",
              flush=True)
        proc = subprocess.run(cmd, cwd=SRC, env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, encoding="utf-8", errors="replace")
        tail = proc.stdout[-4000:] if proc.stdout else ""
        if tail.strip():
            print(tail, flush=True)
        if proc.returncode == 0:
            print("[resilient] run completed successfully", flush=True)
            return 0
        lowered = (proc.stdout or "").lower()
        if any(m.lower() in lowered for m in FATAL_MARKERS):
            print("[resilient] deterministic failure — not retrying", flush=True)
            return proc.returncode
        if attempt < args.max_attempts:
            print(f"[resilient] exit={proc.returncode}; retrying in "
                  f"{args.backoff_seconds:.0f}s", flush=True)
            time.sleep(args.backoff_seconds)
    print(f"[resilient] gave up after {args.max_attempts} attempts", flush=True)
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
