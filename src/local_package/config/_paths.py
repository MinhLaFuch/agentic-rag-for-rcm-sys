from pathlib import Path
from ._find_root import find_repo_root

"""
<root>/
├── pyproject.toml (or any local marker)
└── resource/
    ├── data/
    │   ├── raw/          <- local raw (used when standalone, or forced via shared=False)
    │   └── processed/
    └── log/
        └── data/
            └── process/
                ├── amazon/
                ├── ml/
                └── steam/

Raw data can come from two places:
- shared: the main repo's own resource/data/raw (only exists if this file currently
    sits inside the main repo's tree, detected via `.gitmodules` above it)
- local: this repo's own resource/data/raw (always exists)

Call `.raw(name, shared=True/False)` to force one explicitly, or leave
`shared=None` (default) to auto-pick: shared if available, else local.
"""

class PathConfig:
    def __init__(self, file: str, local_marker: str = "pyproject.toml", shared_marker: str = ".gitmodules"):
        local_root = find_repo_root(file, local_marker)
        if local_root is None:
            raise FileNotFoundError(f"Could not find {local_marker} above {file}")

        shared_root = find_repo_root(file, shared_marker)
        raw_root = shared_root if shared_root else local_root

        self.resource_dir = local_root / "resource"
        self.raw_dir = (raw_root / "data" / "raw") if shared_root else (self.resource_dir / "data" / "raw")
        self.processed_dir = self.resource_dir / "data" / "processed"
        self.log_dir = self.resource_dir / "log" / "data" / "process"

    def raw(self, dataset_name: str) -> Path:
        return self.raw_dir / dataset_name

    def processed(self, dataset_name: str) -> Path:
        return self.processed_dir / dataset_name

    def log(self, dataset_name: str) -> Path:
        return self.log_dir / dataset_name