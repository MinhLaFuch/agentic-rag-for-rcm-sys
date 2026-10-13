"""Tests for the small evaluation utilities: merge_model_params, hardware_info, select_fit_target, grids, saving."""

import json

import pandas as pd
import pytest
import yaml

from package.tools.evaluation import (
    merge_model_params, next_experiment_dir, parameter_grid, save_experiment, select_fit_target,
)
from package.tools.evaluation.hardware_info import hardware_info


# ---------------------------------------------------------------- merge_model_params
def test_merge_overrides_and_adds_parameters():
    base = {"seed": 42, "item_knn": {"k": 20, "block_elements": 100}}
    merged = merge_model_params(base, "item_knn", {"k": 5, "extra": True})
    assert merged == {"seed": 42, "item_knn": {"k": 5, "block_elements": 100, "extra": True}}


def test_merge_missing_model_key_creates_it_and_empty_params_is_a_copy():
    base = {"seed": 1}
    assert merge_model_params(base, "bpr_mf", {"epochs": 2}) == {"seed": 1, "bpr_mf": {"epochs": 2}}
    same = merge_model_params({"a": {"x": 1}}, "a", {})
    assert same == {"a": {"x": 1}}


def test_merge_does_not_mutate_the_base_config():
    base = {"item_knn": {"k": 20}, "other": {"x": [1]}}
    merge_model_params(base, "item_knn", {"k": 5})
    merge_model_params(base, "new_model", {"p": 1})
    assert base == {"item_knn": {"k": 20}, "other": {"x": [1]}}


def test_merge_is_shallow_other_models_and_param_values_are_shared():
    """Documented limitation: only the overridden model's dict is rebuilt. Other models' dicts - and the *values*
    inside params - are shared with the base, so mutating them through the merged config mutates the base."""
    shared_list = [1, 2]
    base = {"other": {"x": [1]}, "m": {}}
    merged = merge_model_params(base, "m", {"values": shared_list})
    assert merged["other"] is base["other"] and merged["m"]["values"] is shared_list
    merged["other"]["x"].append(2)
    assert base["other"]["x"] == [1, 2]
    assert merged["m"] is not base["m"]  # the overridden model's own dict is a fresh object


# ---------------------------------------------------------------- hardware_info
def test_hardware_info_fields_are_serialisable():
    import platform

    info = hardware_info()
    assert set(info) == {"platform", "python", "cpu_count"}
    assert info["python"] == platform.python_version() and isinstance(info["platform"], str)
    assert info["cpu_count"] is None or (isinstance(info["cpu_count"], int) and info["cpu_count"] > 0)
    assert json.loads(json.dumps(info)) == info
    yaml.safe_dump(info)


def test_hardware_info_survives_unavailable_cpu_count(monkeypatch):
    monkeypatch.setattr("os.cpu_count", lambda: None)
    assert hardware_info()["cpu_count"] is None


def test_hardware_info_alone_does_not_pin_library_versions():
    """Reproducibility caveat: nothing about numpy/scipy/pandas/BLAS/GPU is recorded here."""
    assert not {"numpy", "scipy", "pandas", "gpu", "memory"} & set(hardware_info())


# ---------------------------------------------------------------- select_fit_target
def _frames():
    mk = lambda tag, n: pd.DataFrame({"user_idx": [0] * n, "item_idx": range(n), "split": tag})
    return mk("train", 3), mk("val", 2), mk("test", 1)


def test_validation_uses_train_to_fit_and_validation_as_target():
    train, val, test = _frames()
    fit, target = select_fit_target(train, val, test, "validation")
    assert set(fit["split"]) == {"train"} and set(target["split"]) == {"val"}


def test_test_uses_train_plus_validation_to_fit_and_never_leaks_test_into_fit():
    train, val, test = _frames()
    fit, target = select_fit_target(train, val, test, "test")
    assert set(fit["split"]) == {"train", "val"} and len(fit) == 5 and set(target["split"]) == {"test"}
    assert fit.index.is_unique  # concatenated with a fresh index


@pytest.mark.parametrize("bad", ["", "val", "TEST", None])
def test_select_fit_target_rejects_unknown_mode(bad):
    with pytest.raises(ValueError, match="eval_on"):
        select_fit_target(*_frames(), bad)


# ---------------------------------------------------------------- parameter_grid
def test_parameter_grid_expansion_order():
    assert parameter_grid({"a": [1, 2], "b": ["x"]}) == [{"a": 1, "b": "x"}, {"a": 2, "b": "x"}]
    assert parameter_grid({}) == [{}]


@pytest.mark.parametrize("bad, exc", [({"a": []}, ValueError), ({"a": 1}, TypeError), ({"a": (1, 2)}, TypeError), ([("a", [1])], TypeError)])
def test_parameter_grid_validation(bad, exc):
    with pytest.raises(exc):
        parameter_grid(bad)


# ---------------------------------------------------------------- experiment directories
def test_next_experiment_dir_counts_up_and_ignores_unrelated_names(tmp_path):
    assert next_experiment_dir(tmp_path).name == "exp_001"
    (tmp_path / "exp_001").mkdir()
    (tmp_path / "exp_007").mkdir()
    (tmp_path / "exp_x").mkdir()
    (tmp_path / "exp_").mkdir()
    (tmp_path / "exp_003.txt").write_text("not a dir")
    assert next_experiment_dir(tmp_path).name == "exp_008"


def test_save_experiment_writes_files_and_refuses_to_overwrite(tmp_path):
    out = save_experiment(
        tmp_path / "exp_001", config={"k": 5}, metrics={"overall": {"recall@3": 0.5}}, seed=7,
        dataset_info={"users": 6}, runtime_seconds=1.2345, notes="hello",
    )
    assert sorted(p.name for p in out.iterdir()) == ["README.md", "config.yaml", "metrics.json"]
    assert json.loads((out / "metrics.json").read_text()) == {"overall": {"recall@3": 0.5}}
    cfg = yaml.safe_load((out / "config.yaml").read_text())
    assert cfg["config"] == {"k": 5} and cfg["run"]["seed"] == 7 and cfg["run"]["runtime_seconds"] == 1.23
    assert set(cfg["run"]["hardware"]) == {"platform", "python", "cpu_count"}
    with pytest.raises(FileExistsError):
        save_experiment(out, config={}, metrics={}, seed=1, dataset_info={}, runtime_seconds=0)
