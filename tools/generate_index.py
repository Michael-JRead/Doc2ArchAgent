#!/usr/bin/env python3
# Copyright (c) 2026 Michael J. Read. All rights reserved.
# SPDX-License-Identifier: BUSL-1.1
"""
Generate index.yaml from system.yaml for L0/L1 context-efficient loading.

Implements OpenViking-inspired hierarchical context management:
- L0: One-sentence abstract (for quick identification)
- L1: Overview with counts and key relationships (for planning)
- L2: Full system.yaml content (loaded only when needed)

The generated index.yaml enables agents to understand the architecture
without loading the full system.yaml into context.

Usage:
    python tools/generate_index.py <system.yaml>
    python tools/generate_index.py architecture/*/system.yaml
"""

import argparse
import sys
from pathlib import Path

import yaml


def generate_index(system_yaml_path: str) -> None:
    """Generate index.yaml alongside the given system.yaml."""
    system_path = Path(system_yaml_path)

    if not system_path.exists():
        print(f"Error: {system_path} not found", file=sys.stderr)
        sys.exit(1)

    with open(system_path) as f:
        system = yaml.safe_load(f)

    if not system:
        print(f"Error: {system_path} is empty", file=sys.stderr)
        sys.exit(1)

    metadata = system.get("metadata", {})
    contexts = system.get("contexts", [])
    containers = system.get("containers", [])
    components = system.get("components", [])
    component_rels = system.get("component_relationships", [])
    external_systems = system.get("external_systems", [])
    data_entities = system.get("data_entities", [])
    trust_boundaries = system.get("trust_boundaries", [])

    # L0 summary — one sentence
    system_name = metadata.get("name", "Unknown System")
    l0 = (
        f"{system_name}: {len(contexts)} context(s), "
        f"{len(containers)} container(s), {len(components)} component(s)"
    )

    if external_systems:
        l0 += f", {len(external_systems)} external system(s)"

    # L1 context index
    context_index = []
    for ctx in contexts:
        ctx_id = ctx.get("id", "")
        ctx_containers = [
            c for c in containers if c.get("context_id") == ctx_id
        ]
        ctx_entry = {
            "id": ctx_id,
            "name": ctx.get("name", ""),
            "internal": ctx.get("internal", True),
            "container_count": len(ctx_containers),
        }
        if ctx.get("description"):
            ctx_entry["description"] = ctx["description"]
        context_index.append(ctx_entry)

    # L1 container index
    container_index = []
    for cont in containers:
        cont_id = cont.get("id", "")
        cont_components = [
            c for c in components if c.get("container_id") == cont_id
        ]
        cont_entry = {
            "id": cont_id,
            "context_id": cont.get("context_id", ""),
            "name": cont.get("name", ""),
            "component_count": len(cont_components),
            "technology": cont.get("technology", "unknown"),
        }
        container_index.append(cont_entry)

    # L1 key relationships (top-level only)
    key_rels = []
    for rel in component_rels[:20]:  # Cap at 20 for L1
        listener_ref = rel.get("target_listener_ref", "")
        rel_entry = {
            "source": rel.get("source_component", ""),
            "target": rel.get("target_component", ""),
        }
        if listener_ref:
            # Find the listener to get protocol/port
            for comp in components:
                if comp.get("id") == rel.get("target_component"):
                    for listener in comp.get("listeners", []):
                        if listener.get("id") == listener_ref:
                            proto = listener.get("protocol", "")
                            port = listener.get("port", "")
                            if proto and port:
                                rel_entry["protocol"] = f"{proto}/{port}"
                            break
                    break
        key_rels.append(rel_entry)

    # Build index
    index = {
        "index": {
            "system_id": metadata.get("name", "").lower().replace(" ", "-"),
            "l0_summary": l0,
            "metadata": {
                "name": metadata.get("name", ""),
                "owner": metadata.get("owner", ""),
                "status": metadata.get("status", ""),
                "compliance_frameworks": metadata.get(
                    "compliance_frameworks", []
                ),
            },
            "counts": {
                "contexts": len(contexts),
                "containers": len(containers),
                "components": len(components),
                "component_relationships": len(component_rels),
                "external_systems": len(external_systems),
                "data_entities": len(data_entities),
                "trust_boundaries": len(trust_boundaries),
            },
            "contexts": context_index,
            "containers": container_index,
        }
    }

    if key_rels:
        index["index"]["key_relationships"] = key_rels

    # Write index.yaml alongside system.yaml
    output_path = system_path.parent / "index.yaml"
    with open(output_path, "w") as f:
        yaml.dump(index, f, default_flow_style=False, sort_keys=False)

    print(f"Generated {output_path} (L0: {l0})")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate L0/L1 index from system.yaml"
    )
    parser.add_argument(
        "system_yaml",
        nargs="+",
        help="Path(s) to system.yaml file(s)",
    )
    args = parser.parse_args()

    for path in args.system_yaml:
        generate_index(path)


if __name__ == "__main__":
    main()
