import json

import pytest

from package.tools.evaluation.ranking_run_store import RankingRunStore


def test_resume_atomic_prefix_and_export(tmp_path):
    directory = tmp_path / "work"
    with pytest.raises(RuntimeError):
        with RankingRunStore(directory, {"seed":42}) as store:
            store.append("candidates", [(0,{"user_idx":9}), (1,{"user_idx":7})])
            # Simulate a transaction killed between INSERT and commit.
            store.conn.execute("INSERT INTO records VALUES ('candidates',2,5,'{}')")
            store.conn.rollback()
            raise RuntimeError("interrupted")
    with RankingRunStore(directory, {"seed":42}, resume=True) as store:
        assert store.count("candidates") == 2
        store.append("candidates", [(2,{"user_idx":5})])
        store.export(["candidates"], tmp_path / "candidates.jsonl")
        assert [json.loads(s)["user_idx"] for s in (tmp_path/"candidates.jsonl").read_text().splitlines()] == [9,7,5]
        assert store.timing()["sessions"][0]["status"] == "interrupted"


def test_rejects_mismatch_duplicate_holes_and_concurrent_writer(tmp_path):
    directory = tmp_path / "work"
    with RankingRunStore(directory, {"protocol":"ascii"}) as store:
        with pytest.raises((OSError,BlockingIOError)):
            RankingRunStore(directory, {"protocol":"ascii"}, resume=True)
        with pytest.raises(ValueError,match="prefix"):
            store.append("candidates", [(1,{"user_idx":9})])
        store.append("candidates", [(0,{"user_idx":9})])
        with pytest.raises(Exception):
            store.append("candidates", [(1,{"user_idx":9})])
        assert store.count("candidates") == 1
    with pytest.raises(ValueError,match="identity mismatch"):
        RankingRunStore(directory, {"protocol":"raw"}, resume=True)
    with pytest.raises(ValueError,match="checkpoint exists"):
        RankingRunStore(directory, {"protocol":"ascii"})


def test_partial_export_does_not_replace_complete_file(tmp_path, monkeypatch):
    with RankingRunStore(tmp_path/"work", {}) as store:
        store.append("candidates",[(0,{"user_idx":1})])
        dest = tmp_path / "candidates.jsonl"
        dest.write_text("previous complete export")
        def fail(*a,**k):
            yield 0,{"user_idx":1}
            raise RuntimeError("disk interrupted")
        monkeypatch.setattr(store,"rows",fail)
        with pytest.raises(RuntimeError):
            store.export(["candidates"],dest)
        assert dest.read_text() == "previous complete export"
