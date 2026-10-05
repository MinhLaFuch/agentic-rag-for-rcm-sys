"""Helper functions for config module."""

import re, os

from typing import Any

from ._error import ConfigError
from ._constants import ENV_VAR_PATTERN

def _interpolate_env(value: Any) -> Any:
    if isinstance(value, str):
        def _replace(match: re.Match) -> str:
            var_name, default = match.group(1), match.group(2)
            value = os.environ.get(var_name)
            if default is not None and not value:  # shell ":-" semantics: unset OR empty
                return default
            if value is None:
                raise ConfigError(
                    f"Config references ${{{var_name}}} but env var "
                    f"'{var_name}' is not set."
                )
            return value

        return ENV_VAR_PATTERN.sub(_replace, value)
    if isinstance(value, dict):
        return {k: _interpolate_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate_env(v) for v in value]
    return value