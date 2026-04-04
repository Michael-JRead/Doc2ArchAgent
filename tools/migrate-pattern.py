#!/usr/bin/env python3
# Copyright (c) 2026 Michael J. Read. All rights reserved.
# SPDX-License-Identifier: BUSL-1.1
"""Migrate legacy .pattern.yaml files to the new directory format.

Converts a single-file pattern (e.g., ibm-mq.pattern.yaml) into a directory
with pattern.meta.yaml + system.yaml (product) or networks.yaml (network).

Usage:
    python tools/migrate-pattern.py patterns/products/messaging/ibm-mq.pattern.yaml
    python tools/migrate-pattern.py patterns/networks/usa/standard-3tier.pattern.yaml

Output:
    Creates a directory alongside the .pattern.yaml file with the new format.
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Error: pyyaml required. pip install pyyaml", file=sys.stderr)
    sys.exit(1)


def migrate_pattern(pattern_path: Path, remove_old: bool = False) -> dict:
    """Migrate a legacy .pattern.yaml to directory format."""
    errors: list[str] = []

    if not pattern_path.exists():
        return {"valid": False, "errors": [f"File not found: {pattern_path}"]}

    with open(pattern_path) as f:
        data = yaml.safe_load(f)

    pattern = data.get("pattern")
    if not pattern:
        return {"valid": False, "errors": ["Missing top-level 'pattern' key"]}

    metadata = pattern.get("metadata", {})
    pattern_id = metadata.get("id", pattern_path.stem.replace(".pattern", ""))

    # Detect type
    is_network = "network_zones" in pattern
    is_product = "containers" in pattern
    pattern_type = "network" if is_network else "product"

    # Create output directory
    output_dir = pattern_path.parent / pattern_id
    output_dir.mkdir(exist_ok=True)

    # Build pattern.meta.yaml
    meta = {
        "pattern": {
            "id": pattern_id,
            "type": pattern_type,
            "name": metadata.get("name", pattern_id),
            "category": metadata.get("category", ""),
            "version": metadata.get("version", "1.0.0"),
            "description": metadata.get("description", ""),
        }
    }

    if metadata.get("tags"):
        meta["pattern"]["tags"] = metadata["tags"]

    # Build provides/requires
    if is_product:
        containers = [c["id"] for c in pattern.get("containers", []) if "id" in c]
        meta["pattern"]["provides"] = [
            {"capability": metadata.get("provides_capability", pattern_id),
             "containers": containers}
        ]
        meta["pattern"]["requires"] = [{"capability": "network-zones"}]
    elif is_network:
        zones = [z["id"] for z in pattern.get("network_zones", []) if "id" in z]
        meta["pattern"]["provides"] = [
            {"capability": "network-zones", "zones": zones}
        ]

    # Build binding points
    binding_points = []
    if is_network:
        for zone in pattern.get("network_zones", []):
            binding_points.append({
                "id": zone["id"],
                "type": "zone",
                "description": zone.get("description", ""),
            })
        for res in pattern.get("infrastructure_resources", []):
            binding_points.append({
                "id": res["id"],
                "type": "infrastructure_resource",
                "description": res.get("description", ""),
            })
    elif is_product:
        for ctr in pattern.get("containers", []):
            binding_points.append({
                "id": ctr["id"],
                "type": "container",
                "description": ctr.get("description", ""),
            })
        for comp in pattern.get("components", []):
            binding_points.append({
                "id": comp["id"],
                "type": "component",
                "bind_to": comp.get("container_id", ""),
                "description": comp.get("description", ""),
            })

    if binding_points:
        meta["pattern"]["binding_points"] = binding_points

    if metadata.get("version_tracking_enabled") is not None:
        meta["pattern"]["version_tracking_enabled"] = metadata["version_tracking_enabled"]
    if metadata.get("version_history"):
        meta["pattern"]["version_history"] = metadata["version_history"]

    # Write pattern.meta.yaml
    meta_path = output_dir / "pattern.meta.yaml"
    with open(meta_path, "w") as f:
        yaml.dump(meta, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    # Build and write the schema-conformant YAML
    if is_network:
        network_data = {
            "network_zones": pattern.get("network_zones", []),
            "infrastructure_resources": pattern.get("infrastructure_resources", []),
        }
        yaml_path = output_dir / "networks.yaml"
        with open(yaml_path, "w") as f:
            yaml.dump(network_data, f, default_flow_style=False, sort_keys=False,
                      allow_unicode=True)
    elif is_product:
        system_data = {
            "metadata": {
                "name": metadata.get("name", pattern_id),
                "description": metadata.get("description", ""),
                "owner": f"pattern-{pattern_id}",
                "status": "active",
            },
            "contexts": [{
                "id": f"{pattern_id}-context",
                "name": f"{metadata.get('name', pattern_id)} Context",
                "description": metadata.get("description", ""),
                "internal": True,
            }],
            "containers": [],
            "components": pattern.get("components", []),
            "component_relationships": pattern.get("component_relationships", []),
        }
        # Add context_id to containers
        for ctr in pattern.get("containers", []):
            ctr_copy = dict(ctr)
            ctr_copy["context_id"] = f"{pattern_id}-context"
            system_data["containers"].append(ctr_copy)

        yaml_path = output_dir / "system.yaml"
        with open(yaml_path, "w") as f:
            yaml.dump(system_data, f, default_flow_style=False, sort_keys=False,
                      allow_unicode=True)

    # Create contexts/ hierarchy
    contexts_dir = output_dir / "contexts"
    contexts_dir.mkdir(exist_ok=True)
    sources_dir = contexts_dir / "sources"
    sources_dir.mkdir(exist_ok=True)

    files_created = [str(meta_path), str(yaml_path)]

    # Generate _context.yaml
    context_yaml_path = contexts_dir / "_context.yaml"
    if is_product:
        context_data = {
            "contexts": [{
                "id": f"{pattern_id}-context",
                "name": f"{metadata.get('name', pattern_id)} Context",
                "description": metadata.get("description", ""),
                "internal": True,
                "owner": f"pattern-{pattern_id}",
            }]
        }
    elif is_network:
        context_data = {
            "contexts": [{
                "id": f"{pattern_id}-network",
                "name": f"{metadata.get('name', pattern_id)} Network",
                "description": metadata.get("description", ""),
                "internal": True,
                "owner": "network-infrastructure-team",
            }]
        }
    with open(context_yaml_path, "w") as f:
        yaml.dump(context_data, f, default_flow_style=False, sort_keys=False,
                  allow_unicode=True)
    files_created.append(str(context_yaml_path))

    # Generate empty doc-inventory.yaml
    inventory_path = sources_dir / "doc-inventory.yaml"
    inventory_data = {
        "pattern_ref": pattern_id,
        "pattern_type": pattern_type,
        "documents": [],
    }
    with open(inventory_path, "w") as f:
        yaml.dump(inventory_data, f, default_flow_style=False, sort_keys=False,
                  allow_unicode=True)
    files_created.append(str(inventory_path))

    # Generate empty provenance.yaml
    provenance_path = contexts_dir / "provenance.yaml"
    provenance_data = {
        "extraction_date": "",
        "documents_analyzed": [],
        "entities": [],
    }
    with open(provenance_path, "w") as f:
        yaml.dump(provenance_data, f, default_flow_style=False, sort_keys=False,
                  allow_unicode=True)
    files_created.append(str(provenance_path))

    if remove_old:
        pattern_path.unlink()

    return {
        "valid": True,
        "errors": errors,
        "output_dir": str(output_dir),
        "files_created": files_created,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Migrate legacy .pattern.yaml to directory format")
    parser.add_argument("pattern", type=Path,
                        help="Path to legacy .pattern.yaml file")
    parser.add_argument("--remove-old", action="store_true",
                        help="Remove the old .pattern.yaml after migration")
    args = parser.parse_args()

    result = migrate_pattern(args.pattern, remove_old=args.remove_old)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
