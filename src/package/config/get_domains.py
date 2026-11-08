from __future__ import annotations

from typing import Any

from .load_config import load_config


def get_domains(config: dict[str, Any] | None = None) -> list[str]:
    config = config or load_config("path/domains")
    return [d["name"] for d in config["domains"]]


def resolve_dataset_tag(domains: list[str] | None = None, config: dict[str, Any] | None = None) -> str:
    """Derive the artifact tag (resource/<kind>/<tag>/) from the selected domains.

    Single source of truth for dataset naming — every caller must go through
    this function instead of choosing a tag by hand:

    - ``domains=None`` or all configured domains -> ``merged_name``
      (configs/path/domains.yaml, currently ``"multi_domain"``)
    - exactly one domain -> that domain's name
    - any other subset -> ValueError (subset bundles are not supported)

    The returned value is stored under the ``tag`` key in ItemKNN provenance
    and experiment manifests; it is a derived name, not a user-chosen label.
    """
    config = config or load_config("path/domains")
    all_names = [d["name"] for d in config["domains"]]
    merged_name = config["merged_name"]

    selected = list(dict.fromkeys(domains)) if domains else list(all_names)
    unknown = [d for d in selected if d not in all_names]
    if unknown:
        raise ValueError(f"Unknown domain(s) {unknown}; known domains: {all_names}")

    if len(selected) == 1:
        return selected[0]
    if set(selected) == set(all_names):
        return merged_name
    raise ValueError(
        f"Cannot derive a dataset tag for domain subset {selected}: pass exactly "
        f"one domain or all domains {all_names} (merged artifact name: {merged_name!r})"
    )
