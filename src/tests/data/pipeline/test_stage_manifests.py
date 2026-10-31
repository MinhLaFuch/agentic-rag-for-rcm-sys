from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import pandas as pd

from package.config import DataPaths
from package.data.pipeline import clean_domain, merge_filter_domains
from package.data.manifest import verify_tag_manifest
from package.data.manifest.write_manifest import write_manifest
from package.data.manifest.verify_manifest import verify_manifest


def _paths(root: Path) -> DataPaths:
    return DataPaths(
        tag="synthetic", raw_dir=root / "raw", cleaned_dir=root / "cleaned",
        filtered_dir=root / "filtered", mapped_dir=root / "mapped", splits_dir=root / "splits",
        item_knn_dir=root / "item_knn", corpus_dir=root / "corpus", log_dir=root / "logs",
        experiments_dir=root / "experiments",
    )


def _write_reviews(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '{"user_id":"u1","parent_asin":"i1","rating":5,"timestamp":900000000000}\n'
        '{"user_id":"u2","parent_asin":"i2","rating":4,"timestamp":900000000001}\n',
        encoding="utf-8",
    )


def test_manifest_content_hashes_repeat_for_same_stage_outputs(tmp_path: Path):
    paths = _paths(tmp_path)
    source = tmp_path / "raw" / "reviews.jsonl"
    _write_reviews(source)
    clean_domain(paths, "DomainA", review_path=source, chunk_size=1, force=True)
    manifest = paths.cleaned_path("DomainA").parent / "stage_1.manifest.json"
    first = verify_manifest(manifest, project_root=Path(__file__).resolve().parents[3])
    clean_domain(paths, "DomainA", review_path=source, chunk_size=1, force=True)
    second = verify_manifest(manifest, project_root=Path(__file__).resolve().parents[3])
    assert first["manifest"]["outputs"] == second["manifest"]["outputs"]
    assert first["manifest"]["inputs"] == second["manifest"]["inputs"]


def test_changed_input_is_rejected_with_path_and_hashes(tmp_path: Path):
    paths = _paths(tmp_path)
    source = tmp_path / "raw" / "reviews.jsonl"
    _write_reviews(source)
    clean_domain(paths, "DomainA", review_path=source, chunk_size=1, force=True)
    output = paths.cleaned_path("DomainA")
    payload = bytearray(output.read_bytes())
    payload[-1] ^= 1
    output.write_bytes(payload)
    with pytest.raises(ValueError, match="interactions.parquet") as exc_info:
        merge_filter_domains(paths, ["DomainA"], force=True)
    assert "expected=" in str(exc_info.value)
    assert "actual=" in str(exc_info.value)


def test_allow_manifest_mismatch_records_warning_in_following_stage(tmp_path: Path):
    paths = _paths(tmp_path)
    source = tmp_path / "raw" / "reviews.jsonl"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("".join(
        json.dumps({"user_id": f"u{u}", "parent_asin": f"i{i}", "rating": 5, "timestamp": 900000000000 + u * 10 + i}) + "\n"
        for u in range(5) for i in range(5)
    ), encoding="utf-8")
    clean_domain(paths, "DomainA", review_path=source, chunk_size=7, force=True)
    output = paths.cleaned_path("DomainA")
    frame = pd.read_parquet(output)
    frame.loc[0, "rating"] = 4
    frame.to_parquet(output, index=False)
    with pytest.raises(ValueError, match="expected=.*actual="):
        merge_filter_domains(paths, ["DomainA"])
    merge_filter_domains(paths, ["DomainA"], allow_manifest_mismatch=True)
    stage2 = paths.filtered_path.parent / "stage_2.manifest.json"
    warnings = json.loads(stage2.read_text(encoding="utf-8"))["warnings"]
    assert any("expected=" in warning and "actual=" in warning for warning in warnings)


def test_manifest_contains_no_absolute_paths(tmp_path: Path):
    paths = _paths(tmp_path)
    source = tmp_path / "raw" / "reviews.jsonl"
    _write_reviews(source)
    clean_domain(paths, "DomainA", review_path=source, chunk_size=1, force=True)
    manifest = paths.cleaned_path("DomainA").parent / "stage_1.manifest.json"
    payload = manifest.read_text(encoding="utf-8")
    parsed = json.loads(payload)
    assert str(tmp_path) not in payload
    assert all(not Path(entry["path"]).is_absolute() for entry in parsed["inputs"] + parsed["outputs"])
    assert all(not Path(path).is_absolute() for path in parsed["config_sha256"])
    assert "D:" not in payload and "C:" not in payload


def test_stage1_manifests_coexist_for_multiple_tags(tmp_path: Path):
    source = tmp_path / "raw" / "reviews.jsonl"
    _write_reviews(source)
    first = _paths(tmp_path)
    clean_domain(first, "DomainA", review_path=source, chunk_size=1, force=True)
    first_manifest = first.stage1_manifest_path("DomainA")
    first_result = verify_manifest(first_manifest, project_root=Path(__file__).resolve().parents[3])

    second = DataPaths(**{**first.__dict__, "tag": "synthetic_v2"})
    clean_domain(second, "DomainA", review_path=source, chunk_size=1, force=True)
    second_manifest = second.stage1_manifest_path("DomainA")
    second_result = verify_manifest(second_manifest, project_root=Path(__file__).resolve().parents[3])
    first_result_after_second_run = verify_manifest(
        first_manifest, project_root=Path(__file__).resolve().parents[3]
    )

    assert first_manifest != second_manifest
    assert first_result["manifest"]["tag"] == first.tag
    assert second_result["manifest"]["tag"] == second.tag
    assert first_result["manifest"]["outputs"] == second_result["manifest"]["outputs"]
    assert first_result_after_second_run["status"] in {"match", "match_with_external_paths"}
    assert first_manifest.is_file() and second_manifest.is_file()


def test_stage1_manifest_lookup_prefers_tag_scoped_and_falls_back_for_legacy(tmp_path: Path):
    paths = _paths(tmp_path)
    clean_dir = paths.cleaned_path("DomainA").parent
    shared = clean_dir / "stage_1.manifest.json"
    assert paths.stage1_manifest_path("DomainA") == shared
    scoped = paths.stage1_manifest_path("DomainA", tag_scoped=True)
    scoped.parent.mkdir(parents=True)
    scoped.write_text("{}", encoding="utf-8")
    assert paths.stage1_manifest_path("DomainA") == scoped


def test_stage1_keeps_string_ids_last_duplicate_and_reports_diagnostics(tmp_path: Path):
    paths = _paths(tmp_path)
    source = tmp_path / "raw" / "reviews.jsonl"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(
        '{"user_id":"u1","parent_asin":"0486418189","rating":3,"timestamp":900000000000}\n'
        '{"user_id":"u1","parent_asin":"0486418189","rating":5,"timestamp":900000000000}\n'
        '{"user_id":"u1","parent_asin":"B000000001","rating":4,"timestamp":900000000000}\n',
        encoding="utf-8",
    )
    report = clean_domain(paths, "DomainA", review_path=source, chunk_size=1, force=True)
    output = pd.read_parquet(paths.cleaned_path("DomainA"))
    kept = output.loc[output["parent_asin"] == "0486418189", "rating"].item()
    assert kept == 5.0
    assert report["num_dropped_duplicates"] == 1
    assert report["num_dropped_invalid_rating"] == 0
    assert report["num_user_timestamp_multiple_items"] == 1
    assert report["num_events_in_user_timestamp_multi_item_groups"] == 2
    assert report["num_consecutive_same_user_item"] == 1
    assert set(output["parent_asin"]) == {"0486418189", "B000000001"}


def test_stage1_aborts_on_timestamp_unit_suspect_rate(tmp_path: Path):
    paths = _paths(tmp_path)
    source = tmp_path / "raw" / "reviews.jsonl"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(
        '{"user_id":"u1","parent_asin":"a","rating":5,"timestamp":1}\n'
        '{"user_id":"u2","parent_asin":"b","rating":5,"timestamp":900000000000}\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="possibly incorrect timestamp unit"):
        clean_domain(paths, "DomainA", review_path=source, chunk_size=1, force=True)
    assert not paths.cleaned_path("DomainA").exists()


def test_manifest_resolves_git_commit_from_dot_git_when_git_is_not_on_path(tmp_path: Path, monkeypatch):
    git_dir = tmp_path / ".git"
    ref = git_dir / "refs" / "heads" / "test-branch"
    ref.parent.mkdir(parents=True)
    commit = "3c7bb25b70077263213887ad4a924694ca017718"
    (git_dir / "HEAD").write_text("ref: refs/heads/test-branch\n", encoding="ascii")
    ref.write_text(commit + "\n", encoding="ascii")
    project_root = tmp_path / "src"
    project_root.mkdir()
    monkeypatch.setattr(subprocess, "check_output",
                        lambda *args, **kwargs: (_ for _ in ()).throw(FileNotFoundError("git unavailable")))

    manifest = write_manifest(project_root / "manifest.json", project_root=project_root, stage="test",
                              tag="synthetic", inputs=[], outputs=[], config_files=[], counts={}, flags={})

    assert manifest["git_commit"] == commit


def test_tag_without_any_stage_manifest_is_reported_as_legacy(tmp_path: Path):
    paths = _paths(tmp_path)
    result = verify_tag_manifest(paths, domains=["DomainA"], project_root=tmp_path)
    assert result["status"] == "legacy_unmanifested"
    assert result["manifest_sha256"] == "legacy_unmanifested"


def test_complete_tag_manifest_chain_hashes_and_verifies(tmp_path: Path):
    paths = _paths(tmp_path)

    def artifact(path: Path, content: bytes) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    clean = artifact(paths.cleaned_path("DomainA"), b"clean")
    stage1 = paths.stage1_manifest_path("DomainA", tag_scoped=True)
    write_manifest(stage1, project_root=tmp_path, stage="clean_domain", tag=paths.tag,
                   inputs=[], outputs=[clean], config_files=[], counts={}, flags={"domain": "DomainA"})

    filtered = artifact(paths.filtered_path, b"filtered")
    stage2 = paths.filtered_path.parent / "stage_2.manifest.json"
    write_manifest(stage2, project_root=tmp_path, stage="merge_filter_domains", tag=paths.tag,
                   inputs=[clean], outputs=[filtered], config_files=[], counts={}, flags={"domains": ["DomainA"]},
                   upstream_manifests=[stage1])

    user_map = artifact(paths.mapped_dir / "user2id.json", b"{}")
    item_map = artifact(paths.mapped_dir / "item2id.json", b"{}")
    splits = [artifact(paths.split_path(name), name.encode()) for name in ("train", "validation", "test")]
    stage3 = paths.splits_dir / "stage_3.manifest.json"
    write_manifest(stage3, project_root=tmp_path, stage="map_split", tag=paths.tag,
                   inputs=[filtered], outputs=[user_map, item_map, *splits], config_files=[], counts={}, flags={},
                   upstream_manifests=[stage2])

    corpus = artifact(paths.corpus_path, b"corpus")
    stage4 = paths.corpus_dir / "stage_4.manifest.json"
    write_manifest(stage4, project_root=tmp_path, stage="build_artifacts", tag=paths.tag,
                   inputs=[user_map, item_map, *splits], outputs=[corpus], config_files=[], counts={}, flags={},
                   upstream_manifests=[stage3])
    result = verify_tag_manifest(paths, domains=["DomainA"], project_root=tmp_path)
    assert result["status"] == "match"
    assert len(result["manifests"]) == 4
    assert len(result["manifest_sha256"]) == 64


def test_downstream_manifest_reuses_mapping_hash_from_upstream(tmp_path: Path, monkeypatch):
    paths = _paths(tmp_path)
    mapping = paths.mapped_dir / "user2id.json"
    mapping.parent.mkdir(parents=True)
    mapping.write_text('{"u":0}', encoding="utf-8")
    upstream = paths.splits_dir / "stage_3.manifest.json"
    write_manifest(upstream, project_root=tmp_path, stage="map_split", tag=paths.tag,
                   inputs=[], outputs=[mapping], config_files=[], counts={}, flags={})
    expected_hash = json.loads(upstream.read_text(encoding="utf-8"))["outputs"][0]["mapping_hash"]
    corpus = paths.corpus_dir / "corpus.sqlite"
    corpus.parent.mkdir(parents=True)
    corpus.write_bytes(b"corpus")

    original_read_text = Path.read_text

    def reject_mapping_parse(self, *args, **kwargs):
        if self.resolve() == mapping.resolve():
            raise AssertionError("downstream manifest reparsed the large mapping JSON")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", reject_mapping_parse)
    downstream = write_manifest(paths.corpus_dir / "stage_4.manifest.json", project_root=tmp_path,
                                stage="build_artifacts", tag=paths.tag, inputs=[mapping],
                                outputs=[corpus], config_files=[], counts={}, flags={},
                                upstream_manifests=[upstream])
    assert downstream["inputs"][0]["mapping_hash"] == expected_hash

