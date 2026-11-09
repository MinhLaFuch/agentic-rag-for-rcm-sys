"""Manager for campaign checkpoint and resume functionality."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ._schema import CampaignResult


class CheckpointManager:
    """Manager for campaign checkpoint and resume functionality."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.checkpoint_file = output_dir / "campaign_checkpoint.json"

    def save_checkpoint(self, result: CampaignResult) -> None:
        """Save campaign checkpoint."""
        import json
        with open(self.checkpoint_file, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)

    def load_checkpoint(self) -> CampaignResult | None:
        """Load campaign checkpoint if exists."""
        if not self.checkpoint_file.exists():
            return None

        import json
        with open(self.checkpoint_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return CampaignResult.from_dict(data)

    def clear_checkpoint(self) -> None:
        """Clear campaign checkpoint."""
        if self.checkpoint_file.exists():
            self.checkpoint_file.unlink()
