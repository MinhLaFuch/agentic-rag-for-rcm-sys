"""Helper functions for config module."""

import hashlib
import os
import re
from pathlib import Path
from typing import Any

import yaml

from ._error import ConfigError
from ._constants import CONFIG_DIR, ENV_VAR_PATTERN, PROJECT_ROOT

# Env var pointing at a YAML "overlay" file: per-run config overrides (e.g. written by the
# campaign runner) merged over configs/ before validation. Same shape as configs/ — top-level
# keys are config names ("agent/agent_eval"), values mirror the file's own content.
OVERLAY_ENV_VAR = "CONFIG_OVERLAY_PATH"

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


def _deep_merge(base: dict, overlay: dict) -> dict:
    """Merge ``overlay`` into ``base`` in place: dicts merge recursively, anything else replaces."""
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def _overlay_path() -> Path | None:
    """Resolved overlay file path, or None when CONFIG_OVERLAY_PATH is unset."""
    path = os.environ.get(OVERLAY_ENV_VAR)
    if not path:
        return None
    overlay_path = Path(path)
    if not overlay_path.is_absolute():
        overlay_path = PROJECT_ROOT / overlay_path
    return overlay_path


def _overlay_signature() -> tuple:
    """(resolved path, mtime_ns, size) of the configured overlay — for cache invalidation.

    Returns () when no overlay is configured or the file does not exist yet.
    """
    overlay_path = _overlay_path()
    if overlay_path is None or not overlay_path.exists():
        return ()
    st = overlay_path.stat()
    return (str(overlay_path), st.st_mtime_ns, st.st_size)


_overlay_cache: dict[tuple, tuple[Path, dict]] = {}


def _overlay_doc() -> tuple[Path, dict] | None:
    """Return (overlay_path, parsed doc); None when no overlay is configured.

    Fails closed: the file must exist, be a mapping, and every top-level key must
    name an existing ``configs/<name>.yaml`` — a typo'd config name is an error,
    not a silent no-op.
    """
    overlay_path = _overlay_path()
    if overlay_path is None:
        return None
    signature = _overlay_signature()
    if not signature:
        raise ConfigError(f"{OVERLAY_ENV_VAR} points to a missing file: {overlay_path}")
    cached = _overlay_cache.get(signature)
    if cached is not None:
        return cached
    doc = yaml.safe_load(overlay_path.read_text(encoding="utf-8")) or {}
    if not isinstance(doc, dict):
        raise ConfigError(f"{OVERLAY_ENV_VAR}: {overlay_path} must contain a mapping, got {type(doc).__name__}")
    for key in doc:
        if not isinstance(key, str) or not (CONFIG_DIR / f"{key}.yaml").is_file():
            raise ConfigError(
                f"{OVERLAY_ENV_VAR}: {overlay_path} sets unknown config {key!r} "
                f"(no configs/{key}.yaml)"
            )
    result = (overlay_path, doc)
    _overlay_cache[signature] = result
    return result


def _overlay_fragment(name: str) -> tuple[dict, Path | None]:
    """Return (fragment, overlay_path) for config ``name``; ({}, None) when no overlay is set."""
    loaded = _overlay_doc()
    if loaded is None:
        return {}, None
    overlay_path, doc = loaded
    entry = doc.get(name)
    if entry is not None and not isinstance(entry, dict):
        raise ConfigError(f"{OVERLAY_ENV_VAR}: overlay for '{name}' in {overlay_path} must be a mapping")
    return entry or {}, overlay_path


def _check_overlay_keys(
    config_name: str,
    fragment: dict,
    base: dict,
    overlay_path: Path,
    prefix: tuple[str, ...] = (),
) -> None:
    """Reject overlay keys that do not exist in the base config (fail closed).

    Dicts merge recursively and are checked key-by-key; lists/scalars replace the
    base value wholesale, so only the key itself must exist.
    """
    for key, value in fragment.items():
        dotted = ".".join((*prefix, str(key)))
        if key not in base:
            raise ConfigError(
                f"{OVERLAY_ENV_VAR}: {overlay_path} sets unknown key '{config_name}.{dotted}' "
                f"(absent from configs/{config_name}.yaml)"
            )
        if isinstance(value, dict) and isinstance(base[key], dict):
            _check_overlay_keys(config_name, value, base[key], overlay_path, (*prefix, str(key)))


def get_overlay_info() -> dict[str, Any] | None:
    """Provenance record for the active CONFIG_OVERLAY_PATH overlay, or None.

    Returns {"path", "sha256", "content"} — content is the parsed overlay doc.
    """
    loaded = _overlay_doc()
    if loaded is None:
        return None
    overlay_path, doc = loaded
    return {
        "path": str(overlay_path),
        "sha256": hashlib.sha256(overlay_path.read_bytes()).hexdigest(),
        "content": doc,
    }


def config_signature(name: str, config_dir: Path | None = None) -> tuple:
    """Change signature for one config: overlay signature + the YAML file's own stat.

    Used by lru_cached limits getters so setting CONFIG_OVERLAY_PATH (or editing the
    file) and then calling the getter directly cannot serve stale values.
    """
    directory = config_dir or CONFIG_DIR
    path = directory / f"{name}.yaml"
    parts: list = [_overlay_signature()]
    if path.exists():
        st = path.stat()
        parts.append((str(path), st.st_mtime_ns, st.st_size))
    return tuple(parts)