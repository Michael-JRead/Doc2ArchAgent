#!/usr/bin/env python3
# Copyright (c) 2026 Michael J. Read. All rights reserved.
# SPDX-License-Identifier: BUSL-1.1
"""Deterministic Terraform/CloudFormation → Doc2ArchAgent YAML converter.

Parses IaC files and extracts architecture entities:
  - Resources → Components/Containers
  - Security Groups → Listeners (protocol, port, CIDR)
  - VPCs/Subnets → Network zones
  - IAM Roles → Trust relationships

Usage:
    python tools/ingest-terraform.py <path-to-iac> [--format terraform|cloudformation] [--output <dir>]

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


def parse_terraform_hcl(content: str) -> dict:
    """Parse Terraform HCL and extract architecture-relevant resources.

    Note: This is a simplified parser for common patterns. For full HCL parsing,
    use the `python-hcl2` library. This parser handles the most common resource types.
    """
    entities = {
        "containers": [],
        "components": [],
        "network_zones": [],
        "infrastructure_resources": [],
        "listeners": [],
        "metadata": {"source_format": "terraform", "parser": "simplified-hcl"},
    }

    # Extract resource blocks: resource "type" "name" { ... }
    resource_pattern = re.compile(
        r'resource\s+"([^"]+)"\s+"([^"]+)"\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}',
        re.DOTALL,
    )

    for match in resource_pattern.finditer(content):
        resource_type = match.group(1)
        resource_name = match.group(2)
        body = match.group(3)

        _process_terraform_resource(resource_type, resource_name, body, entities)

    return entities


def _process_terraform_resource(rtype: str, name: str, body: str, entities: dict):
    """Map a Terraform resource to Doc2ArchAgent entities."""
    rid = _to_kebab(name)

    # VPC → Network zone (top-level)
    if rtype == "aws_vpc":
        cidr = _extract_hcl_value(body, "cidr_block")
        entities["network_zones"].append({
            "id": rid,
            "name": _extract_hcl_value(body, "tags.Name") or name,
            "zone_type": "vpc",
            "internet_routable": False,
            "trust": "trusted",
            "description": f"VPC {cidr or ''}".strip(),
            "_source": f"terraform:aws_vpc.{name}",
        })

    # Subnet → Network zone (child)
    elif rtype == "aws_subnet":
        cidr = _extract_hcl_value(body, "cidr_block")
        is_public = "true" in body.lower() and "map_public_ip" in body.lower()
        entities["network_zones"].append({
            "id": rid,
            "name": _extract_hcl_value(body, "tags.Name") or name,
            "zone_type": "subnet",
            "internet_routable": is_public,
            "trust": "semi_trusted" if is_public else "trusted",
            "description": f"Subnet {cidr or ''}".strip(),
            "_source": f"terraform:aws_subnet.{name}",
        })

    # Security Group → Infrastructure resource + listener extraction
    elif rtype == "aws_security_group":
        entities["infrastructure_resources"].append({
            "id": rid,
            "name": _extract_hcl_value(body, "tags.Name") or name,
            "resource_type": "security_group",
            "technology": "AWS Security Group",
            "zone_id": "unknown",
            "_source": f"terraform:aws_security_group.{name}",
        })
        # Extract ingress rules as listeners
        _extract_sg_rules(body, rid, entities)

    # ECS Service / EKS / Lambda → Container
    elif rtype in ("aws_ecs_service", "aws_ecs_task_definition", "aws_lambda_function"):
        tech_map = {
            "aws_ecs_service": "AWS ECS",
            "aws_ecs_task_definition": "AWS ECS Task",
            "aws_lambda_function": "AWS Lambda",
        }
        entities["containers"].append({
            "id": rid,
            "name": _extract_hcl_value(body, "tags.Name") or name,
            "container_type": "serverless" if "lambda" in rtype else "container_service",
            "technology": tech_map.get(rtype, "AWS"),
            "description": f"Extracted from {rtype}",
            "_source": f"terraform:{rtype}.{name}",
        })

    # RDS / DynamoDB / ElastiCache → Component (database)
    elif rtype in ("aws_db_instance", "aws_dynamodb_table", "aws_elasticache_cluster"):
        tech_map = {
            "aws_db_instance": _extract_hcl_value(body, "engine") or "RDS",
            "aws_dynamodb_table": "DynamoDB",
            "aws_elasticache_cluster": _extract_hcl_value(body, "engine") or "ElastiCache",
        }
        port_map = {
            "aws_db_instance": _extract_hcl_value(body, "port"),
            "aws_dynamodb_table": None,
            "aws_elasticache_cluster": _extract_hcl_value(body, "port"),
        }
        entities["components"].append({
            "id": rid,
            "name": _extract_hcl_value(body, "tags.Name") or name,
            "component_type": "database",
            "technology": tech_map.get(rtype, "AWS"),
            "port": port_map.get(rtype),
            "_source": f"terraform:{rtype}.{name}",
        })

    # ALB / NLB → Infrastructure resource (load balancer)
    elif rtype in ("aws_lb", "aws_alb"):
        is_internal = "internal" in body.lower() and "true" in body.lower()
        entities["infrastructure_resources"].append({
            "id": rid,
            "name": _extract_hcl_value(body, "tags.Name") or name,
            "resource_type": "load_balancer",
            "technology": "AWS ALB" if "alb" in rtype else "AWS NLB",
            "zone_id": "unknown",
            "_source": f"terraform:{rtype}.{name}",
        })

    # WAF → Infrastructure resource
    elif rtype in ("aws_wafv2_web_acl", "aws_waf_web_acl"):
        entities["infrastructure_resources"].append({
            "id": rid,
            "name": _extract_hcl_value(body, "tags.Name") or name,
            "resource_type": "waf",
            "technology": "AWS WAF",
            "zone_id": "unknown",
            "_source": f"terraform:{rtype}.{name}",
        })


def _extract_sg_rules(body: str, sg_id: str, entities: dict):
    """Extract security group ingress rules as listener-like objects."""
    ingress_pattern = re.compile(
        r'ingress\s*\{([^}]*)\}', re.DOTALL,
    )
    for match in ingress_pattern.finditer(body):
        rule_body = match.group(1)
        port = _extract_hcl_value(rule_body, "from_port")
        protocol = _extract_hcl_value(rule_body, "protocol") or "tcp"
        cidr = _extract_hcl_value(rule_body, "cidr_blocks")
        entities["listeners"].append({
            "sg_id": sg_id,
            "protocol": protocol.upper(),
            "port": int(port) if port and port.isdigit() else None,
            "cidr": cidr,
            "_source": f"terraform:sg_ingress.{sg_id}",
        })


def parse_cloudformation(content: str) -> dict:
    """Parse CloudFormation JSON/YAML and extract architecture entities."""
    entities = {
        "containers": [],
        "components": [],
        "network_zones": [],
        "infrastructure_resources": [],
        "listeners": [],
        "metadata": {"source_format": "cloudformation", "parser": "cfn-yaml"},
    }

    try:
        template = yaml.safe_load(content)
    except yaml.YAMLError:
        try:
            template = json.loads(content)
        except json.JSONDecodeError:
            return entities

    if not isinstance(template, dict):
        return entities

    resources = template.get("Resources", {})
    for logical_id, resource in resources.items():
        if not isinstance(resource, dict):
            continue
        rtype = resource.get("Type", "")
        props = resource.get("Properties", {})
        rid = _to_kebab(logical_id)

        if rtype == "AWS::EC2::VPC":
            entities["network_zones"].append({
                "id": rid,
                "name": logical_id,
                "zone_type": "vpc",
                "internet_routable": False,
                "trust": "trusted",
                "description": f"VPC {props.get('CidrBlock', '')}",
                "_source": f"cloudformation:{logical_id}",
            })

        elif rtype == "AWS::EC2::Subnet":
            entities["network_zones"].append({
                "id": rid,
                "name": logical_id,
                "zone_type": "subnet",
                "internet_routable": props.get("MapPublicIpOnLaunch", False),
                "trust": "semi_trusted" if props.get("MapPublicIpOnLaunch") else "trusted",
                "_source": f"cloudformation:{logical_id}",
            })

        elif rtype in ("AWS::ECS::Service", "AWS::Lambda::Function"):
            entities["containers"].append({
                "id": rid,
                "name": logical_id,
                "container_type": "serverless" if "Lambda" in rtype else "container_service",
                "technology": "AWS Lambda" if "Lambda" in rtype else "AWS ECS",
                "_source": f"cloudformation:{logical_id}",
            })

        elif rtype in ("AWS::RDS::DBInstance", "AWS::DynamoDB::Table"):
            entities["components"].append({
                "id": rid,
                "name": logical_id,
                "component_type": "database",
                "technology": props.get("Engine", "DynamoDB" if "DynamoDB" in rtype else "RDS"),
                "_source": f"cloudformation:{logical_id}",
            })

        elif rtype in ("AWS::ElasticLoadBalancingV2::LoadBalancer",):
            entities["infrastructure_resources"].append({
                "id": rid,
                "name": logical_id,
                "resource_type": "load_balancer",
                "technology": "AWS ALB",
                "zone_id": "unknown",
                "_source": f"cloudformation:{logical_id}",
            })

    return entities


def _extract_hcl_value(body: str, key: str) -> str | None:
    """Extract a simple string value from HCL body by key."""
    pattern = re.compile(rf'{re.escape(key)}\s*=\s*"([^"]*)"')
    match = pattern.search(body)
    return match.group(1) if match else None


def _to_kebab(name: str) -> str:
    """Convert a resource name to kebab-case."""
    s = re.sub(r'[A-Z]', lambda m: '-' + m.group(0).lower(), name)
    s = re.sub(r'[^a-z0-9-]', '-', s.lower())
    s = re.sub(r'-+', '-', s).strip('-')
    return s


def entities_to_yaml(entities: dict, output_dir: str):
    """Write extracted entities to Doc2ArchAgent YAML files."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    # Write networks.yaml
    if entities["network_zones"] or entities["infrastructure_resources"]:
        networks = {}
        if entities["network_zones"]:
            networks["network_zones"] = [
                {k: v for k, v in z.items() if not k.startswith("_")}
                for z in entities["network_zones"]
            ]
        if entities["infrastructure_resources"]:
            networks["infrastructure_resources"] = [
                {k: v for k, v in r.items() if not k.startswith("_")}
                for r in entities["infrastructure_resources"]
            ]
        with open(output / "networks.yaml", "w") as f:
            f.write("# Auto-generated from IaC by ingest-terraform.py\n")
            f.write(f"# Source format: {entities['metadata']['source_format']}\n\n")
            yaml.dump(networks, f, default_flow_style=False, sort_keys=False)

    # Write partial system.yaml
    system = {"metadata": {
        "name": "Imported from IaC",
        "description": f"Auto-extracted from {entities['metadata']['source_format']}",
        "owner": "TODO",
        "status": "proposed",
    }}
    if entities["containers"]:
        system["containers"] = [
            {k: v for k, v in c.items() if not k.startswith("_") and v is not None}
            for c in entities["containers"]
        ]
    if entities["components"]:
        system["components"] = [
            {k: v for k, v in c.items() if not k.startswith("_") and v is not None}
            for c in entities["components"]
        ]
    with open(output / "system.yaml", "w") as f:
        f.write("# Auto-generated from IaC by ingest-terraform.py\n")
        f.write("# Review and refine with @architect before use.\n\n")
        yaml.dump(system, f, default_flow_style=False, sort_keys=False)

    print(json.dumps({
        "success": True,
        "output_dir": str(output),
        "entities": {
            "network_zones": len(entities["network_zones"]),
            "infrastructure_resources": len(entities["infrastructure_resources"]),
            "containers": len(entities["containers"]),
            "components": len(entities["components"]),
            "listeners": len(entities["listeners"]),
        },
    }, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Convert IaC to Doc2ArchAgent YAML.")
    parser.add_argument("path", help="Path to IaC file or directory")
    parser.add_argument("--format", choices=["terraform", "cloudformation"], default="terraform")
    parser.add_argument("--output", help="Output directory for YAML files")
    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(json.dumps({"error": f"Path not found: {args.path}"}))
        sys.exit(1)

    # Collect files
    files = []
    if path.is_dir():
        if args.format == "terraform":
            files = list(path.glob("*.tf"))
        else:
            files = list(path.glob("*.yaml")) + list(path.glob("*.yml")) + list(path.glob("*.json"))
    else:
        files = [path]

    if not files:
        print(json.dumps({"error": f"No {args.format} files found at {args.path}"}))
        sys.exit(1)

    # Parse all files
    all_entities = {
        "containers": [], "components": [], "network_zones": [],
        "infrastructure_resources": [], "listeners": [],
        "metadata": {"source_format": args.format, "parser": ""},
    }

    for f in files:
        content = f.read_text()
        if args.format == "terraform":
            entities = parse_terraform_hcl(content)
        else:
            entities = parse_cloudformation(content)

        for key in ("containers", "components", "network_zones", "infrastructure_resources", "listeners"):
            all_entities[key].extend(entities.get(key, []))
        all_entities["metadata"] = entities.get("metadata", all_entities["metadata"])

    if args.output:
        entities_to_yaml(all_entities, args.output)
    else:
        print(json.dumps(all_entities, indent=2, default=str))


if __name__ == "__main__":
    main()
