"""D1 regression tests (Phase E): unified_report phải surface provenance thật.

ĐỎ cho tới khi Phase E implement:
- git_sha lấy từ metadata.git_sha khi top-level rỗng (run_benchmark_cli hiện
  không truyền git_sha vào run_benchmark -> top-level luôn "")
- metadata.provenance (llm/judge/dataset hashes) xuất hiện trong component entry
- provider_error_count được aggregate (đếm case có cờ provider_error),
  provider_error KHÔNG còn chỉ nằm trong file con
"""

from __future__ import annotations

import json

from package.evaluation.component import _run_all


def _write_result(path, *, git_sha="", metadata=None, provider_error_cases=0):
    per_case = [
        {
            "case_id": f"c{i}",
            "success": True,
            "metrics": {"m": 1.0},
            "latency_seconds": 0.01,
            **({"provider_error": True} if i < provider_error_cases else {}),
        }
        for i in range(3)
    ]
    payload = {
        "component": "x",
        "per_case_results": per_case,
        "metrics": {"m_mean": 1.0, "success_rate": 1.0},
        "git_sha": git_sha,
        "metadata": metadata or {},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def _info(result_file=None, *, error=None, not_implemented=False):
    return {"result_file": result_file, "error": error, "not_implemented": not_implemented}


def test_git_sha_falls_back_to_metadata(tmp_path):
    f = _write_result(
        tmp_path / "r.json",
        git_sha="",
        metadata={"git_sha": "deadbeef", "provenance": {"dataset_sha256": "x"}},
    )
    agg = _run_all.aggregate_results({"comp": _info(f)})
    assert agg["components"]["comp"]["git_sha"] == "deadbeef"


def test_provenance_surfaced_in_unified_report(tmp_path):
    f = _write_result(
        tmp_path / "r.json",
        metadata={
            "git_sha": "deadbeef",
            "provenance": {"llm": {"model": "gpt-5.4"}, "dataset_sha256": "abc"},
        },
    )
    agg = _run_all.aggregate_results({"comp": _info(f)})
    prov = agg["components"]["comp"].get("provenance")
    assert prov is not None
    assert prov["dataset_sha256"] == "abc"


def test_provider_error_count_aggregated(tmp_path):
    f = _write_result(tmp_path / "r.json", provider_error_cases=1)
    agg = _run_all.aggregate_results({"comp": _info(f)})
    comp = agg["components"]["comp"]
    assert comp.get("provider_error_count") == 1


def test_provider_error_count_zero_when_absent(tmp_path):
    f = _write_result(tmp_path / "r.json")
    agg = _run_all.aggregate_results({"comp": _info(f)})
    assert agg["components"]["comp"].get("provider_error_count") == 0
