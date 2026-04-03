#!/usr/bin/env python3
# Copyright (c) 2026 Michael J. Read. All rights reserved.
# SPDX-License-Identifier: BUSL-1.1
"""Deterministic OpenAPI/Swagger → Doc2ArchAgent YAML converter.

Parses OpenAPI 3.x and Swagger 2.0 specs to extract:
  - Paths/operations → Component listeners
  - Security schemes → authn_mechanism values
  - Servers → Deployment metadata
  - Request/response schemas → Data entities

Usage:
    python tools/ingest-openapi.py <openapi-spec.yaml> [--output <dir>]

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


def parse_openapi(content: str) -> dict:
    """Parse an OpenAPI/Swagger spec and extract architecture entities."""
    try:
        spec = yaml.safe_load(content)
    except yaml.YAMLError:
        try:
            spec = json.loads(content)
        except json.JSONDecodeError:
            return {"error": "Cannot parse as YAML or JSON"}

    if not isinstance(spec, dict):
        return {"error": "Spec is not a valid mapping"}

    version = spec.get("openapi", spec.get("swagger", "unknown"))
    info = spec.get("info", {})

    entities = {
        "metadata": {
            "source_format": "openapi",
            "openapi_version": version,
            "api_title": info.get("title", "Unknown API"),
            "api_version": info.get("version", "0.0.0"),
        },
        "components": [],
        "listeners": [],
        "data_entities": [],
        "security_schemes": [],
    }

    # Extract security schemes
    security_defs = {}
    if "components" in spec and "securitySchemes" in spec["components"]:
        security_defs = spec["components"]["securitySchemes"]
    elif "securityDefinitions" in spec:  # Swagger 2.0
        security_defs = spec["securityDefinitions"]

    for scheme_name, scheme in security_defs.items():
        scheme_type = scheme.get("type", "unknown")
        authn = _map_security_scheme(scheme_type, scheme)
        entities["security_schemes"].append({
            "id": _to_kebab(scheme_name),
            "name": scheme_name,
            "type": scheme_type,
            "authn_mechanism": authn,
            "_source": f"openapi:securitySchemes.{scheme_name}",
        })

    # Determine default auth mechanism
    global_security = spec.get("security", [])
    default_authn = "none"
    if global_security and security_defs:
        first_scheme_name = list(global_security[0].keys())[0] if global_security[0] else None
        if first_scheme_name and first_scheme_name in security_defs:
            default_authn = _map_security_scheme(
                security_defs[first_scheme_name].get("type", ""),
                security_defs[first_scheme_name],
            )

    # Extract server info for listeners
    servers = spec.get("servers", [])
    if not servers and "host" in spec:  # Swagger 2.0
        scheme = spec.get("schemes", ["https"])[0]
        servers = [{"url": f"{scheme}://{spec['host']}{spec.get('basePath', '')}"}]

    # Determine port and TLS from server URLs
    port = 443
    tls_enabled = True
    for server in servers:
        url = server.get("url", "")
        if "http://" in url:
            tls_enabled = False
            port = 80
        host_part = url.split("//")[-1]
        if ":" in host_part:
            parts = host_part.split(":")
            if len(parts) >= 2:
                port_str = parts[1].split("/")[0]
                if port_str.isdigit():
                    port = int(port_str)

    # Extract paths as listener endpoints
    paths = spec.get("paths", {})
    api_id = _to_kebab(info.get("title", "api"))

    entities["components"].append({
        "id": api_id,
        "name": info.get("title", "API"),
        "component_type": "api",
        "technology": f"OpenAPI {version}",
        "description": info.get("description", ""),
        "listeners": [{
            "id": f"{api_id}-listener",
            "protocol": "HTTPS" if tls_enabled else "HTTP",
            "port": port,
            "tls_enabled": tls_enabled,
            "authn_mechanism": default_authn,
            "authz_required": default_authn != "none",
        }],
        "endpoints": [],
        "_source": f"openapi:info.title",
    })

    # Extract individual endpoints
    for path, methods in paths.items():
        if not isinstance(methods, dict):
            continue
        for method, operation in methods.items():
            if method.startswith("x-") or method == "parameters":
                continue
            if not isinstance(operation, dict):
                continue
            op_id = operation.get("operationId", f"{method}-{path}")
            entities["components"][0]["endpoints"].append({
                "path": path,
                "method": method.upper(),
                "operation_id": op_id,
                "summary": operation.get("summary", ""),
                "has_auth": bool(operation.get("security", global_security)),
            })

    # Extract schema definitions as data entities
    schemas = {}
    if "components" in spec and "schemas" in spec["components"]:
        schemas = spec["components"]["schemas"]
    elif "definitions" in spec:  # Swagger 2.0
        schemas = spec["definitions"]

    for schema_name, schema_def in schemas.items():
        if not isinstance(schema_def, dict):
            continue
        entities["data_entities"].append({
            "id": _to_kebab(schema_name),
            "name": schema_name,
            "description": schema_def.get("description", ""),
            "classification": "internal",  # Default; user should review
            "properties": list(schema_def.get("properties", {}).keys()),
            "_source": f"openapi:schemas.{schema_name}",
        })

    return entities


def _map_security_scheme(scheme_type: str, scheme: dict) -> str:
    """Map OpenAPI security scheme types to Doc2ArchAgent authn_mechanism values."""
    mapping = {
        "oauth2": "oauth2",
        "http": "basic" if scheme.get("scheme") == "basic" else "bearer",
        "apiKey": "api_key",
        "openIdConnect": "oidc",
        "mutualTLS": "mtls",
    }
    return mapping.get(scheme_type, "api_key")


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

    system = {
        "metadata": {
            "name": entities["metadata"].get("api_title", "Imported API"),
            "description": f"Auto-extracted from OpenAPI {entities['metadata'].get('openapi_version', '')}",
            "owner": "TODO",
            "status": "proposed",
        },
    }

    if entities["components"]:
        system["components"] = []
        for comp in entities["components"]:
            clean = {k: v for k, v in comp.items() if not k.startswith("_")}
            system["components"].append(clean)

    if entities["data_entities"]:
        system["data_entities"] = [
            {k: v for k, v in d.items() if not k.startswith("_")}
            for d in entities["data_entities"]
        ]

    with open(output / "system.yaml", "w") as f:
        f.write("# Auto-generated from OpenAPI spec by ingest-openapi.py\n")
        f.write("# Review and refine with @architect before use.\n\n")
        yaml.dump(system, f, default_flow_style=False, sort_keys=False)

    print(json.dumps({
        "success": True,
        "output_dir": str(output),
        "entities": {
            "components": len(entities["components"]),
            "data_entities": len(entities["data_entities"]),
            "security_schemes": len(entities["security_schemes"]),
            "endpoints": sum(len(c.get("endpoints", [])) for c in entities["components"]),
        },
    }, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Convert OpenAPI/Swagger to Doc2ArchAgent YAML.")
    parser.add_argument("spec", help="Path to OpenAPI/Swagger spec file")
    parser.add_argument("--output", help="Output directory for YAML files")
    args = parser.parse_args()

    path = Path(args.spec)
    if not path.exists():
        print(json.dumps({"error": f"File not found: {args.spec}"}))
        sys.exit(1)

    entities = parse_openapi(path.read_text())

    if "error" in entities:
        print(json.dumps(entities))
        sys.exit(1)

    if args.output:
        entities_to_yaml(entities, args.output)
    else:
        print(json.dumps(entities, indent=2, default=str))


if __name__ == "__main__":
    main()
