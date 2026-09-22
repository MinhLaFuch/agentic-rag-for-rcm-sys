from __future__ import annotations

import os
from pathlib import Path

from ._find_root import find_repo_root
from ._submodule import submodule_name

RESOURCE_DIR_ENV_VAR = "LOCAL_PACKAGE_RESOURCE_DIR"


def resource_dir(start: str | Path = __file__) -> Path:
    """
    Where `resource/` lives for the repo `start` runs in.

    - Inside a forked-repo submodule (`forked_repository/<name>/...`, declared in the
      host's `.gitmodules`): `host_root/resource/<name>` — so every forked repo's
      output lands under the host, namespaced by its own folder name, instead of
      scattered across each submodule's own checkout.
    - Inside the host repo itself: `host_root/resource`.
    - No `.gitmodules` found anywhere above `start` (repo checked out standalone, no
      host around it): falls back to that repo's own `pyproject.toml` root.

    Set LOCAL_PACKAGE_RESOURCE_DIR to override outright (e.g. this package vendored as
    a submodule with no pyproject.toml of its own, where root detection can't tell it
    apart from the host repo).
    """
    override = os.getenv(RESOURCE_DIR_ENV_VAR)
    if override:
        return Path(override)

    start_path = Path(start).resolve()

    host_root = find_repo_root(start_path, marker=".gitmodules")
    if host_root is not None:
        name = submodule_name(host_root, start_path)
        return host_root / "resource" / name if name else host_root / "resource"

    root = find_repo_root(start_path)
    if root is None:
        raise FileNotFoundError(f"Could not find pyproject.toml above {start}")
    return root / "resource"


def raw_dir(start: str | Path = __file__) -> Path:
    return resource_dir(start) / "data" / "raw"


def processed_dir(start: str | Path = __file__) -> Path:
    return resource_dir(start) / "data" / "processed"


def checkpoint_dir(start: str | Path = __file__) -> Path:
    return resource_dir(start) / "data" / "checkpoint"


def log_root(start: str | Path = __file__) -> Path:
    return resource_dir(start) / "log" / "data" / "process"


def crawler_log_dir(start: str | Path = __file__) -> Path:
    return resource_dir(start) / "log"


def dataset_raw_dir(dataset: str, start: str | Path = __file__) -> Path:
    return raw_dir(start) / dataset


def dataset_processed_dir(dataset: str, start: str | Path = __file__) -> Path:
    return processed_dir(start) / dataset


def dataset_log_dir(dataset: str, start: str | Path = __file__) -> Path:
    return log_root(start) / dataset