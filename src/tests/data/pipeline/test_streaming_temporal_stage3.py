from __future__ import annotations

import json
import importlib
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from package.config import DataPaths, PROJECT_ROOT
from package.data.manifest.write_manifest import write_manifest
from package.data.pipeline.map_split import map_split
from package.tools.recommenders.mapping_hash import mapping_hash


def test_dictionary_batch_is_decoded_before_pandas_and_output(tmp_path: Path):
    from package.data.pipeline._streaming_temporal_stage3 import _batch_to_pandas

    categories = pa.array([f"user-{index:05d}" for index in range(20_000)])
    indices = pa.array([index % 3 for index in range(128)], type=pa.int32())
    dictionary = pa.DictionaryArray.from_arrays(indices, categories)
    source = tmp_path / "dictionary_input.parquet"
    pq.write_table(pa.table({"user_id": dictionary}), source)

    batch = next(pq.ParquetFile(source).iter_batches(batch_size=128))
    assert pa.types.is_dictionary(batch.schema.field("user_id").type)
    assert len(batch.column("user_id").dictionary) == 20_000

    frame = _batch_to_pandas(batch)
    assert not isinstance(frame["user_id"].dtype, pd.CategoricalDtype)
    assert frame["user_id"].tolist() == [f"user-{index % 3:05d}" for index in range(128)]

    output_table = pa.Table.from_pandas(frame, preserve_index=False)
    assert not pa.types.is_dictionary(output_table.schema.field("user_id").type)
    assert output_table.nbytes < batch.column("user_id").dictionary.nbytes // 10


def test_stage2_writer_does_not_repeat_file_wide_category_vocabularies(tmp_path: Path):
    from package.data.pipeline.merge_filter_domains import _write_filtered_parquet

    categories = [f"user-{index:05d}" for index in range(20_000)]
    values = [categories[index % 3] for index in range(128)]
    frame = pd.DataFrame({"user_id": pd.Categorical(values, categories=categories)})
    output = tmp_path / "filtered.parquet"

    _write_filtered_parquet(frame, output, row_group_size=32)

    parquet = pq.ParquetFile(output)
    assert parquet.metadata.num_rows == len(frame)
    assert parquet.metadata.num_row_groups == 4
    user_type = parquet.schema_arrow.field("user_id").type
    assert pa.types.is_string(user_type) or pa.types.is_large_string(user_type)
    category_bytes = pa.array(categories).nbytes
    stored_bytes = sum(parquet.metadata.row_group(i).column(0).total_uncompressed_size
                       for i in range(parquet.metadata.num_row_groups))
    assert stored_bytes < category_bytes // 10
    assert pq.read_table(output).column("user_id").to_pylist() == values


def test_streaming_temporal_stage3_keeps_cutoffs_pair_core_and_cold_cohort(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    paths = DataPaths(
        tag="streaming_synthetic",
        raw_dir=tmp_path / "raw",
        cleaned_dir=tmp_path / "cleaned",
        filtered_dir=tmp_path / "filtered" / "streaming_synthetic",
        mapped_dir=tmp_path / "mapped" / "streaming_synthetic",
        splits_dir=tmp_path / "splits" / "streaming_synthetic",
        item_knn_dir=tmp_path / "item_knn" / "streaming_synthetic",
        corpus_dir=tmp_path / "corpus" / "streaming_synthetic",
        log_dir=tmp_path / "logs" / "streaming_synthetic",
        experiments_dir=tmp_path / "experiments",
    )
    rows = pd.DataFrame(
        [
            ("u1", "D::i1", 5.0, 10, "D", "i1"),
            ("u1", "D::i2", 4.0, 20, "D", "i2"),
            ("u2", "D::i1", 5.0, 30, "D", "i1"),
            ("u2", "D::i2", 4.0, 40, "D", "i2"),
            ("u3", "D::i3", 3.0, 50, "D", "i3"),
            ("u3", "D::i3", 3.0, 60, "D", "i3"),
            ("u3", "D::i3", 3.0, 70, "D", "i3"),
            ("u1", "D::i3", 5.0, 150, "D", "i3"),
            ("u4", "D::i4", 5.0, 160, "D", "i4"),
            ("u1", "D::i2", 5.0, 250, "D", "i2"),
            ("u5", "D::i5", 5.0, 260, "D", "i5"),
        ],
        columns=["user_id", "parent_asin", "rating", "timestamp", "domain", "original_item_id"],
    )
    paths.filtered_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pandas(rows, preserve_index=False), paths.filtered_path)
    stage2_manifest = paths.filtered_path.parent / "stage_2.manifest.json"
    write_manifest(
        stage2_manifest,
        project_root=PROJECT_ROOT,
        stage="merge_filter_domains",
        tag=paths.tag,
        inputs=[],
        outputs=[paths.filtered_path],
        config_files=[],
        counts={"num_rows": len(rows)},
        flags={"legacy_kcore_before_split": False},
    )

    def fake_load_config(name: str):
        if name == "data/split":
            return {"split": {"train_ratio": 0.8, "validation_ratio": 0.1, "test_ratio": 0.1,
                               "temporal_train_core": {"train_end_inclusive_ms": 100,
                                                       "validation_end_inclusive_ms": 200}}}
        if name == "data/filtering":
            return {"filtering": {"min_user_interactions": 2, "min_item_interactions": 2}}
        if name == "eval/segment_thresholds":
            return {"segment_thresholds": {"sparse_max_history": 1}}
        raise AssertionError(f"unexpected config {name}")

    module = importlib.import_module("package.data.pipeline.map_split")
    monkeypatch.setattr(module, "load_config", fake_load_config)
    result = map_split(paths, data_protocol="temporal_train_core", scratch_dir=str(tmp_path / "scratch"))

    assert (result["train_rows"], result["val_rows"], result["test_rows"]) == (7, 2, 2)
    train = pd.read_parquet(paths.split_path("train"))
    val = pd.read_parquet(paths.split_path("validation"))
    test = pd.read_parquet(paths.split_path("test"))
    assert train.timestamp.max() <= 100
    assert val.timestamp.min() > 100 and val.timestamp.max() <= 200
    assert test.timestamp.min() > 200

    core = pd.read_parquet(paths.splits_dir / "train_core.parquet")
    assert len(core) == 4
    assert set(core.user_id) == {"u1", "u2"}
    assert set(core.parent_asin) == {"D::i1", "D::i2"}
    cohort = pd.read_parquet(paths.splits_dir / "evaluation_cohort.parquet")
    assert cohort.loc[cohort.user_id.eq("u4"), "segment"].item() == "cold"
    assert set(cohort.eval_on) == {"validation", "test"}

    user_map = json.loads((paths.mapped_dir / "user2id.json").read_text(encoding="utf-8"))
    item_map = json.loads((paths.mapped_dir / "item2id.json").read_text(encoding="utf-8"))
    manifest = json.loads((paths.splits_dir / "stage_3.manifest.json").read_text(encoding="utf-8"))
    records = {record["path"]: record for record in manifest["outputs"]}
    user_hashes = {record["mapping_hash"] for name, record in records.items()
                   if name.endswith("/user2id.json")}
    item_hashes = {record["mapping_hash"] for name, record in records.items()
                   if name.endswith("/item2id.json")}
    assert mapping_hash(user_map) in user_hashes
    assert mapping_hash(item_map) in item_hashes

    fit_core_path = paths.splits_dir / "train_core.parquet"
    fit_user_path = paths.mapped_dir / "fit_core" / "user2id.json"
    fit_item_path = paths.mapped_dir / "fit_core" / "item2id.json"
    fit_artifacts_before = (fit_core_path.read_bytes(), fit_user_path.read_bytes(), fit_item_path.read_bytes())

    changed_targets = rows.copy()
    changed_targets.loc[changed_targets.timestamp.eq(150), ["user_id", "parent_asin", "original_item_id"]] = [
        "future_user_a", "D::future_item_a", "future_item_a"
    ]
    changed_targets.loc[changed_targets.timestamp.eq(160), ["user_id", "parent_asin", "original_item_id"]] = [
        "future_user_b", "D::future_item_b", "future_item_b"
    ]
    changed_targets.loc[changed_targets.timestamp.eq(250), ["user_id", "parent_asin", "original_item_id"]] = [
        "future_user_c", "D::future_item_c", "future_item_c"
    ]
    changed_targets.loc[changed_targets.timestamp.eq(260), ["user_id", "parent_asin", "original_item_id"]] = [
        "future_user_d", "D::future_item_d", "future_item_d"
    ]
    pq.write_table(pa.Table.from_pandas(changed_targets, preserve_index=False), paths.filtered_path)
    write_manifest(
        stage2_manifest,
        project_root=PROJECT_ROOT,
        stage="merge_filter_domains",
        tag=paths.tag,
        inputs=[],
        outputs=[paths.filtered_path],
        config_files=[],
        counts={"num_rows": len(changed_targets)},
        flags={"legacy_kcore_before_split": False},
    )
    map_split(paths, data_protocol="temporal_train_core", scratch_dir=str(tmp_path / "scratch"), force=True)
    fit_artifacts_after = (fit_core_path.read_bytes(), fit_user_path.read_bytes(), fit_item_path.read_bytes())
    assert fit_artifacts_after == fit_artifacts_before
