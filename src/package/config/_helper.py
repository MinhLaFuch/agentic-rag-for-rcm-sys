import re, os

from typing import Any

from ._error import ConfigError
from ._config import ENV_VAR_PATTERN

def _interpolate_env(value: Any) -> Any:
    if isinstance(value, str):
        def _replace(match: re.Match) -> str:
            var_name = match.group(1)
            if var_name not in os.environ:
                raise ConfigError(
                    f"Config references ${{{var_name}}} but env var "
                    f"'{var_name}' is not set."
                )
            return os.environ[var_name]

        return ENV_VAR_PATTERN.sub(_replace, value)
    if isinstance(value, dict):
        return {k: _interpolate_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate_env(v) for v in value]
    return value