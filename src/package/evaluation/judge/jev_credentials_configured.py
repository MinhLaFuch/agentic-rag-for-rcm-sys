"""True when a judge credential exists for the Jev provider.

Checks the env fallbacks JevProvider reads (TYPESAFE_API_KEY /
OPENROUTER_API_KEY) first, then judge.yaml's resolved api_key
(JEV_API_KEY env interpolation happens inside load_config).
"""

from __future__ import annotations

import os


def jev_credentials_configured() -> bool:
    if os.environ.get("TYPESAFE_API_KEY") or os.environ.get("OPENROUTER_API_KEY"):
        return True
    try:
        from package.config import load_config

        return bool(load_config("eval/judge").get("api_key"))
    except Exception:
        return False
