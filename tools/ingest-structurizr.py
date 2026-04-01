#!/usr/bin/env python3
# Copyright (c) 2026 Michael J. Read. All rights reserved.
# SPDX-License-Identifier: BUSL-1.1
"""Deterministic Structurizr DSL → Doc2ArchAgent YAML converter.

Parses Structurizr DSL (.dsl) files to extract:
  - workspace/model → System metadata
  - person → External actors (contexts)
  - softwareSystem → Contexts
  - container → Containers with technology
  - component → Components with technology
  - -> (relationship) → Component/container relationships
  - deploymentEnvironment → Deployment metadata
  - deploymentNode → Zone placements
  - group → Trust boundaries

Usage:
    python tools/ingest-structurizr.py <workspace.dsl> [--output <dir>]

Output:
    JSON to stdout with extracted entities, or writes YAML files to --output directory.

This is deterministic parsing, not LLM inference. Follows zero-hallucination principles.
"""

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Error: pyyaml is required. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


def parse_structurizr_dsl(content: str) -> dict:
    """Parse a Structurizr DSL file and extract architecture entities."""
    entities = {
        "contexts": [],
        "containers": [],
        "components": [],
        "relationships": [],
        "deployments": [],
        "external_systems": [],
        "persons": [],
        "groups": [],
        "metadata": {"source_format": "structurizr", "parser": "dsl-regex"},
    }

    # Remove comments (// and /* */)
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    content = re.sub(r'//[^\n]*', '', content)

    # Extract workspace metadata
    workspace_match = re.search(r'workspace\s+"([^"]*)"(?:\s+"([^"]*)")?\s*\{', content)
    if workspace_match:
        entities["metadata"]["workspace_name"] = workspace_match.group(1)
        if workspace_match.group(2):
            entities["metadata"]["workspace_description"] = workspace_match.group(2)

    # Find the model block
    model_content = _extract_block(content, "model")
    if model_content:
        _parse_model(model_content, entities)

    # Find deployment environments
    _parse_deployments(model_content or content, entities)

    return entities


def _extract_block(content: str, block_type: str) -> str | None:
    """Extract the content of a named block, handling nested braces."""
    pattern = re.compile(rf'\b{re.escape(block_type)}\b[^{{]*\{{')
    match = pattern.search(content)
    if not match:
        return None

    start = match.end()
    depth = 1
    i = start
    while i < len(content) and depth > 0:
        if content[i] == '{':
            depth += 1
        elif content[i] == '}':
            depth -= 1
        i += 1

    return content[start:i - 1] if depth == 0 else None


def _parse_model(model_content: str, entities: dict):
    """Parse the model block to extract persons, systems, containers, components."""

    # Extract persons: identifier = person "Name" "Description" { ... }
    # or: identifier = person "Name" "Description"
    person_pattern = re.compile(
        r'(\w+)\s*=\s*person\s+"([^"]*)"(?:\s+"([^"]*)")?\s*(?:\{([^}]*)\})?',
        re.DOTALL,
    )
    for match in person_pattern.finditer(model_content):
        identifier = match.group(1)
        name = match.group(2)
        description = match.group(3) or ""
        entities["persons"].append({
            "id": _to_kebab(identifier),
            "dsl_id": identifier,
            "name": name,
            "description": description,
            "_source": f"structurizr:person.{identifier}",
        })

    # Extract software systems: identifier = softwareSystem "Name" "Description" { ... }
    system_pattern = re.compile(
        r'(\w+)\s*=\s*softwareSystem\s+"([^"]*)"(?:\s+"([^"]*)")?\s*(?:\{([^}]*(?:\{[^}]*\}[^}]*)*)\})?',
        re.DOTALL,
    )
    for match in system_pattern.finditer(model_content):
        identifier = match.group(1)
        name = match.group(2)
        description = match.group(3) or ""
        body = match.group(4) or ""

        # Check if external (tagged or no containers)
        tags = _extract_tags(body)
        is_external = "External" in tags or "external" in tags

        if is_external:
            entities["external_systems"].append({
                "id": _to_kebab(identifier),
                "dsl_id": identifier,
                "name": name,
                "description": description,
                "tags": tags,
                "_source": f"structurizr:softwareSystem.{identifier}",
            })
        else:
            entities["contexts"].append({
                "id": _to_kebab(identifier),
                "dsl_id": identifier,
                "name": name,
                "description": description,
                "tags": tags,
                "_source": f"structurizr:softwareSystem.{identifier}",
            })

            # Extract containers within this system
            _parse_containers(body, identifier, entities)

    # Extract groups: group "Name" { ... }
    group_pattern = re.compile(
        r'group\s+"([^"]*)"(?:\s+"([^"]*)")?\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}',
        re.DOTALL,
    )
    for match in group_pattern.finditer(model_content):
        group_name = match.group(1)
        entities["groups"].append({
            "id": _to_kebab(group_name),
            "name": group_name,
            "_source": f"structurizr:group.{_to_kebab(group_name)}",
        })

    # Extract relationships: source -> target "Label" "Technology" { ... }
    _parse_relationships(model_content, entities)


def _parse_containers(system_body: str, system_id: str, entities: dict):
    """Extract containers from a softwareSystem block."""
    container_pattern = re.compile(
        r'(\w+)\s*=\s*container\s+"([^"]*)"(?:\s+"([^"]*)")?(?:\s+"([^"]*)")?\s*(?:\{([^}]*(?:\{[^}]*\}[^}]*)*)\})?',
        re.DOTALL,
    )
    for match in container_pattern.finditer(system_body):
        identifier = match.group(1)
        name = match.group(2)
        description = match.group(3) or ""
        technology = match.group(4) or ""
        body = match.group(5) or ""

        tags = _extract_tags(body)

        container = {
            "id": _to_kebab(identifier),
            "dsl_id": identifier,
            "name": name,
            "description": description,
            "technology": technology,
            "parent_system": _to_kebab(system_id),
            "tags": tags,
            "_source": f"structurizr:container.{identifier}",
        }

        # Infer container type from tags or technology
        container["container_type"] = _infer_container_type(tags, technology, name)

        entities["containers"].append(container)

        # Extract components within this container
        _parse_components(body, identifier, entities)


def _parse_components(container_body: str, container_id: str, entities: dict):
    """Extract components from a container block."""
    component_pattern = re.compile(
        r'(\w+)\s*=\s*component\s+"([^"]*)"(?:\s+"([^"]*)")?(?:\s+"([^"]*)")?\s*(?:\{([^}]*)\})?',
        re.DOTALL,
    )
    for match in component_pattern.finditer(container_body):
        identifier = match.group(1)
        name = match.group(2)
        description = match.group(3) or ""
        technology = match.group(4) or ""
        body = match.group(5) or ""

        tags = _extract_tags(body)

        entities["components"].append({
            "id": _to_kebab(identifier),
            "dsl_id": identifier,
            "name": name,
            "description": description,
            "technology": technology,
            "parent_container": _to_kebab(container_id),
            "tags": tags,
            "_source": f"structurizr:component.{identifier}",
        })


def _parse_relationships(content: str, entities: dict):
    """Extract relationships from DSL content."""
    # Pattern: identifier -> identifier "Label" "Technology" { ... }
    rel_pattern = re.compile(
        r'(\w+)\s*->\s*(\w+)\s+"([^"]*)"(?:\s+"([^"]*)")?\s*(?:\{([^}]*)\})?'
    )
    for match in rel_pattern.finditer(content):
        source = match.group(1)
        target = match.group(2)
        label = match.group(3)
        technology = match.group(4) or ""

        entities["relationships"].append({
            "id": _to_kebab(f"{source}-to-{target}"),
            "source_dsl_id": source,
            "target_dsl_id": target,
            "source": _to_kebab(source),
            "target": _to_kebab(target),
            "label": label,
            "technology": technology,
            "sync": "async" not in technology.lower() if technology else True,
            "_source": f"structurizr:relationship.{source}->{target}",
        })


def _parse_deployments(content: str, entities: dict):
    """Extract deployment environments from DSL content."""
    deploy_env_pattern = re.compile(
        r'deploymentEnvironment\s+"([^"]*)"\s*\{([^}]*(?:\{[^}]*(?:\{[^}]*\}[^}]*)*\}[^}]*)*)\}',
        re.DOTALL,
    )
    for match in deploy_env_pattern.finditer(content):
        env_name = match.group(1)
        env_body = match.group(2)

        deployment = {
            "id": _to_kebab(env_name),
            "name": env_name,
            "nodes": [],
            "_source": f"structurizr:deploymentEnvironment.{_to_kebab(env_name)}",
        }

        # Extract deployment nodes
        node_pattern = re.compile(
            r'deploymentNode\s+"([^"]*)"(?:\s+"([^"]*)")?(?:\s+"([^"]*)")?\s*(?:(\d+)\s*)?\{([^}]*(?:\{[^}]*\}[^}]*)*)\}',
            re.DOTALL,
        )
        for node_match in node_pattern.finditer(env_body):
            node_name = node_match.group(1)
            node_desc = node_match.group(2) or ""
            node_tech = node_match.group(3) or ""
            instances = node_match.group(4) or "1"
            node_body = node_match.group(5) or ""

            node = {
                "id": _to_kebab(node_name),
                "name": node_name,
                "description": node_desc,
                "technology": node_tech,
                "instances": int(instances) if instances.isdigit() else 1,
                "container_instances": [],
            }

            # Extract containerInstance references
            ci_pattern = re.compile(r'containerInstance\s+(\w+)')
            for ci_match in ci_pattern.finditer(node_body):
                node["container_instances"].append(_to_kebab(ci_match.group(1)))

            # Extract infrastructureNode references
            infra_pattern = re.compile(
                r'infrastructureNode\s+"([^"]*)"(?:\s+"([^"]*)")?(?:\s+"([^"]*)")?'
            )
            for infra_match in infra_pattern.finditer(node_body):
                node.setdefault("infrastructure_nodes", []).append({
                    "name": infra_match.group(1),
                    "description": infra_match.group(2) or "",
                    "technology": infra_match.group(3) or "",
                })

            deployment["nodes"].append(node)

        entities["deployments"].append(deployment)


def _extract_tags(body: str) -> list[str]:
    """Extract tags from a DSL block body."""
    tags_match = re.search(r'tags\s+"([^"]*)"', body)
    if tags_match:
        return [t.strip() for t in tags_match.group(1).split(",")]
    return []


def _infer_container_type(tags: list[str], technology: str, name: str) -> str:
    """Infer container type from tags, technology, or name."""
    combined = " ".join(tags + [technology, name]).lower()

    if any(kw in combined for kw in ("database", "db", "postgres", "mysql", "mongo", "dynamo", "rds")):
        return "database"
    if any(kw in combined for kw in ("queue", "kafka", "rabbitmq", "sqs", "message")):
        return "message_queue"
    if any(kw in combined for kw in ("cache", "redis", "memcache", "elasticache")):
        return "cache"
    if any(kw in combined for kw in ("web", "browser", "spa", "frontend", "react", "angular", "vue")):
        return "web_app"
    if any(kw in combined for kw in ("api", "rest", "graphql", "gateway")):
        return "api"
    if any(kw in combined for kw in ("worker", "background", "batch", "cron", "scheduler")):
        return "background_service"

    return "service"


def _to_kebab(name: str) -> str:
    """Convert a name to kebab-case."""
    s = re.sub(r'[A-Z]', lambda m: '-' + m.group(0).lower(), name)
    s = re.sub(r'[^a-z0-9-]', '-', s.lower())
    s = re.sub(r'-+', '-', s).strip('-')
    return s or "unknown"


def entities_to_yaml(entities: dict, output_dir: str):
    """Write extracted entities to Doc2ArchAgent YAML files."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    workspace_name = entities["metadata"].get("workspace_name", "Imported from Structurizr")

    # Write system.yaml
    system = {
        "metadata": {
            "name": workspace_name,
            "description": entities["metadata"].get("workspace_description",
                           f"Auto-extracted from Structurizr DSL"),
            "owner": "TODO",
            "status": "proposed",
        },
    }

    if entities["contexts"]:
        system["contexts"] = [
            {k: v for k, v in c.items() if not k.startswith("_") and k != "dsl_id"}
            for c in entities["contexts"]
        ]

    if entities["containers"]:
        system["containers"] = [
            {k: v for k, v in c.items() if not k.startswith("_") and k != "dsl_id"}
            for c in entities["containers"]
        ]

    if entities["components"]:
        system["components"] = [
            {k: v for k, v in c.items() if not k.startswith("_") and k != "dsl_id"}
            for c in entities["components"]
        ]

    if entities["external_systems"]:
        system["external_systems"] = [
            {k: v for k, v in s.items() if not k.startswith("_") and k != "dsl_id"}
            for s in entities["external_systems"]
        ]

    if entities["persons"]:
        system["persons"] = [
            {k: v for k, v in p.items() if not k.startswith("_") and k != "dsl_id"}
            for p in entities["persons"]
        ]

    if entities["relationships"]:
        system["relationships"] = [
            {k: v for k, v in r.items()
             if not k.startswith("_") and k not in ("source_dsl_id", "target_dsl_id")}
            for r in entities["relationships"]
        ]

    with open(output / "system.yaml", "w") as f:
        f.write("# Auto-generated from Structurizr DSL by ingest-structurizr.py\n")
        f.write("# Review and refine with @architect before use.\n\n")
        yaml.dump(system, f, default_flow_style=False, sort_keys=False)

    # Write deployments if present
    for deployment in entities["deployments"]:
        deploy_file = output / "deployments" / f"{deployment['id']}.yaml"
        deploy_file.parent.mkdir(parents=True, exist_ok=True)
        deploy_data = {
            "deployment_metadata": {
                "id": deployment["id"],
                "name": deployment["name"],
                "status": "proposed",
            },
            "nodes": [
                {k: v for k, v in n.items() if not k.startswith("_")}
                for n in deployment.get("nodes", [])
            ],
        }
        with open(deploy_file, "w") as f:
            f.write("# Auto-generated from Structurizr DSL by ingest-structurizr.py\n\n")
            yaml.dump(deploy_data, f, default_flow_style=False, sort_keys=False)

    print(json.dumps({
        "success": True,
        "output_dir": str(output),
        "entities": {
            "contexts": len(entities["contexts"]),
            "containers": len(entities["containers"]),
            "components": len(entities["components"]),
            "relationships": len(entities["relationships"]),
            "external_systems": len(entities["external_systems"]),
            "persons": len(entities["persons"]),
            "deployments": len(entities["deployments"]),
            "groups": len(entities["groups"]),
        },
    }, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Convert Structurizr DSL to Doc2ArchAgent YAML.")
    parser.add_argument("spec", help="Path to Structurizr DSL file (.dsl)")
    parser.add_argument("--output", help="Output directory for YAML files")
    args = parser.parse_args()

    path = Path(args.spec)
    if not path.exists():
        print(json.dumps({"error": f"File not found: {args.spec}"}))
        sys.exit(1)

    entities = parse_structurizr_dsl(path.read_text())

    if args.output:
        entities_to_yaml(entities, args.output)
    else:
        print(json.dumps(entities, indent=2, default=str))


if __name__ == "__main__":
    main()
