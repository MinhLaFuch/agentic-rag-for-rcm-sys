"""Phase 4.5: benchmark result provenance — hashes, never raw secrets."""

from package.evaluation.component.run_benchmark_cli import (
    _build_provenance,
    _config_hash,
    _scrub_secrets,
)


def test_scrub_secrets_redacts_secret_looking_keys():
    obj = {"api_key": "sk-live-123", "model": "gpt-x", "nested": {"auth_token": "t", "ok": 1}}
    scrubbed = _scrub_secrets(obj)
    assert scrubbed["api_key"] == "<redacted>"
    assert scrubbed["model"] == "gpt-x"
    assert scrubbed["nested"]["auth_token"] == "<redacted>"
    assert scrubbed["nested"]["ok"] == 1


def test_config_hash_is_stable_and_secret_independent():
    a = {"model": "m", "api_key": "key-A"}
    b = {"model": "m", "api_key": "key-B"}
    # Same non-secret content → same hash even though raw keys differ
    assert _config_hash(a) == _config_hash(b)
    assert _config_hash({"model": "other"}) != _config_hash(a)


def test_provenance_never_contains_raw_secrets():
    prov = _build_provenance("executor", {"api_key": "sk-should-not-appear"}, "ds.jsonl")
    import json
    blob = json.dumps(prov)
    assert "sk-should-not-appear" not in blob
    assert "<redacted>" not in blob  # hashes only, no placeholders leaked either
    assert prov["evaluator_config_sha256"]


def test_provenance_includes_llm_for_planner():
    prov = _build_provenance("planner", {}, "planner_dataset.jsonl")
    assert "llm" in prov
    assert prov["llm"]["provider"] == "openai_compatible"
    assert "base_url_sha256" in prov["llm"]
    assert "config_sha256" in prov["llm"]


def test_provenance_includes_judge_for_grounding():
    prov = _build_provenance("grounding", {"use_jev": True}, "grounding_dataset.jsonl")
    assert "judge" in prov and "config_sha256" in prov["judge"]
