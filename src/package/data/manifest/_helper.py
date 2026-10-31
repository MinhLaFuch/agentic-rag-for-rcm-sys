"""Internal helpers shared by pipeline manifest creation and validation."""

from __future__ import annotations

from pathlib import Path

from package.config import CONFIG_DIR, PROJECT_ROOT
from package.tools.evaluation.sha256_file import sha256_file
from .verify_manifest import verify_manifest
from .write_manifest import _relative


def _config_files(stage: str) -> list[Path]:
    files = list((CONFIG_DIR / "data").glob("*.yaml"))
    files.append(CONFIG_DIR / "path" / "domains.yaml")
    if stage == "build_artifacts":
        files.extend((CONFIG_DIR / "agent" / "agent_eval.yaml", CONFIG_DIR / "eval" / "baselines.yaml"))
    if stage == "map_split":
        files.append(CONFIG_DIR / "eval" / "segment_thresholds.yaml")
    return [path for path in sorted(set(files)) if path.is_file()]


def _check_upstream(manifests: list[Path], expected_inputs: list[list[Path]], *, allow_mismatch: bool) -> list[str]:
    """Require valid upstream stage manifests or return explicit bypass warnings."""
    warnings: list[str] = []
    for manifest_index, path in enumerate(manifests):
        if not path.is_file():
            try:
                display = path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
            except ValueError:
                display = path.name
            message = f"upstream manifest missing: {display}"
            if not allow_mismatch:
                raise FileNotFoundError(message + "; rerun the preceding pipeline stage or pass --allow-manifest-mismatch")
            warnings.append(message)
            continue
        try:
            result = verify_manifest(path, project_root=PROJECT_ROOT)
        except ValueError as exc:
            if not allow_mismatch:
                raise
            warnings.append(str(exc))
            continue
        warnings.extend(result.get("manifest", {}).get("warnings", []))
        warnings.extend(f"external artifact path cannot be independently reopened: {item}"
                        for item in result.get("unverified_external", []))
        prior_outputs = {record["path"]: record["sha256"] for record in result["manifest"].get("outputs", [])}
        for current_input in expected_inputs[manifest_index]:
            relative = _relative(current_input, PROJECT_ROOT)
            expected = prior_outputs.get(relative)
            actual = sha256_file(current_input) if current_input.is_file() else "missing"
            if expected != actual:
                message = f"upstream artifact mismatch: {relative}: expected={expected or 'not recorded'} actual={actual}"
                if not allow_mismatch:
                    raise ValueError(message)
                warnings.append(message)
    return warnings

