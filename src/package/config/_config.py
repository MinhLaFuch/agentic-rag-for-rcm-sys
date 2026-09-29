import re
from pathlib import Path

ENV_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")

CONFIG_DIR = Path(__file__).resolve().parents[2] / "configs"