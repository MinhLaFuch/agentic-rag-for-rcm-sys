"""Bootstrap constants for the config module (not tunable: they are how YAML is found/parsed)."""

import re
from pathlib import Path

# ${VAR} (required) or ${VAR:-default} (optional; default may be empty, e.g. ${LLM_API_KEY:-})
ENV_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "configs"
