#!/usr/bin/env python3
# Copyright (c) 2026 Michael J. Read. All rights reserved.
# SPDX-License-Identifier: BUSL-1.1
"""Deterministic validation for Doc2ArchAgent pattern YAML files and catalogs.

Validates both legacy single-file patterns (.pattern.yaml) and new directory-
format patterns (pattern.meta.yaml + system.yaml/networks.yaml).

Usage:
    python tools/validate-patterns.py patterns/networks/
    python tools/validate-patterns.py patterns/products/
    python tools/validate-patterns.py patterns/networks/usa/standard-3tier.pattern.yaml
    python tools/validate-patterns.py patterns/products/messaging/ibm-mq/

Output:
    JSON to stdout: {"valid": bool, "errors": [...], "warnings": [...]}
"""

import json
import re
import sys
from pathlib import Path

import yaml

# --- Constants ---

KEBAB_CASE_RE = re.compile(r'^[a-z][a-z0-9]*(-[a-z0-9]+)*$')
SEMVER_RE = re.compile(r'^\d+\.\d+\.\d+$')

VALID_TRUST_LEVELS = {'trusted', 'semi_trusted', 'untrusted'}
VALID_ZONE_TYPES = {'external', 'dmz', 'private', 'management', 'data', 'custom'}
VALID_RESOURCE_TYPES = {'waf', 'secrets_manager', 'logging', 'monitoring', 'load_balancer', 'custom'}

REQUIRED_METADATA = ('id', 'name', 'category', 'version', 'description')
REQUIRED_ZONE_FIELDS = ('id', 'name', 'zone_type', 'internet_routable', 'trust')
REQUIRED_INFRA_FIELDS = ('id', 'name', 'resource_type', 'technology', 'zone_id')
REQUIRED_CONTAINER_FIELDS = ('id', 'name', 'container_type', 'technology')
REQUIRED_COMPONENT_FIELDS = ('id', 'name', 'container_id', 'component_type', 'technology')
REQUIRED_LISTENER_FIELDS = ('id', 'protocol', 'port', 'tls_enabled', 'authn_mechanism', 'authz_required')

REQUIRED_META_FIELDS = ('id', 'type', 'name', 'version', 'description')
VALID_PATTERN_TYPES = {'product', 'network'}
VALID_BINDING_TYPES = {'container', 'component', 'zone', 'infrastructure_resource'}


# ============================================================================
# New-format validation (directory with pattern.meta.yaml)
# ============================================================================

def validate_pattern_meta(meta_path: Path) -> dict:
    """Validate a pattern.meta.yaml file."""
    errors: list[str] = []
    warnings: list[str] = []
    fname = meta_path.name

    try:
        with open(meta_path) as f:
            data = yaml.safe_load(f) or {}
    except Exception as e:
        return {"valid": False, "errors": [f"{fname}: cannot load YAML: {e}"], "warnings": []}

    pattern = data.get('pattern')
    if not isinstance(pattern, dict):
        return {"valid": False, "errors": [f"{fname}: missing top-level 'pattern' key"], "warnings": []}

    # Required fields
    for field in REQUIRED_META_FIELDS:
        if not pattern.get(field):
            errors.append(f"{fname}: pattern.{field} is required")

    pid = pattern.get('id', '')
    if pid and not KEBAB_CASE_RE.match(pid):
        warnings.append(f"{fname}: pattern.id '{pid}' is not kebab-case")

    ptype = pattern.get('type', '')
    if ptype and ptype not in VALID_PATTERN_TYPES:
        errors.append(f"{fname}: pattern.type '{ptype}' must be one of {VALID_PATTERN_TYPES}")

    version = pattern.get('version', '')
    if version and not SEMVER_RE.match(str(version)):
        errors.append(f"{fname}: pattern.version '{version}' is not valid semver (expected X.Y.Z)")

    # Binding points validation
    for bp in pattern.get('binding_points', []):
        if not bp.get('id'):
            errors.append(f"{fname}: binding_point missing 'id'")
        if bp.get('type') and bp['type'] not in VALID_BINDING_TYPES:
            errors.append(f"{fname}: binding_point '{bp.get('id', '?')}' has invalid type '{bp['type']}'")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings,
            "pattern_type": ptype, "pattern_id": pid}


def validate_new_format_dir(pattern_dir: Path) -> dict:
    """Validate a new-format pattern directory."""
    errors: list[str] = []
    warnings: list[str] = []
    dirname = pattern_dir.name

    meta_path = pattern_dir / "pattern.meta.yaml"
    if not meta_path.exists():
        return {"valid": False,
                "errors": [f"{dirname}/: missing pattern.meta.yaml"],
                "warnings": []}

    # Validate metadata
    meta_result = validate_pattern_meta(meta_path)
    errors.extend(meta_result['errors'])
    warnings.extend(meta_result['warnings'])

    ptype = meta_result.get('pattern_type', '')

    # Validate the corresponding YAML
    if ptype == 'network':
        networks_path = pattern_dir / "networks.yaml"
        if not networks_path.exists():
            errors.append(f"{dirname}/: network pattern missing networks.yaml")
        else:
            try:
                with open(networks_path) as f:
                    net_data = yaml.safe_load(f) or {}
                _validate_network_content(net_data, f"{dirname}/networks.yaml", errors, warnings)
            except Exception as e:
                errors.append(f"{dirname}/networks.yaml: cannot load: {e}")

    elif ptype == 'product':
        system_path = pattern_dir / "system.yaml"
        if not system_path.exists():
            errors.append(f"{dirname}/: product pattern missing system.yaml")
        else:
            try:
                with open(system_path) as f:
                    sys_data = yaml.safe_load(f) or {}
                _validate_product_system(sys_data, f"{dirname}/system.yaml", errors, warnings)
            except Exception as e:
                errors.append(f"{dirname}/system.yaml: cannot load: {e}")

    # Cross-validate: binding_points reference real IDs
    if not errors:
        _cross_validate_bindings(pattern_dir, meta_result, errors, warnings)

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}


def _validate_network_content(net_data: dict, fname: str, errors: list, warnings: list):
    """Validate networks.yaml content (shared between old and new format)."""
    zones = net_data.get('network_zones', [])
    if not zones:
        errors.append(f"{fname}: network_zones must be non-empty")
        return

    zone_ids: set[str] = set()
    for zone in zones:
        if not isinstance(zone, dict):
            continue
        zid = zone.get('id', '?')
        for field in REQUIRED_ZONE_FIELDS:
            if field not in zone:
                errors.append(f"{fname}: network_zone '{zid}': required field '{field}' is missing")
        if zone.get('trust') and zone['trust'] not in VALID_TRUST_LEVELS:
            errors.append(f"{fname}: network_zone '{zid}': trust '{zone['trust']}' is not valid")
        if zid != '?' and not KEBAB_CASE_RE.match(zid):
            warnings.append(f"{fname}: network_zone id '{zid}' is not kebab-case")
        if zid in zone_ids:
            errors.append(f"{fname}: duplicate network_zone id '{zid}'")
        zone_ids.add(zid)

    for res in net_data.get('infrastructure_resources', []):
        if not isinstance(res, dict):
            continue
        rid = res.get('id', '?')
        for field in REQUIRED_INFRA_FIELDS:
            if not res.get(field):
                errors.append(f"{fname}: infrastructure_resource '{rid}': required field '{field}' is missing")
        if res.get('zone_id') and res['zone_id'] not in zone_ids:
            errors.append(f"{fname}: infrastructure_resource '{rid}': zone_id '{res['zone_id']}' does not exist in pattern zones")
        if rid != '?' and not KEBAB_CASE_RE.match(rid):
            warnings.append(f"{fname}: infrastructure_resource id '{rid}' is not kebab-case")


def _validate_product_system(sys_data: dict, fname: str, errors: list, warnings: list):
    """Validate product pattern system.yaml content."""
    # Metadata
    metadata = sys_data.get('metadata', {})
    if not isinstance(metadata, dict):
        errors.append(f"{fname}: metadata is missing or not a mapping")
    else:
        for field in ('name', 'description', 'owner', 'status'):
            if not metadata.get(field):
                errors.append(f"{fname}: metadata.{field} is required")

    # Contexts
    contexts = sys_data.get('contexts', [])
    if not contexts:
        warnings.append(f"{fname}: no contexts defined")

    # Containers
    containers = sys_data.get('containers', [])
    if not containers:
        errors.append(f"{fname}: containers must be non-empty")
        return

    container_ids: set[str] = set()
    for ctr in containers:
        if not isinstance(ctr, dict):
            continue
        cid = ctr.get('id', '?')
        for field in ('id', 'name', 'container_type', 'technology'):
            if not ctr.get(field):
                errors.append(f"{fname}: container '{cid}': required field '{field}' is missing")
        if cid != '?' and not KEBAB_CASE_RE.match(cid):
            warnings.append(f"{fname}: container id '{cid}' is not kebab-case")
        if cid in container_ids:
            errors.append(f"{fname}: duplicate container id '{cid}'")
        container_ids.add(cid)

    # Components
    components = sys_data.get('components', [])
    if not components:
        errors.append(f"{fname}: components must be non-empty")
        return

    component_ids: set[str] = set()
    listeners_by_component: dict[str, set[str]] = {}
    for comp in components:
        if not isinstance(comp, dict):
            continue
        compid = comp.get('id', '?')
        for field in REQUIRED_COMPONENT_FIELDS:
            if not comp.get(field):
                errors.append(f"{fname}: component '{compid}': required field '{field}' is missing")
        if comp.get('container_id') and comp['container_id'] not in container_ids:
            errors.append(f"{fname}: component '{compid}': container_id '{comp['container_id']}' does not exist in containers")
        if compid != '?' and not KEBAB_CASE_RE.match(compid):
            warnings.append(f"{fname}: component id '{compid}' is not kebab-case")
        if compid in component_ids:
            errors.append(f"{fname}: duplicate component id '{compid}'")
        component_ids.add(compid)

        # Listeners
        listener_ids: set[str] = set()
        for listener in comp.get('listeners', []):
            if not isinstance(listener, dict):
                continue
            lid = listener.get('id', '?')
            for field in REQUIRED_LISTENER_FIELDS:
                if field not in listener:
                    errors.append(f"{fname}: listener '{lid}' on component '{compid}': required field '{field}' is missing")
            if lid in listener_ids:
                errors.append(f"{fname}: duplicate listener id '{lid}' on component '{compid}'")
            listener_ids.add(lid)
        listeners_by_component[compid] = listener_ids

    # Component relationships
    for rel in sys_data.get('component_relationships', []):
        if not isinstance(rel, dict):
            continue
        relid = rel.get('id', '?')
        src = rel.get('source_component', '')
        tgt = rel.get('target_component', '')
        if src and src not in component_ids:
            errors.append(f"{fname}: component_relationship '{relid}': source_component '{src}' does not exist")
        if tgt and tgt not in component_ids:
            errors.append(f"{fname}: component_relationship '{relid}': target_component '{tgt}' does not exist")
        lref = rel.get('target_listener_ref', '')
        if lref and tgt and tgt in listeners_by_component:
            if lref not in listeners_by_component[tgt]:
                errors.append(f"{fname}: component_relationship '{relid}': target_listener_ref '{lref}' does not exist on component '{tgt}'")


def _cross_validate_bindings(pattern_dir: Path, meta_result: dict, errors: list, warnings: list):
    """Verify binding_points reference real entity IDs."""
    ptype = meta_result.get('pattern_type', '')
    meta_path = pattern_dir / "pattern.meta.yaml"
    with open(meta_path) as f:
        meta = yaml.safe_load(f)

    binding_points = meta.get('pattern', {}).get('binding_points', [])
    if not binding_points:
        return

    if ptype == 'network':
        networks_path = pattern_dir / "networks.yaml"
        if not networks_path.exists():
            return
        with open(networks_path) as f:
            data = yaml.safe_load(f) or {}
        all_ids = {z['id'] for z in data.get('network_zones', []) if 'id' in z}
        all_ids |= {r['id'] for r in data.get('infrastructure_resources', []) if 'id' in r}
    elif ptype == 'product':
        system_path = pattern_dir / "system.yaml"
        if not system_path.exists():
            return
        with open(system_path) as f:
            data = yaml.safe_load(f) or {}
        all_ids = {c['id'] for c in data.get('containers', []) if 'id' in c}
        all_ids |= {c['id'] for c in data.get('components', []) if 'id' in c}
    else:
        return

    for bp in binding_points:
        if bp.get('id') and bp['id'] not in all_ids:
            warnings.append(
                f"pattern.meta.yaml: binding_point '{bp['id']}' not found in pattern YAML"
            )


# ============================================================================
# Legacy format validation (single .pattern.yaml file)
# ============================================================================

def validate_pattern_file(path: Path) -> dict:
    """Validate a single .pattern.yaml file (legacy format)."""
    errors: list[str] = []
    warnings: list[str] = []
    fname = path.name

    try:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
    except Exception as e:
        return {"valid": False, "errors": [f"{fname}: cannot load YAML: {e}"], "warnings": []}

    pattern = data.get('pattern')
    if not isinstance(pattern, dict):
        return {"valid": False, "errors": [f"{fname}: missing top-level 'pattern' key"], "warnings": []}

    # --- Metadata validation ---
    metadata = pattern.get('metadata', {})
    if not isinstance(metadata, dict):
        errors.append(f"{fname}: metadata is missing or not a mapping")
        return {"valid": False, "errors": errors, "warnings": warnings}

    for field in REQUIRED_METADATA:
        if not metadata.get(field):
            errors.append(f"{fname}: metadata.{field} is required")

    pid = metadata.get('id', '')
    if pid and not KEBAB_CASE_RE.match(pid):
        warnings.append(f"{fname}: metadata.id '{pid}' is not kebab-case")

    version = metadata.get('version', '')
    if version and not SEMVER_RE.match(str(version)):
        errors.append(f"{fname}: metadata.version '{version}' is not valid semver (expected X.Y.Z)")

    # Detect pattern type by content
    has_zones = 'network_zones' in pattern
    has_containers = 'containers' in pattern
    is_network = has_zones
    is_product = has_containers

    if not is_network and not is_product:
        errors.append(f"{fname}: pattern must have either 'network_zones' (network pattern) or 'containers' (product pattern)")
        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

    if is_network:
        _validate_network_pattern(pattern, fname, errors, warnings)
    if is_product:
        _validate_product_pattern(pattern, fname, errors, warnings)

    # Add deprecation warning for legacy format
    warnings.append(f"{fname}: legacy .pattern.yaml format — consider migrating to directory format with 'python tools/migrate-pattern.py {path}'")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}


def _validate_network_pattern(pattern: dict, fname: str, errors: list, warnings: list):
    """Validate legacy network pattern content."""
    net_data = {
        'network_zones': pattern.get('network_zones', []),
        'infrastructure_resources': pattern.get('infrastructure_resources', []),
    }
    _validate_network_content(net_data, fname, errors, warnings)


def _validate_product_pattern(pattern: dict, fname: str, errors: list, warnings: list):
    """Validate legacy product pattern content."""
    containers = pattern.get('containers', [])
    if not containers:
        errors.append(f"{fname}: containers must be non-empty")
        return

    container_ids: set[str] = set()
    for ctr in containers:
        if not isinstance(ctr, dict):
            continue
        cid = ctr.get('id', '?')
        for field in REQUIRED_CONTAINER_FIELDS:
            if not ctr.get(field):
                errors.append(f"{fname}: container '{cid}': required field '{field}' is missing")
        if cid != '?' and not KEBAB_CASE_RE.match(cid):
            warnings.append(f"{fname}: container id '{cid}' is not kebab-case")
        if cid in container_ids:
            errors.append(f"{fname}: duplicate container id '{cid}'")
        container_ids.add(cid)

    # Components
    components = pattern.get('components', [])
    if not components:
        errors.append(f"{fname}: components must be non-empty")
        return

    component_ids: set[str] = set()
    listeners_by_component: dict[str, set[str]] = {}
    for comp in components:
        if not isinstance(comp, dict):
            continue
        compid = comp.get('id', '?')
        for field in REQUIRED_COMPONENT_FIELDS:
            if not comp.get(field):
                errors.append(f"{fname}: component '{compid}': required field '{field}' is missing")
        if comp.get('container_id') and comp['container_id'] not in container_ids:
            errors.append(f"{fname}: component '{compid}': container_id '{comp['container_id']}' does not exist in pattern containers")
        if compid != '?' and not KEBAB_CASE_RE.match(compid):
            warnings.append(f"{fname}: component id '{compid}' is not kebab-case")
        if compid in component_ids:
            errors.append(f"{fname}: duplicate component id '{compid}'")
        component_ids.add(compid)

        # Listeners
        listener_ids: set[str] = set()
        for listener in comp.get('listeners', []):
            if not isinstance(listener, dict):
                continue
            lid = listener.get('id', '?')
            for field in REQUIRED_LISTENER_FIELDS:
                if field not in listener:
                    errors.append(f"{fname}: listener '{lid}' on component '{compid}': required field '{field}' is missing")
            if lid in listener_ids:
                errors.append(f"{fname}: duplicate listener id '{lid}' on component '{compid}'")
            listener_ids.add(lid)
        listeners_by_component[compid] = listener_ids

    # Component relationships
    for rel in pattern.get('component_relationships', []):
        if not isinstance(rel, dict):
            continue
        relid = rel.get('id', '?')
        src = rel.get('source_component', '')
        tgt = rel.get('target_component', '')
        if src and src not in component_ids:
            errors.append(f"{fname}: component_relationship '{relid}': source_component '{src}' does not exist in pattern")
        if tgt and tgt not in component_ids:
            errors.append(f"{fname}: component_relationship '{relid}': target_component '{tgt}' does not exist in pattern")
        lref = rel.get('target_listener_ref', '')
        if lref and tgt and tgt in listeners_by_component:
            if lref not in listeners_by_component[tgt]:
                errors.append(f"{fname}: component_relationship '{relid}': target_listener_ref '{lref}' does not exist on component '{tgt}'")


# ============================================================================
# Catalog validation
# ============================================================================

def validate_catalog(catalog_path: Path) -> dict:
    """Validate a _catalog.yaml file and check referenced pattern files/dirs."""
    errors: list[str] = []
    warnings: list[str] = []
    fname = catalog_path.name
    base_dir = catalog_path.parent

    try:
        with open(catalog_path) as f:
            data = yaml.safe_load(f) or {}
    except Exception as e:
        return {"valid": False, "errors": [f"{fname}: cannot load: {e}"], "warnings": []}

    catalog = data.get('catalog')
    if not isinstance(catalog, dict):
        return {"valid": False, "errors": [f"{fname}: missing top-level 'catalog' key"], "warnings": []}

    if not catalog.get('type'):
        errors.append(f"{fname}: catalog.type is required")
    tree = catalog.get('tree', [])
    if not tree:
        warnings.append(f"{fname}: catalog tree is empty")

    # Collect all referenced pattern IDs and files/dirs
    seen_ids: set[str] = set()
    referenced_paths: set[str] = set()

    def _walk_tree(nodes: list, path: str = ""):
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_path = f"{path}/{node.get('name', '?')}"
            key = node.get('key', '')
            if key and not KEBAB_CASE_RE.match(key):
                warnings.append(f"{fname}: tree node '{node_path}' key '{key}' is not kebab-case")
            for pat in node.get('patterns', []):
                if not isinstance(pat, dict):
                    continue
                pid = pat.get('id', '')
                pfile = pat.get('file', '')
                pdir = pat.get('dir', '')
                if not pid:
                    errors.append(f"{fname}: pattern in '{node_path}' missing 'id'")
                if not pfile and not pdir:
                    errors.append(f"{fname}: pattern '{pid}' in '{node_path}' missing 'file' or 'dir'")
                if pid in seen_ids:
                    errors.append(f"{fname}: duplicate pattern id '{pid}' in catalog")
                seen_ids.add(pid)
                if pfile:
                    referenced_paths.add(pfile)
                    full_path = base_dir / pfile
                    if not full_path.exists():
                        errors.append(f"{fname}: pattern '{pid}' references non-existent file '{pfile}'")
                if pdir:
                    referenced_paths.add(pdir)
                    full_path = base_dir / pdir
                    if not full_path.exists() or not full_path.is_dir():
                        errors.append(f"{fname}: pattern '{pid}' references non-existent directory '{pdir}'")
                    elif not (full_path / "pattern.meta.yaml").exists():
                        errors.append(f"{fname}: pattern '{pid}' directory '{pdir}' missing pattern.meta.yaml")
            _walk_tree(node.get('children', []), node_path)

    _walk_tree(tree)

    # Check for pattern files/dirs on disk not in catalog
    for pattern_file in base_dir.rglob('*.pattern.yaml'):
        rel = str(pattern_file.relative_to(base_dir))
        if rel not in referenced_paths:
            warnings.append(f"{fname}: pattern file '{rel}' exists on disk but is not in the catalog")

    for d in base_dir.iterdir():
        if d.is_dir() and not d.name.startswith('_'):
            for sub in d.rglob("pattern.meta.yaml"):
                pattern_dir = sub.parent
                rel = str(pattern_dir.relative_to(base_dir))
                if rel not in referenced_paths:
                    # Check if referenced by file (legacy)
                    legacy = rel + ".pattern.yaml"
                    if legacy not in referenced_paths:
                        warnings.append(f"{fname}: pattern directory '{rel}' exists on disk but is not in the catalog")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}


# ============================================================================
# Directory validation
# ============================================================================

def validate_directory(dir_path: Path) -> dict:
    """Validate all patterns and catalog in a directory."""
    all_errors: list[str] = []
    all_warnings: list[str] = []

    # Validate catalog
    catalog_path = dir_path / '_catalog.yaml'
    if catalog_path.exists():
        result = validate_catalog(catalog_path)
        all_errors.extend(result['errors'])
        all_warnings.extend(result['warnings'])
    else:
        all_warnings.append(f"No _catalog.yaml found in {dir_path}")

    # Validate all legacy pattern files
    for pattern_file in sorted(dir_path.rglob('*.pattern.yaml')):
        result = validate_pattern_file(pattern_file)
        all_errors.extend(result['errors'])
        all_warnings.extend(result['warnings'])

    # Validate all new-format pattern directories
    for meta_file in sorted(dir_path.rglob('pattern.meta.yaml')):
        pattern_dir = meta_file.parent
        result = validate_new_format_dir(pattern_dir)
        all_errors.extend(result['errors'])
        all_warnings.extend(result['warnings'])

    return {
        "valid": len(all_errors) == 0,
        "errors": all_errors,
        "warnings": all_warnings,
    }


def main():
    if len(sys.argv) < 2:
        print(json.dumps({
            "valid": False,
            "errors": ["Usage: python tools/validate-patterns.py <path> (directory, .pattern.yaml, or pattern directory)"],
            "warnings": [],
        }))
        sys.exit(1)

    target = Path(sys.argv[1])

    if target.is_file() and target.name.endswith('.pattern.yaml'):
        result = validate_pattern_file(target)
    elif target.is_file() and target.name == '_catalog.yaml':
        result = validate_catalog(target)
    elif target.is_file() and target.name == 'pattern.meta.yaml':
        result = validate_new_format_dir(target.parent)
    elif target.is_dir() and (target / 'pattern.meta.yaml').exists():
        result = validate_new_format_dir(target)
    elif target.is_dir():
        result = validate_directory(target)
    else:
        result = {"valid": False, "errors": [f"Unknown target: {target}"], "warnings": []}

    print(json.dumps(result, indent=2))
    sys.exit(0 if result['valid'] else 1)


if __name__ == '__main__':
    main()
