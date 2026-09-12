import os
from pathlib import Path
from typing import Literal, Optional, Union

from ._find_root import find_repo_root


RepositorySource = Literal["main", "forked"]
SOURCE_ENV_VAR = "LOCAL_PACKAGE_REPOSITORY"
FORKED_REPOSITORY_ENV_VAR = "LOCAL_PACKAGE_FORKED_REPOSITORY"

class PathConfig:
    def __init__(
        self,
        file: Union[str, Path],
        source: Optional[RepositorySource] = None,
        forked_repository: Optional[Union[str, Path]] = None,
    ) -> None:
        main_root = find_repo_root(file)
        if main_root is None:
            raise FileNotFoundError(f"Could not find pyproject.toml above {file}")

        selected_source = source or os.getenv(SOURCE_ENV_VAR, "main").lower()
        if selected_source not in {"main", "forked"}:
            raise ValueError(
                f"{SOURCE_ENV_VAR} must be 'main' or 'forked', got {selected_source!r}"
            )

        self.source: RepositorySource = selected_source
        if selected_source == "main":
            repository_root = main_root
            self.resource_dir = repository_root / "src" / "resource"
        else:
            forked_name = forked_repository or os.getenv(
                FORKED_REPOSITORY_ENV_VAR, "RecAI"
            )
            repository_root = main_root / "forked_repository" / Path(forked_name)
            self.resource_dir = self._find_resource_dir(repository_root)

        self.repository_root = repository_root
        self.raw_dir = self.resource_dir / "data" / "raw"
        self.processed_dir = self.resource_dir / "data" / "processed"
        self.checkpoint_dir = self.resource_dir / "data" / "checkpoint"
        self.log_dir = self.resource_dir / "log" / "data" / "process"
        self.crawler_log_dir = self.resource_dir / "log"

    @staticmethod
    def _find_resource_dir(repository_root: Path) -> Path:
        for candidate in (repository_root / "resource", repository_root / "src" / "resource"):
            if candidate.is_dir():
                return candidate
        return repository_root / "resource"

    def raw(self, dataset_name: str) -> Path:
        return self.raw_dir / dataset_name

    def processed(self, dataset_name: str) -> Path:
        return self.processed_dir / dataset_name

    def log(self, dataset_name: str) -> Path:
        return self.log_dir / dataset_name