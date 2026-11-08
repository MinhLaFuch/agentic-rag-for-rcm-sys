from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path


class RankingRunStore:

    def __init__(self, directory, identity, *, resume=False):
        self.path = Path(directory)
        self.path.mkdir(parents=True, exist_ok=True)
        self._lock = (self.path / "writer.lock").open("a+b")
        self.conn = None
        self._counts = {}
        try:
            self._lock.seek(0, 2)
            if not self._lock.tell():
                self._lock.write(b"0")
                self._lock.flush()
            self._lock.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self._lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            db = self.path / "checkpoint.sqlite3"
            if db.exists() and not resume:
                raise ValueError("checkpoint exists; use --resume with identical protocol or a new --work-dir")
            if resume and not db.exists():
                raise ValueError("resume checkpoint does not exist")
            self.conn = sqlite3.connect(db)
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA synchronous=FULL")
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS records (
                    stream TEXT, position INTEGER, user_idx INTEGER, payload TEXT NOT NULL,
                    PRIMARY KEY(stream, position), UNIQUE(stream, user_idx));
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY, started REAL, seconds REAL, status TEXT);
            """)
            saved = self.get("identity")
            if saved is not None and saved != identity:
                raise ValueError("resume identity mismatch: code/environment/data/mappings/protocol/parameters changed")
            if saved is None:
                self.put("identity", identity)
            manifest = self.path / "run_manifest.json"
            if not manifest.exists():
                temporary = manifest.with_suffix(".json.partial")
                temporary.write_text(json.dumps({"format_version":1, "created_at_unix":time.time(), "identity":identity},
                                                 ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
                temporary.replace(manifest)
            self.started = time.perf_counter()
            with self.conn:
                cur = self.conn.execute("INSERT INTO sessions(started,seconds,status) VALUES (?,0,'running')", (time.time(),))
                self.session_id = cur.lastrowid
        except BaseException:
            if self.conn is not None:
                self.conn.close()
            self._lock.close()
            raise

    def get(self, key, default=None):
        row = self.conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def put(self, key, value):
        with self.conn:
            self.conn.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (key, json.dumps(value, ensure_ascii=False, allow_nan=False)))

    def count(self, stream):
        if stream not in self._counts:
            n, low, high = self.conn.execute("SELECT count(*), min(position), max(position) FROM records WHERE stream=?", (stream,)).fetchone()
            if n and (low != 0 or high != n-1):
                raise ValueError("checkpoint position prefix is corrupt")
            self._counts[stream] = n
        return self._counts[stream]

    def append(self, stream, batch):
        """Positions must form a prefix; duplicates and holes fail atomically."""
        if not batch:
            return
        start = self.count(stream)
        if [pos for pos, _ in batch] != list(range(start, start + len(batch))):
            raise ValueError("checkpoint batch must extend the committed position prefix")
        encoded = [(stream, pos, int(row["user_idx"]), json.dumps(row, ensure_ascii=False, allow_nan=False)) for pos, row in batch]
        with self.conn:
            self.conn.executemany("INSERT INTO records VALUES (?,?,?,?)", encoded)
            self.conn.execute("UPDATE sessions SET seconds=? WHERE id=?", (time.perf_counter() - self.started, self.session_id))

        self._counts[stream] = start + len(batch)

    def rows(self, stream, *, start=0, batch_size=100):
        """Keyset iteration remains safe while other streams are committed."""
        position = start
        while True:
            rows = self.conn.execute("SELECT position,payload FROM records WHERE stream=? AND position>=? ORDER BY position LIMIT ?",
                                     (stream, position, batch_size)).fetchall()
            if not rows:
                return
            for pos, payload in rows:
                yield pos, json.loads(payload)
            position = rows[-1][0] + 1

    def export(self, streams, destination):
        destination = Path(destination)
        temporary = destination.with_suffix(destination.suffix + ".partial")
        with temporary.open("w", encoding="utf-8", newline="\n") as out:
            for stream in streams:
                for _, row in self.rows(stream):
                    out.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
            out.flush()
            os.fsync(out.fileno())
        temporary.replace(destination)

    def timing(self):
        with self.conn:
            self.conn.execute("UPDATE sessions SET seconds=? WHERE id=?", (time.perf_counter() - self.started, self.session_id))
        rows = self.conn.execute("SELECT seconds,status FROM sessions ORDER BY id").fetchall()
        return {"sessions": [{"seconds": seconds, "status": status} for seconds,status in rows],
                "committed_active_seconds": sum(r[0] for r in rows),
                "interrupted_tail_timing": "hard kills may lose elapsed timing since last committed batch; downtime excluded"}

    def close(self, status="complete"):
        if self.conn is not None:
            try:
                with self.conn:
                    self.conn.execute("UPDATE sessions SET seconds=?,status=? WHERE id=?",
                                      (time.perf_counter() - self.started, status, self.session_id))
            finally:
                self.conn.close()
                self.conn = None
                self._lock.close()

    def __enter__(self):
        return self

    def __exit__(self, typ, value, traceback):
        self.close("interrupted" if typ else "complete")
