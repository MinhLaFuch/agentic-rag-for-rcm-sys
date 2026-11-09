from __future__ import annotations

import time


class StageProgress:
    def __init__(self, stage, total, *, completed=0, every=100):
        self.stage, self.total, self.initial, self.every = stage, total, completed, every
        self.started = time.perf_counter()
        self.last = completed
        self.update(completed, force=True)

    def update(self, completed, *, force=False):
        if not force and completed - self.last < self.every and completed != self.total:
            return
        elapsed = time.perf_counter() - self.started
        rate = (completed - self.initial) / elapsed if elapsed else 0
        eta = 0. if completed >= self.total else ((self.total - completed) / rate if rate > 0 else None)
        remaining = f"{eta:.0f}s" if eta is not None else "unknown (warming up/resumed)"
        print(f"[{self.stage}] committed={completed}/{self.total} rate={rate:.2f} users/s ETA={remaining}", flush=True)
        self.last = completed
