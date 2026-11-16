"""Opt-in historical config evidence, separate from current runtime settings."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from package.config import PROJECT_ROOT, load_config
from package.recommenders.shared import file_hash


def load_audit_profile(paths, *, project_root=PROJECT_ROOT):
    """Validate the explicit profile and effective runtime contract, or return None.

    Manifest hashes remain the authority for historical config contents. A profile
    never replaces expected hashes or changes input/output/upstream verification.
    """
    value = os.environ.get("EVAL_BUNDLE_PROFILE")
    if not value:
        return None
    root = Path(project_root).resolve()
    path = Path(value)
    path = (root / path).resolve() if not path.is_absolute() else path.resolve()
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or doc.get("version") != 1 or doc.get("tag") != paths.tag:
        raise ValueError("Audit profile version/tag mismatch")

    def inside(relative):
        resolved = (root / relative).resolve()
        if Path(relative).is_absolute() or not resolved.is_relative_to(root):
            raise ValueError("Audit profile path must stay within project root")
        return resolved

    snapshot_root = inside(doc["snapshot_root"])
    overlay_path = inside(doc["overlay_path"])
    active = os.environ.get("CONFIG_OVERLAY_PATH")
    if not active or Path(active).resolve() != overlay_path:
        raise ValueError("Audit profile requires CONFIG_OVERLAY_PATH set to its absolute overlay path")
    overlay_hash = file_hash(overlay_path)
    if overlay_hash != doc["overlay_sha256"]:
        raise ValueError("Audit profile overlay checksum mismatch")

    def check_subset(actual, required, prefix):
        if isinstance(required, dict):
            if not isinstance(actual, dict):
                raise ValueError(f"Runtime config incompatible at {prefix}")
            for key, expected in required.items():
                if key not in actual:
                    raise ValueError(f"Runtime config missing {prefix}.{key}")
                check_subset(actual[key], expected, f"{prefix}.{key}")
        elif actual != required:
            raise ValueError(f"Runtime config incompatible at {prefix}: {actual!r} != {required!r}")

    required_configs = doc.get("required_runtime_configs")
    if not required_configs:
        raise ValueError("Audit profile lacks runtime compatibility contract")
    for name, required in required_configs.items():
        check_subset(load_config(name), required, name)
    # Validate the essential contract against bundle evidence, not only profile claims.
    stage3 = paths.splits_dir / "stage_3.manifest.json"
    import json
    flags = json.loads(stage3.read_text(encoding="utf-8"))["flags"]
    split = load_config("data/split")["split"]
    if split.get("data_protocol") != flags.get("data_protocol"):
        raise ValueError("Audit runtime data protocol differs from recorded stage 3 protocol")
    if flags.get("data_protocol") == "temporal_train_core":
        cutoff = split.get("temporal_train_core", {})
        if (cutoff.get("train_end_inclusive_ms"), cutoff.get("validation_end_inclusive_ms")) != (flags.get("cutoff_1"), flags.get("cutoff_2")):
            raise ValueError("Audit runtime cutoffs differ from recorded stage 3 cutoffs")
    return {"path": str(path), "sha256": file_hash(path), "tag": paths.tag,
            "historical_config_root": str(snapshot_root), "overlay_path": str(overlay_path),
            "overlay_sha256": overlay_hash, "runtime_contract": required_configs,
            "historical_and_runtime_configs_are_separate": True}
