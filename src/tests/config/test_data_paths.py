import subprocess
import sys

from package.config import get_data_paths, get_domains, load_config
from package.config._config import PROJECT_ROOT


def test_get_domains_follows_data_yaml_order():
    assert get_domains() == ["Video_Games", "Toys_and_Games", "Electronics"]


def test_data_paths_layout_is_under_resource():
    paths = get_data_paths()
    assert paths.tag == "multi_domain"
    assert paths.raw_dir == PROJECT_ROOT / "resource" / "raw"
    assert paths.review_path("Video_Games") == paths.raw_dir / "Video_Games.jsonl.gz"
    assert paths.meta_path("Video_Games") == paths.raw_dir / "meta_Video_Games.jsonl.gz"
    assert paths.cleaned_path("Electronics") == PROJECT_ROOT / "resource/cleaned/Electronics/interactions.parquet"
    assert paths.filtered_path == PROJECT_ROOT / "resource/filtered/multi_domain/interactions.parquet"
    assert paths.mapped_dir == PROJECT_ROOT / "resource/mapped/multi_domain"
    assert paths.splits_dir == PROJECT_ROOT / "resource/splits/multi_domain"


def test_tag_only_changes_per_run_dirs():
    paths = get_data_paths("vg_toys")
    assert paths.splits_dir.name == "vg_toys"
    assert paths.filtered_dir.name == "vg_toys"
    assert paths.cleaned_dir == get_data_paths().cleaned_dir  # stage 1 không phụ thuộc tag


def test_config_cli_prints_values_for_shell_scripts():
    def run(key):
        out = subprocess.run(
            [sys.executable, "-m", "package.config", key], capture_output=True, text=True, cwd=PROJECT_ROOT
        )
        return out.returncode, out.stdout.split()

    assert run("data.domains") == (0, get_domains())
    assert run("data.run_tag") == (0, [load_config("data")["run_tag"]])
    assert run("data.paths.raw_dir") == (0, ["resource/raw"])
    assert run("data.does_not_exist")[0] != 0
