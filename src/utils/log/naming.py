from __future__ import annotations

import datetime
import re
from pathlib import Path


def _next_exp_number(directory: Path, scenario: str, date: datetime.date) -> int:
    """Highest existing Exp{N} for this scenario+date in `directory`, plus one."""
    if not directory.exists():
        return 1
    pattern = re.compile(rf"^Exp(\d+)_{re.escape(scenario)}_{date:%Y%m%d}\.log$")
    nums = [
        int(m.group(1))
        for f in directory.iterdir()
        if (m := pattern.match(f.name))
    ]
    return max(nums, default=0) + 1


def experiment_log_path(
    folder_name: str,
    scenario: str,
    *,
    workspace: str | None = None,
    exp_num: int | None = None,
    date: datetime.date | None = None,
    start: str | Path = __file__,
) -> Path:
    """
    `resource/<workspace>/log/<folder_name>/Exp{N}_{scenario}_{date}.log`

    - workspace: `"local"` or `"recai"` (see package.utils.path.resolve_workspace).
    - folder_name: purpose (`process`, `pipeline`).
    - scenario: script/module/experiment name.
    - N (exp_num): auto-increments per (workspace, folder_name, scenario, date)
      and resets to 1 each day. Pass exp_num explicitly to pin a run number.
    """
    from ..path import log_dir  # local import avoids a path<->log circular import

    date = date or datetime.date.today()
    directory = log_dir(workspace, folder_name, start=start)
    directory.mkdir(parents=True, exist_ok=True)

    if exp_num is None:
        exp_num = _next_exp_number(directory, scenario, date)

    path = directory / f"Exp{exp_num}_{scenario}_{date:%Y%m%d}.log"
    # Reserve the number immediately: setup_logging's FileHandler doesn't open
    # the file until later, so without this, two calls made back-to-back
    # (before either file exists) would both compute the same N.
    path.touch(exist_ok=True)
    return path