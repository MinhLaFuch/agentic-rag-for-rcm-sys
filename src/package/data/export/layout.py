from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from ...utils import workspace_dir


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass(frozen=True)
class ExportDirs:
    """Where one category's exports go: `resource/<workspace>/<kind>/<category>`."""

    category: str
    workspace: str | None = None

    # Class-level constants: shared by every instance, not init parameters.
    MAPPED: ClassVar[str] = "mapped"
    PROCESSED: ClassVar[str] = "processed"
    SPLITS: ClassVar[str] = "splits"

    def _resolve(self, kind: str) -> Path:
        return workspace_dir(self.workspace) / kind / self.category

    @property
    def mapped(self) -> Path:
        return self._resolve(self.MAPPED)

    @property
    def processed(self) -> Path:
        return self._resolve(self.PROCESSED)

    @property
    def splits(self) -> Path:
        return self._resolve(self.SPLITS)