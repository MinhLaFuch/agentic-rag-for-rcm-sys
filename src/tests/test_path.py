import pytest

from package.utils.path import (
    DEFAULT_WORKSPACE,
    RESOURCE_DIR_ENV_VAR,
    SHARED_RESOURCE_NAMES,
    WORKSPACE_ENV_VAR,
    checkpoint_dir,
    find_repo_root,
    log_dir,
    processed_dir,
    raw_dir,
    resolve_workspace,
    resource_dir,
    workspace_dir,
)
from package.utils.path import paths as paths_module
from package.utils.path.generate_tree import _is_visible, generate_tree


@pytest.fixture
def synthetic_repo(tmp_path):
    """repo/pyproject.toml + repo/src/pkg/mod.py"""
    repo = tmp_path / "repo"
    module = repo / "src" / "pkg" / "mod.py"
    module.parent.mkdir(parents=True)
    (repo / "pyproject.toml").touch()
    module.touch()
    return repo, module


@pytest.fixture
def synthetic_tree(tmp_path):
    root = tmp_path / "tree"
    (root / "src" / "__pycache__").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / "src" / "a.py").touch()
    (root / "src" / "b.txt").touch()
    (root / "src" / "__pycache__" / "x.pyc").touch()
    (root / "docs" / "c.md").touch()
    (root / ".hidden").touch()
    (root / "README.md").touch()
    return root


# ------------------------------------------------------------ constants


def test_config_constants():
    assert DEFAULT_WORKSPACE == "local"
    assert "raw" in SHARED_RESOURCE_NAMES
    assert RESOURCE_DIR_ENV_VAR != WORKSPACE_ENV_VAR


# -------------------------------------------------------- find_repo_root


def test_find_repo_root_walks_up_from_nested_file(synthetic_repo):
    repo, module = synthetic_repo
    assert find_repo_root(module) == repo.resolve()


def test_find_repo_root_accepts_directory(synthetic_repo):
    repo, module = synthetic_repo
    assert find_repo_root(module.parent) == repo.resolve()


def test_find_repo_root_marker_in_same_directory(synthetic_repo):
    repo, _ = synthetic_repo
    assert find_repo_root(repo) == repo.resolve()
    assert find_repo_root(repo / "mod_next_to_marker.py") == repo.resolve()


def test_find_repo_root_nearest_marker_wins(synthetic_repo):
    repo, module = synthetic_repo
    (repo / "src" / "pyproject.toml").touch()
    assert find_repo_root(module) == (repo / "src").resolve()


def test_find_repo_root_custom_marker(synthetic_repo):
    repo, module = synthetic_repo
    (repo / "src" / "setup.cfg").touch()
    assert find_repo_root(module, marker="setup.cfg") == (repo / "src").resolve()


def test_find_repo_root_returns_none_when_marker_missing(tmp_path):
    assert find_repo_root(tmp_path, marker="__definitely_not_here__.toml") is None


# ---------------------------------------------------------- resource_dir


def test_resource_dir_env_override_wins(resource_root):
    assert resource_dir() == resource_root


def test_resource_dir_defaults_to_repo_resource_folder(synthetic_repo, monkeypatch):
    repo, module = synthetic_repo
    monkeypatch.delenv(RESOURCE_DIR_ENV_VAR, raising=False)
    assert resource_dir(start=module) == repo.resolve() / "resource"


def test_resource_dir_raises_when_no_repo_found(monkeypatch, tmp_path):
    monkeypatch.delenv(RESOURCE_DIR_ENV_VAR, raising=False)
    monkeypatch.setattr(paths_module, "find_repo_root", lambda *args, **kwargs: None)
    with pytest.raises(FileNotFoundError, match="pyproject.toml"):
        resource_dir(start=tmp_path)


# ------------------------------------------------------ resolve_workspace


def test_resolve_workspace_explicit_name(monkeypatch):
    monkeypatch.delenv(WORKSPACE_ENV_VAR, raising=False)
    assert resolve_workspace("recai") == "recai"


def test_resolve_workspace_defaults_to_local(monkeypatch):
    monkeypatch.delenv(WORKSPACE_ENV_VAR, raising=False)
    assert resolve_workspace(None) == DEFAULT_WORKSPACE


def test_resolve_workspace_uses_env_var_when_no_argument(monkeypatch):
    monkeypatch.setenv(WORKSPACE_ENV_VAR, "recai")
    assert resolve_workspace() == "recai"


def test_resolve_workspace_argument_beats_env_var(monkeypatch):
    monkeypatch.setenv(WORKSPACE_ENV_VAR, "recai")
    assert resolve_workspace("local") == "local"


def test_resolve_workspace_strips_whitespace(monkeypatch):
    monkeypatch.delenv(WORKSPACE_ENV_VAR, raising=False)
    assert resolve_workspace("  recai ") == "recai"


@pytest.mark.parametrize("bad", ["raw", "a/b", "   ", ".", ".."])
def test_resolve_workspace_rejects_invalid_names(bad):
    with pytest.raises(ValueError, match="workspace must be a single folder"):
        resolve_workspace(bad)


# ---------------------------------------- workspace_dir / raw_dir / *_dir


def test_workspace_dir_default_and_named(resource_root):
    assert workspace_dir() == resource_root / "local"
    assert workspace_dir("recai") == resource_root / "recai"


def test_workspace_dir_reads_env_var(resource_root, monkeypatch):
    monkeypatch.setenv(WORKSPACE_ENV_VAR, "recai")
    assert workspace_dir() == resource_root / "recai"


def test_raw_dir_root_and_dataset(resource_root):
    assert raw_dir() == resource_root / "raw"
    assert raw_dir("All_Beauty") == resource_root / "raw" / "All_Beauty"


def test_raw_dir_is_shared_across_workspaces(resource_root, monkeypatch):
    monkeypatch.setenv(WORKSPACE_ENV_VAR, "recai")
    assert raw_dir("All_Beauty") == resource_root / "raw" / "All_Beauty"


@pytest.mark.parametrize("func, subdir", [(processed_dir, "processed"), (checkpoint_dir, "checkpoint")])
def test_processed_and_checkpoint_dir_layout(resource_root, func, subdir):
    assert func() == resource_root / "local" / subdir
    assert func("recai") == resource_root / "recai" / subdir
    assert func("local", "All_Beauty") == resource_root / "local" / subdir / "All_Beauty"
    assert func("recai", "Amazon_Fashion") == resource_root / "recai" / subdir / "Amazon_Fashion"


def test_log_dir_layout(resource_root):
    assert log_dir() == resource_root / "local" / "log"
    assert log_dir("recai") == resource_root / "recai" / "log"
    assert log_dir("local", "process") == resource_root / "local" / "log" / "process"


@pytest.mark.parametrize("func", [workspace_dir, processed_dir, checkpoint_dir, log_dir])
def test_dir_helpers_reject_shared_raw_workspace(resource_root, func):
    with pytest.raises(ValueError):
        func("raw")


@pytest.mark.parametrize(
    "build",
    [
        lambda: raw_dir("All_Beauty"),
        lambda: processed_dir("local", "All_Beauty"),
        lambda: checkpoint_dir("local", "All_Beauty"),
        lambda: log_dir("local", "process"),
    ],
)
def test_dir_helpers_do_not_create_directories(resource_root, build):
    assert not build().exists()


# --------------------------------------------------------- generate_tree


def test_generate_tree_prints_dirs_first_and_hides_noise(synthetic_tree, capsys):
    generate_tree(synthetic_tree)
    assert capsys.readouterr().out.splitlines() == [
        ".",
        "├── docs",
        "│   └── c.md",
        "├── src",
        "│   ├── a.py",
        "│   └── b.txt",
        "└── README.md",
    ]


def test_generate_tree_show_hidden(synthetic_tree, capsys):
    generate_tree(synthetic_tree, show_hidden=True)
    out = capsys.readouterr().out.splitlines()
    assert out[-2:] == ["├── .hidden", "└── README.md"]


def test_generate_tree_exts_filter_keeps_only_matching_branches(synthetic_tree, capsys):
    generate_tree(synthetic_tree, exts={".py"})
    assert capsys.readouterr().out.splitlines() == [".", "└── src", "    └── a.py"]


def test_generate_tree_max_depth(synthetic_tree, capsys):
    generate_tree(synthetic_tree, max_depth=1)
    assert capsys.readouterr().out.splitlines() == [".", "├── docs", "├── src", "└── README.md"]


def test_generate_tree_non_directory_prints_only_root(tmp_path, capsys):
    generate_tree(tmp_path / "does_not_exist")
    assert capsys.readouterr().out.splitlines() == ["."]


def test_generate_tree_accepts_str_path(synthetic_tree, capsys):
    generate_tree(str(synthetic_tree), max_depth=1)
    assert "README.md" in capsys.readouterr().out


# ----------------------------------------------------------- _is_visible


def test_is_visible_ignore_list_and_hidden(synthetic_tree):
    assert not _is_visible(synthetic_tree / "src" / "__pycache__", None, True)
    assert not _is_visible(synthetic_tree / ".hidden", None, False)
    assert _is_visible(synthetic_tree / ".hidden", None, True)


def test_is_visible_file_extension_filter(synthetic_tree):
    assert _is_visible(synthetic_tree / "src" / "a.py", {".py"}, False)
    assert not _is_visible(synthetic_tree / "src" / "b.txt", {".py"}, False)


def test_is_visible_directory_needs_a_matching_child_when_filtering(synthetic_tree):
    assert _is_visible(synthetic_tree / "src", {".py"}, False)
    assert not _is_visible(synthetic_tree / "docs", {".py"}, False)
    assert _is_visible(synthetic_tree / "docs", None, False)