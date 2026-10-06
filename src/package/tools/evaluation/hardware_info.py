from __future__ import annotations

import os
import platform
from typing import Any


def hardware_info() -> dict[str, Any]:
    """Get hardware and platform information."""
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cpu_count": os.cpu_count(),
    }
