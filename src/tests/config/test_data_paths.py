import subprocess
import sys

from package.config import get_data_paths, get_domains, load_config
from package.config._constants import PROJECT_ROOT


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
    assert paths.split_path("train") == PROJECT_ROOT / "resource/splits/multi_domain/train.parquet"


def test_logs_and_experiments_are_separate_semantic_dirs():
    paths = get_data_paths()
    assert paths.log_dir == PROJECT_ROOT / "resource/logs/multi_domain"  # pipeline/tool logs
    assert paths.experiments_dir == PROJECT_ROOT / "experiments"  # experiment artifacts
    assert paths.log_dir != paths.experiments_dir
    assert PROJECT_ROOT / "tests" / "logs" not in (paths.log_dir, paths.experiments_dir)  # test logs are not configured here


def test_tag_only_changes_per_run_dirs():
    paths = get_data_paths("vg_toys")
    assert paths.splits_dir.name == "vg_toys"
    assert paths.filtered_dir.name == "vg_toys"
    assert paths.log_dir.name == "vg_toys"
    assert paths.cleaned_dir == get_data_paths().cleaned_dir  # stage 1 không phụ thuộc tag
    assert paths.experiments_dir == get_data_paths().experiments_dir  # experiment numbering is global


def test_config_cli_prints_values_for_shell_scripts():
    def run(*args):
        out = subprocess.run(
            [sys.executable, "-m", "package.config", *args], capture_output=True, text=True, cwd=PROJECT_ROOT
        )
        return out.returncode, out.stdout.split()

    assert run("domains.domains") == (0, get_domains())
    assert run("run_tag.tag") == (0, [load_config("path/run_tag")["tag"]])
    assert run("data_paths.paths.raw_dir") == (0, ["resource/raw"])
    assert run("data_paths.does_not_exist")[0] != 0


def test_config_cli_resolves_paths_from_datapaths_for_shell_scripts():
    def run(*args):
        out = subprocess.run(
            [sys.executable, "-m", "package.config", *args], capture_output=True, text=True, cwd=PROJECT_ROOT
        )
        return out.returncode, out.stdout.split()

    assert run("path:raw_dir") == (0, ["resource/raw"])
    assert run("path:filtered_path") == (0, ["resource/filtered/multi_domain/interactions.parquet"])
    assert run("--tag", "vg_toys", "path:splits_dir") == (0, ["resource/splits/vg_toys"])
    assert run("--tag", "vg_toys", "path:log_dir") == (0, ["resource/logs/vg_toys"])
    assert run("path:experiments_dir") == (0, ["experiments"])
    assert run("path:review_path:Video_Games") == (0, ["resource/raw/Video_Games.jsonl.gz"])
    assert run("path:meta_path:Video_Games") == (0, ["resource/raw/meta_Video_Games.jsonl.gz"])
    assert run("path:cleaned_path:Electronics") == (0, ["resource/cleaned/Electronics/interactions.parquet"])
    assert run("--tag", "t", "path:split_path:train") == (0, ["resource/splits/t/train.parquet"])
    # shell and Python must agree: the CLI is just a view of DataPaths
    assert run("path:split_path:test") == (0, [get_data_paths().split_path("test").relative_to(PROJECT_ROOT).as_posix()])
    assert run("path:nope")[0] != 0
    assert run("path:cleaned_path")[0] != 0  # needs an argument
    assert run("path:raw_dir:oops")[0] != 0  # takes none
    assert run("path:split_path:validation_typo")[0] != 0
