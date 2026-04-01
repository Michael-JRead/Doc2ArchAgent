#!/usr/bin/env python3
# Copyright (c) 2026 Michael J. Read. All rights reserved.
# SPDX-License-Identifier: BUSL-1.1
"""Deterministic schema validation for Doc2ArchAgent YAML files.

Implements the Separation Principle: validation is pure code, no LLM involvement.
Same input always produces same output.

Usage:
    python tools/validate.py architecture/<system-id>/system.yaml [architecture/networks.yaml]

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

VALID_STATUSES = {'proposed', 'active', 'deprecated', 'decommissioned'}
VALID_DEPLOYMENT_STATUSES = {'proposed', 'approved', 'active', 'deprecated'}
VALID_TRUST_LEVELS = {'trusted', 'semi_trusted', 'untrusted'}


def validate(system_path: str, networks_path: str | None = None) -> dict:
    """Run all validation checks and return results as dict."""
    errors: list[str] = []
    warnings: list[str] = []

    # --- Load files ---
    try:
        with open(system_path) as f:
            system = yaml.safe_load(f) or {}
    except Exception as e:
        return {"valid": False, "errors": [f"Cannot load system YAML: {e}"], "warnings": []}

    networks = {}
    if networks_path:
        try:
            with open(networks_path) as f:
                networks = yaml.safe_load(f) or {}
        except Exception as e:
            warnings.append(f"Cannot load networks YAML: {e}")

    # --- Build lookup tables ---
    contexts = {c['id']: c for c in system.get('contexts', []) if isinstance(c, dict) and 'id' in c}
    containers = {c['id']: c for c in system.get('containers', []) if isinstance(c, dict) and 'id' in c}
    components = {}
    listeners_by_component = {}
    for comp in system.get('components', []):
        if isinstance(comp, dict) and 'id' in comp:
            components[comp['id']] = comp
            for listener in comp.get('listeners', []):
                if isinstance(listener, dict) and 'id' in listener:
                    listeners_by_component.setdefault(comp['id'], {})[listener['id']] = listener

    zones = {z['id']: z for z in networks.get('network_zones', []) if isinstance(z, dict) and 'id' in z}
    external_systems = {e['id']: e for e in system.get('external_systems', []) if isinstance(e, dict) and 'id' in e}

    # --- 1. Metadata required fields ---
    metadata = system.get('metadata', {})
    if not isinstance(metadata, dict):
        errors.append("metadata: missing or not a mapping")
    else:
        for field in ('name', 'description', 'owner', 'status'):
            if not metadata.get(field):
                errors.append(f"metadata.{field}: required field is missing or empty")
        if metadata.get('status') and metadata['status'] not in VALID_STATUSES:
            errors.append(f"metadata.status: '{metadata['status']}' is not a valid status ({', '.join(sorted(VALID_STATUSES))})")

    # --- 2. Context required fields + unique IDs ---
    _check_unique_ids('context', system.get('contexts', []), errors)
    for ctx in system.get('contexts', []):
        if not isinstance(ctx, dict):
            continue
        for field in ('id', 'name', 'description'):
            if not ctx.get(field):
                errors.append(f"context '{ctx.get('id', '?')}': required field '{field}' is missing")
        if 'internal' not in ctx:
            errors.append(f"context '{ctx.get('id', '?')}': required field 'internal' is missing")
        _check_kebab_case(ctx.get('id', ''), 'context', warnings)

    # --- 3. Container required fields + referential integrity ---
    _check_unique_ids('container', system.get('containers', []), errors)
    for ctr in system.get('containers', []):
        if not isinstance(ctr, dict):
            continue
        for field in ('id', 'name', 'context_id', 'container_type', 'technology'):
            if not ctr.get(field):
                errors.append(f"container '{ctr.get('id', '?')}': required field '{field}' is missing")
        if ctr.get('context_id') and ctr['context_id'] not in contexts:
            errors.append(f"container '{ctr.get('id', '?')}': references non-existent context '{ctr['context_id']}'")
        _check_kebab_case(ctr.get('id', ''), 'container', warnings)

    # --- 4. Component required fields + referential integrity ---
    _check_unique_ids('component', system.get('components', []), errors)
    for comp in system.get('components', []):
        if not isinstance(comp, dict):
            continue
        for field in ('id', 'name', 'container_id', 'component_type', 'technology'):
            if not comp.get(field):
                errors.append(f"component '{comp.get('id', '?')}': required field '{field}' is missing")
        if comp.get('container_id') and comp['container_id'] not in containers:
            errors.append(f"component '{comp.get('id', '?')}': references non-existent container '{comp['container_id']}'")
        _check_kebab_case(comp.get('id', ''), 'component', warnings)

        # Listener required fields
        for listener in comp.get('listeners', []):
            if not isinstance(listener, dict):
                continue
            for field in ('id', 'protocol', 'port', 'tls_enabled', 'authn_mechanism', 'authz_required'):
                if field not in listener:
                    errors.append(f"listener '{listener.get('id', '?')}' on component '{comp.get('id', '?')}': required field '{field}' is missing")

    # --- 5. Context relationship referential integrity ---
    for rel in system.get('context_relationships', []):
        if not isinstance(rel, dict):
            continue
        _check_kebab_case(rel.get('id', ''), 'context_relationship', warnings)
        if rel.get('source_context') and rel['source_context'] not in contexts:
            errors.append(f"context_relationship '{rel.get('id', '?')}': source_context '{rel['source_context']}' does not exist")
        if rel.get('target_context') and rel['target_context'] not in contexts:
            errors.append(f"context_relationship '{rel.get('id', '?')}': target_context '{rel['target_context']}' does not exist")

    # --- 6. Container relationship referential integrity ---
    for rel in system.get('container_relationships', []):
        if not isinstance(rel, dict):
            continue
        _check_kebab_case(rel.get('id', ''), 'container_relationship', warnings)
        if rel.get('source_container') and rel['source_container'] not in containers:
            errors.append(f"container_relationship '{rel.get('id', '?')}': source_container '{rel['source_container']}' does not exist")
        if rel.get('target_container') and rel['target_container'] not in containers:
            errors.append(f"container_relationship '{rel.get('id', '?')}': target_container '{rel['target_container']}' does not exist")

    # --- 7. Component relationship referential integrity ---
    for rel in system.get('component_relationships', []):
        if not isinstance(rel, dict):
            continue
        _check_kebab_case(rel.get('id', ''), 'component_relationship', warnings)
        src = rel.get('source_component', '')
        tgt = rel.get('target_component', '')
        if src and src not in components:
            errors.append(f"component_relationship '{rel.get('id', '?')}': source_component '{src}' does not exist")
        if tgt and tgt not in components:
            errors.append(f"component_relationship '{rel.get('id', '?')}': target_component '{tgt}' does not exist")
        # Check target_listener_ref
        listener_ref = rel.get('target_listener_ref', '')
        if listener_ref and tgt:
            target_listeners = listeners_by_component.get(tgt, {})
            if listener_ref not in target_listeners:
                errors.append(
                    f"component_relationship '{rel.get('id', '?')}': target_listener_ref '{listener_ref}' "
                    f"does not exist on component '{tgt}'"
                )

    # --- 8. Network zone required fields (if networks.yaml provided) ---
    if networks:
        _check_unique_ids('network_zone', networks.get('network_zones', []), errors)
        for zone in networks.get('network_zones', []):
            if not isinstance(zone, dict):
                continue
            for field in ('id', 'name', 'zone_type', 'internet_routable', 'trust'):
                if field not in zone:
                    errors.append(f"network_zone '{zone.get('id', '?')}': required field '{field}' is missing")
            if zone.get('trust') and zone['trust'] not in VALID_TRUST_LEVELS:
                errors.append(f"network_zone '{zone.get('id', '?')}': trust '{zone['trust']}' is not valid ({', '.join(sorted(VALID_TRUST_LEVELS))})")
            _check_kebab_case(zone.get('id', ''), 'network_zone', warnings)

    # --- 9. Security posture warnings ---
    for comp in system.get('components', []):
        if not isinstance(comp, dict):
            continue
        for listener in comp.get('listeners', []):
            if not isinstance(listener, dict):
                continue
            if listener.get('authn_mechanism') == 'none':
                warnings.append(
                    f"component '{comp.get('id', '?')}' listener '{listener.get('id', '?')}': "
                    f"authn_mechanism is 'none' — unauthenticated access"
                )
            if listener.get('tls_enabled') is False:
                warnings.append(
                    f"component '{comp.get('id', '?')}' listener '{listener.get('id', '?')}': "
                    f"tls_enabled is false — unencrypted traffic"
                )

    # --- 10. Orphaned components ---
    connected = set()
    for rel in system.get('component_relationships', []):
        if isinstance(rel, dict):
            if rel.get('source_component'):
                connected.add(rel['source_component'])
            if rel.get('target_component'):
                connected.add(rel['target_component'])
    for comp_id in components:
        if comp_id not in connected:
            warnings.append(f"component '{comp_id}' has no relationships (orphaned)")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


def _check_unique_ids(entity_type: str, items: list, errors: list) -> None:
    """Check that all IDs are unique within their entity type."""
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict) or 'id' not in item:
            continue
        if item['id'] in seen:
            errors.append(f"Duplicate {entity_type} id: '{item['id']}'")
        seen.add(item['id'])


def _check_kebab_case(id_value: str, entity_type: str, warnings: list) -> None:
    """Check that an ID follows kebab-case convention."""
    if id_value and not KEBAB_CASE_RE.match(id_value):
        warnings.append(f"{entity_type} id '{id_value}' is not kebab-case (expected: lowercase-with-hyphens)")


def main():
    if len(sys.argv) < 2:
        print(json.dumps({
            "valid": False,
            "errors": ["Usage: python tools/validate.py <system.yaml> [networks.yaml]"],
            "warnings": [],
        }))
        sys.exit(1)

    system_path = sys.argv[1]
    networks_path = sys.argv[2] if len(sys.argv) > 2 else None

    # Auto-detect networks.yaml if not provided
    if not networks_path:
        system_dir = Path(system_path).parent
        candidate = system_dir.parent / 'networks.yaml'
        if candidate.exists():
            networks_path = str(candidate)

    result = validate(system_path, networks_path)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result['valid'] else 1)


if __name__ == '__main__':
    main()
