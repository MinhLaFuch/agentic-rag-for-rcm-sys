MARKER = "pyproject.toml"

RESOURCE_DIR_ENV_VAR = "LOCAL_PACKAGE_RESOURCE_DIR"
WORKSPACE_ENV_VAR = "LOCAL_PACKAGE_WORKSPACE"
DEFAULT_WORKSPACE = "local"
# Shared input under resource/; never a log/export target.
SHARED_RESOURCE_NAMES = frozenset({"raw"})