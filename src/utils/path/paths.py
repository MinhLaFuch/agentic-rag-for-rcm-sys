from __future__ import annotations

import os
from pathlib import Path

from .config import (
    DEFAULT_WORKSPACE,
    RESOURCE_DIR_ENV_VAR,
    SHARED_RESOURCE_NAMES,
    WORKSPACE_ENV_VAR,
)
from .find_root import find_repo_root


def resource_dir(*, start: str | Path = __file__) -> Path:
    """
    Host `resource/` folder: shared `raw/` plus workspaces.

    Always the host repo (pyproject.toml), not a forked submodule checkout.
    Set LOCAL_PACKAGE_RESOURCE_DIR to override the whole path.

    Usage:
        resource_dir()
        # -> agentic-rag-for-rcm-sys/resource

    You rarely call this directly - the other functions below call it
    internally to build their paths.
    """
    override = os.getenv(RESOURCE_DIR_ENV_VAR)
    if override:
        return Path(override)

    start_path = Path(start).resolve()
    root = find_repo_root(start_path)
    if root is None:
        raise FileNotFoundError(f"Could not find pyproject.toml above {start}")
    return root / "resource"


def resolve_workspace(workspace: str | None = None) -> str:
    """
    Which folder under `resource/` receives logs and exports.

    There is no auto-detect / fallback to a forked repo. Order:
      1. explicit `workspace` argument ("local" or "recai")
      2. LOCAL_PACKAGE_WORKSPACE env var
      3. "local" (this repo)

    Usage:
        resolve_workspace("local")   # -> "local"
        resolve_workspace("recai")   # -> "recai"
        resolve_workspace(None)      # -> "local" (DEFAULT_WORKSPACE)
        resolve_workspace("raw")     # -> raises ValueError, "raw" is shared, not a workspace
        resolve_workspace("a/b")     # -> raises ValueError, no nested paths allowed

    Internal helper - the `*_dir` functions below call this to validate the
    workspace name before building a path with it. You rarely call it directly.
    """
    raw = workspace if workspace is not None else os.getenv(WORKSPACE_ENV_VAR)
    name = (raw or DEFAULT_WORKSPACE).strip()
    if not name or name in SHARED_RESOURCE_NAMES or Path(name).name != name:
        raise ValueError(
            "workspace must be a single folder under resource/ besides 'raw' "
            f"(e.g. 'local' or 'recai'), got {name!r}"
        )
    return name


def workspace_dir(workspace: str | None = None, *, start: str | Path = __file__) -> Path:
    """
    `resource/local` or `resource/recai` - same layout (log/, processed/).

    Usage:
        workspace_dir("local")
        # -> resource/local

        workspace_dir("recai")
        # -> resource/recai

        workspace_dir()
        # -> resource/local   (no argument -> DEFAULT_WORKSPACE)

    Base for processed_dir/checkpoint_dir/log_dir below. Call it directly
    only when you need a workspace's root and don't care which subfolder.
    """
    return resource_dir(start=start) / resolve_workspace(workspace)


def raw_dir(dataset: str | None = None, *, start: str | Path = __file__) -> Path:
    """
    `resource/raw` or `resource/raw/<dataset>`. Shared, no workspace.

    Omit dataset to get the shared raw root; pass it for one category's
    raw folder.

    Usage:
        raw_dir()
        # -> resource/raw
        import os
        categories = os.listdir(raw_dir())
        # ['All_Beauty', 'Amazon_Fashion']

        raw_dir("All_Beauty")
        # -> resource/raw/All_Beauty

        raw_dir("Amazon_Fashion")
        # -> resource/raw/Amazon_Fashion

        path = raw_dir("All_Beauty")
        df = pd.read_json(path / "All_Beauty.jsonl.gz", lines=True, compression="gzip")

    No `workspace` parameter - raw data is shared across every workspace,
    there's only ever one copy on disk.
    """
    root = resource_dir(start=start) / "raw"
    return root / dataset if dataset else root


def processed_dir(
    workspace: str | None = None,
    dataset: str | None = None,
    *,
    start: str | Path = __file__,
) -> Path:
    """
    `resource/<workspace>/processed` or `resource/<workspace>/processed/<dataset>`.

    workspace is "local" or "recai".
    Omit dataset for one shared output folder; pass it for one category's
    own processed folder.

    Usage:
        processed_dir("local")
        # -> resource/local/processed          (root, no dataset)

        out = processed_dir("local")
        out.mkdir(parents=True, exist_ok=True)
        merged_df.to_csv(out / "all_categories_merged.csv", index=False)

        processed_dir("local", "All_Beauty")
        # -> resource/local/processed/All_Beauty

        processed_dir("recai", "Amazon_Fashion")
        # -> resource/recai/processed/Amazon_Fashion

        for cat in ["All_Beauty", "Amazon_Fashion"]:
            out = processed_dir("local", cat)
            out.mkdir(parents=True, exist_ok=True)
            process(cat).to_csv(out / "reviews.csv", index=False)

    Same argument order as checkpoint_dir/log_dir: workspace first, then
    the more specific identifier (dataset/folder_name) second.
    """
    root = workspace_dir(workspace, start=start) / "processed"
    return root / dataset if dataset else root


def checkpoint_dir(
    workspace: str | None = None,
    dataset: str | None = None,
    *,
    start: str | Path = __file__,
) -> Path:
    """
    `resource/<workspace>/checkpoint` or `resource/<workspace>/checkpoint/<dataset>`.

    workspace is "local" or "recai".
    Omit dataset for one shared checkpoint folder; pass it to keep a
    category's checkpoints separate (useful if you train one model per
    category instead of one model over everything).

    Usage:
        checkpoint_dir("local")
        # -> resource/local/checkpoint          (root, no dataset)

        ckpt = checkpoint_dir("recai")
        ckpt.mkdir(parents=True, exist_ok=True)
        torch.save(model.state_dict(), ckpt / "epoch_10.pt")

        checkpoint_dir("local", "All_Beauty")
        # -> resource/local/checkpoint/All_Beauty

        ckpt = checkpoint_dir("local", "All_Beauty")
        ckpt.mkdir(parents=True, exist_ok=True)
        torch.save(model.state_dict(), ckpt / "epoch_10.pt")

    Same argument order as processed_dir/log_dir: workspace first, then
    the more specific identifier (dataset/folder_name) second.
    """
    root = workspace_dir(workspace, start=start) / "checkpoint"
    return root / dataset if dataset else root


def log_dir(
    workspace: str | None = None,
    folder_name: str | None = None,
    *,
    start: str | Path = __file__,
) -> Path:
    """
    `resource/<workspace>/log` or `resource/<workspace>/log/<folder_name>`.

    workspace is "local" or "recai".
    folder_name is purpose ("process", "pipeline", "crawler"). Omit it to
    get the workspace's log root directly.

    Usage:
        log_dir("local")
        # -> resource/local/log            (root, no folder_name)

        log_dir("local", "process")
        # -> resource/local/log/process

        log_dir("recai", "pipeline")
        # -> resource/recai/log/pipeline

        log_dir("local", "crawler")
        # -> resource/local/log/crawler

        d = log_dir("local", "process")
        d.mkdir(parents=True, exist_ok=True)
        logger = setup_logging("process", log_file=d / "run.log")

    Same argument order as processed_dir/checkpoint_dir: workspace first,
    then the more specific identifier (folder_name/dataset) second.
    raw_dir is the one exception - it has no workspace param at all, since
    raw data is shared across every workspace.
    """
    root = workspace_dir(workspace, start=start) / "log"
    return root / folder_name if folder_name else root