#!/usr/bin/env python3
# Copyright (c) 2026 Michael J. Read. All rights reserved.
# SPDX-License-Identifier: BUSL-1.1
"""Deterministic schema validation for Doc2ArchAgent YAML files.

Implements the Separation Principle: validation is pure code, no LLM involvement.
Same input always produces same output.

Usage:
    python tools/validate.py <system.yaml> [networks.yaml] [--format json|table|sarif] [--strict]

Output formats:
    json   — JSON to stdout (default): {"valid": bool, "errors": [...], "warnings": [...]}
    table  — Human-readable table to stdout
    sarif  — SARIF 2.1.0 JSON for GitHub Security tab integration

Exit codes:
    0 — No errors (warnings allowed unless --strict)
    1 — Errors found
    2 — Only warnings found (with --strict)
"""

import argparse
import hashlib
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

# SARIF rule definitions — each validation check maps to a rule ID
SARIF_RULES = {
    "ARCH001": {
        "id": "ARCH001",
        "shortDescription": {"text": "Missing required field"},
        "fullDescription": {"text": "A required field is missing or empty in the architecture YAML."},
        "help": {"text": "Add the required field with a non-empty value."},
        "defaultConfiguration": {"level": "error"},
    },
    "ARCH002": {
        "id": "ARCH002",
        "shortDescription": {"text": "Referential integrity violation"},
        "fullDescription": {"text": "A reference points to a non-existent entity."},
        "help": {"text": "Ensure the referenced ID exists in the YAML model."},
        "defaultConfiguration": {"level": "error"},
    },
    "ARCH003": {
        "id": "ARCH003",
        "shortDescription": {"text": "Duplicate ID"},
        "fullDescription": {"text": "Two or more entities share the same ID within an entity type."},
        "help": {"text": "Use unique IDs within each entity type."},
        "defaultConfiguration": {"level": "error"},
    },
    "ARCH004": {
        "id": "ARCH004",
        "shortDescription": {"text": "Invalid enum value"},
        "fullDescription": {"text": "A field contains a value not in the allowed set."},
        "help": {"text": "Use one of the allowed enum values."},
        "defaultConfiguration": {"level": "error"},
    },
    "ARCH005": {
        "id": "ARCH005",
        "shortDescription": {"text": "Naming convention violation"},
        "fullDescription": {"text": "An ID does not follow kebab-case convention."},
        "help": {"text": "Use lowercase-with-hyphens format (e.g., 'my-component')."},
        "defaultConfiguration": {"level": "warning"},
    },
    "ARCH006": {
        "id": "ARCH006",
        "shortDescription": {"text": "Unauthenticated listener"},
        "fullDescription": {"text": "A component listener has no authentication mechanism."},
        "help": {"text": "Set authn_mechanism to a value other than 'none'."},
        "defaultConfiguration": {"level": "warning"},
    },
    "ARCH007": {
        "id": "ARCH007",
        "shortDescription": {"text": "Unencrypted listener"},
        "fullDescription": {"text": "A component listener has TLS disabled."},
        "help": {"text": "Set tls_enabled to true and specify tls_version_min."},
        "defaultConfiguration": {"level": "warning"},
    },
    "ARCH008": {
        "id": "ARCH008",
        "shortDescription": {"text": "Orphaned entity"},
        "fullDescription": {"text": "An entity (component, container, or zone) has no references connecting it to the architecture model."},
        "help": {"text": "Add relationships, placements, or infrastructure resources referencing this entity."},
        "defaultConfiguration": {"level": "warning"},
    },
    "ARCH009": {
        "id": "ARCH009",
        "shortDescription": {"text": "Invalid port number"},
        "fullDescription": {"text": "A listener port is outside the valid range 1-65535."},
        "help": {"text": "Use a port number between 1 and 65535."},
        "defaultConfiguration": {"level": "error"},
    },
    "ARCH010": {
        "id": "ARCH010",
        "shortDescription": {"text": "Component in external context"},
        "fullDescription": {"text": "A component exists in an external (non-internal) context, which may indicate an extraction error."},
        "help": {"text": "External contexts represent third-party systems. Internal components should be in internal contexts."},
        "defaultConfiguration": {"level": "warning"},
    },
    "ARCH011": {
        "id": "ARCH011",
        "shortDescription": {"text": "Unusual cardinality"},
        "fullDescription": {"text": "An entity has an unusually high number of children, suggesting a possible extraction error."},
        "help": {"text": "Review the architecture model for correct abstraction levels."},
        "defaultConfiguration": {"level": "warning"},
    },
    "ARCH012": {
        "id": "ARCH012",
        "shortDescription": {"text": "Security cross-reference violation"},
        "fullDescription": {"text": "A security overlay file references an ID that does not exist in the base file."},
        "help": {"text": "Ensure all IDs in security files match entities in the corresponding base file."},
        "defaultConfiguration": {"level": "error"},
    },
    "ARCH013": {
        "id": "ARCH013",
        "shortDescription": {"text": "Missing security annotation"},
        "fullDescription": {"text": "A component in system.yaml has no corresponding entry in system-security.yaml."},
        "help": {"text": "Add a component_security entry for this component."},
        "defaultConfiguration": {"level": "warning"},
    },
    "ARCH014": {
        "id": "ARCH014",
        "shortDescription": {"text": "Missing architecture file"},
        "fullDescription": {"text": "An expected architecture file is missing from the architecture directory."},
        "help": {"text": "Generate the missing file using the appropriate agent or tool."},
        "defaultConfiguration": {"level": "warning"},
    },
    "ARCH015": {
        "id": "ARCH015",
        "shortDescription": {"text": "Missing threat coverage"},
        "fullDescription": {"text": "A component with listeners has no threat modeling coverage."},
        "help": {"text": "Run tools/threat-rules.py to generate threat findings for this component."},
        "defaultConfiguration": {"level": "warning"},
    },
    "ARCH016": {
        "id": "ARCH016",
        "shortDescription": {"text": "Stale architecture data"},
        "fullDescription": {"text": "Architecture metadata indicates the model has not been reviewed recently."},
        "help": {"text": "Update metadata.last_review_date after reviewing the architecture."},
        "defaultConfiguration": {"level": "warning"},
    },
    "ARCH017": {
        "id": "ARCH017",
        "shortDescription": {"text": "Missing coverage gap"},
        "fullDescription": {"text": "A component or listener is missing an expected annotation or configuration."},
        "help": {"text": "Add the missing annotation to improve architecture completeness."},
        "defaultConfiguration": {"level": "warning"},
    },
}


def validate(system_path: str, networks_path: str | None = None,
             security_path: str | None = None,
             networks_security_path: str | None = None,
             deployment_security_path: str | None = None) -> dict:
    """Run all validation checks and return results as dict."""
    errors: list[dict] = []
    warnings: list[dict] = []

    def add_error(msg: str, rule_id: str = "ARCH001", file: str | None = None):
        errors.append({"message": msg, "rule_id": rule_id, "file": file or system_path})

    def add_warning(msg: str, rule_id: str = "ARCH005", file: str | None = None):
        warnings.append({"message": msg, "rule_id": rule_id, "file": file or system_path})

    # --- Load files ---
    try:
        with open(system_path) as f:
            raw_content = f.read()
        if raw_content.startswith("# GENERATED by compose.py"):
            add_warning(
                "This file was generated by compose.py — edit the deployment manifest instead",
                rule_id="ARCH005", file=system_path)
        system = yaml.safe_load(raw_content) or {}
    except Exception as e:
        return {
            "valid": False,
            "errors": [{"message": f"Cannot load system YAML: {e}", "rule_id": "ARCH001", "file": system_path}],
            "warnings": [],
        }

    networks = {}
    nw_file = networks_path or ""
    if networks_path:
        try:
            with open(networks_path) as f:
                networks = yaml.safe_load(f) or {}
        except Exception as e:
            add_warning(f"Cannot load networks YAML: {e}", file=networks_path)

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
        add_error("metadata: missing or not a mapping")
    else:
        for field in ('name', 'description', 'owner', 'status'):
            if not metadata.get(field):
                add_error(f"metadata.{field}: required field is missing or empty")
        if metadata.get('status') and metadata['status'] not in VALID_STATUSES:
            add_error(
                f"metadata.status: '{metadata['status']}' is not a valid status ({', '.join(sorted(VALID_STATUSES))})",
                rule_id="ARCH004",
            )

    # --- 2. Context required fields + unique IDs ---
    _check_unique_ids('context', system.get('contexts', []), errors, system_path)
    for ctx in system.get('contexts', []):
        if not isinstance(ctx, dict):
            continue
        for field in ('id', 'name', 'description'):
            if not ctx.get(field):
                add_error(f"context '{ctx.get('id', '?')}': required field '{field}' is missing")
        if 'internal' not in ctx:
            add_error(f"context '{ctx.get('id', '?')}': required field 'internal' is missing")
        _check_kebab_case(ctx.get('id', ''), 'context', warnings, system_path)

    # --- 3. Container required fields + referential integrity ---
    _check_unique_ids('container', system.get('containers', []), errors, system_path)
    for ctr in system.get('containers', []):
        if not isinstance(ctr, dict):
            continue
        for field in ('id', 'name', 'context_id', 'container_type', 'technology'):
            if not ctr.get(field):
                add_error(f"container '{ctr.get('id', '?')}': required field '{field}' is missing")
        if ctr.get('context_id') and ctr['context_id'] not in contexts:
            add_error(
                f"container '{ctr.get('id', '?')}': references non-existent context '{ctr['context_id']}'",
                rule_id="ARCH002",
            )
        _check_kebab_case(ctr.get('id', ''), 'container', warnings, system_path)

    # --- 4. Component required fields + referential integrity ---
    _check_unique_ids('component', system.get('components', []), errors, system_path)
    for comp in system.get('components', []):
        if not isinstance(comp, dict):
            continue
        for field in ('id', 'name', 'container_id', 'component_type', 'technology'):
            if not comp.get(field):
                add_error(f"component '{comp.get('id', '?')}': required field '{field}' is missing")
        if comp.get('container_id') and comp['container_id'] not in containers:
            add_error(
                f"component '{comp.get('id', '?')}': references non-existent container '{comp['container_id']}'",
                rule_id="ARCH002",
            )
        _check_kebab_case(comp.get('id', ''), 'component', warnings, system_path)

        # Listener required fields + port validation
        for listener in comp.get('listeners', []):
            if not isinstance(listener, dict):
                continue
            for field in ('id', 'protocol', 'port'):
                if field not in listener:
                    add_error(
                        f"listener '{listener.get('id', '?')}' on component '{comp.get('id', '?')}': "
                        f"required field '{field}' is missing"
                    )
            # Port range validation
            port = listener.get('port')
            if port is not None and (not isinstance(port, int) or port < 1 or port > 65535):
                add_error(
                    f"listener '{listener.get('id', '?')}' on component '{comp.get('id', '?')}': "
                    f"port {port} is outside valid range 1-65535",
                    rule_id="ARCH009",
                )

    # --- 5. Context relationship referential integrity ---
    for rel in system.get('context_relationships', []):
        if not isinstance(rel, dict):
            continue
        _check_kebab_case(rel.get('id', ''), 'context_relationship', warnings, system_path)
        if rel.get('source_context') and rel['source_context'] not in contexts:
            add_error(
                f"context_relationship '{rel.get('id', '?')}': source_context '{rel['source_context']}' does not exist",
                rule_id="ARCH002",
            )
        if rel.get('target_context') and rel['target_context'] not in contexts:
            add_error(
                f"context_relationship '{rel.get('id', '?')}': target_context '{rel['target_context']}' does not exist",
                rule_id="ARCH002",
            )

    # --- 6. Container relationship referential integrity ---
    for rel in system.get('container_relationships', []):
        if not isinstance(rel, dict):
            continue
        _check_kebab_case(rel.get('id', ''), 'container_relationship', warnings, system_path)
        if rel.get('source_container') and rel['source_container'] not in containers:
            add_error(
                f"container_relationship '{rel.get('id', '?')}': source_container '{rel['source_container']}' does not exist",
                rule_id="ARCH002",
            )
        if rel.get('target_container') and rel['target_container'] not in containers:
            add_error(
                f"container_relationship '{rel.get('id', '?')}': target_container '{rel['target_container']}' does not exist",
                rule_id="ARCH002",
            )

    # --- 7. Component relationship referential integrity ---
    for rel in system.get('component_relationships', []):
        if not isinstance(rel, dict):
            continue
        _check_kebab_case(rel.get('id', ''), 'component_relationship', warnings, system_path)
        src = rel.get('source_component', '')
        tgt = rel.get('target_component', '')
        if src and src not in components:
            add_error(
                f"component_relationship '{rel.get('id', '?')}': source_component '{src}' does not exist",
                rule_id="ARCH002",
            )
        if tgt and tgt not in components:
            add_error(
                f"component_relationship '{rel.get('id', '?')}': target_component '{tgt}' does not exist",
                rule_id="ARCH002",
            )
        # Check target_listener_ref
        listener_ref = rel.get('target_listener_ref', '')
        if listener_ref and tgt:
            target_listeners = listeners_by_component.get(tgt, {})
            if listener_ref not in target_listeners:
                add_error(
                    f"component_relationship '{rel.get('id', '?')}': target_listener_ref '{listener_ref}' "
                    f"does not exist on component '{tgt}'",
                    rule_id="ARCH002",
                )

    # --- 8. Network zone required fields (if networks.yaml provided) ---
    if networks:
        _check_unique_ids('network_zone', networks.get('network_zones', []), errors, nw_file)
        for zone in networks.get('network_zones', []):
            if not isinstance(zone, dict):
                continue
            for field in ('id', 'name', 'zone_type', 'internet_routable', 'trust'):
                if field not in zone:
                    add_error(
                        f"network_zone '{zone.get('id', '?')}': required field '{field}' is missing",
                        file=nw_file,
                    )
            if zone.get('trust') and zone['trust'] not in VALID_TRUST_LEVELS:
                add_error(
                    f"network_zone '{zone.get('id', '?')}': trust '{zone['trust']}' is not valid "
                    f"({', '.join(sorted(VALID_TRUST_LEVELS))})",
                    rule_id="ARCH004",
                    file=nw_file,
                )
            _check_kebab_case(zone.get('id', ''), 'network_zone', warnings, nw_file)

    # --- 9. Infrastructure resource required fields + referential integrity ---
    if networks:
        infra_resources = networks.get('infrastructure_resources', [])
        _check_unique_ids('infrastructure_resource', infra_resources, errors, nw_file)
        for res in infra_resources:
            if not isinstance(res, dict):
                continue
            for field in ('id', 'name', 'resource_type', 'technology', 'zone_id'):
                if not res.get(field):
                    add_error(
                        f"infrastructure_resource '{res.get('id', '?')}': required field '{field}' is missing",
                        file=nw_file,
                    )
            if res.get('zone_id') and res['zone_id'] not in zones:
                add_error(
                    f"infrastructure_resource '{res.get('id', '?')}': zone_id '{res['zone_id']}' "
                    f"does not exist in network_zones",
                    rule_id="ARCH002",
                    file=nw_file,
                )
            _check_kebab_case(res.get('id', ''), 'infrastructure_resource', warnings, nw_file)

    # --- 10. Security posture warnings ---
    for comp in system.get('components', []):
        if not isinstance(comp, dict):
            continue
        for listener in comp.get('listeners', []):
            if not isinstance(listener, dict):
                continue
            if listener.get('authn_mechanism') == 'none':
                add_warning(
                    f"component '{comp.get('id', '?')}' listener '{listener.get('id', '?')}': "
                    f"authn_mechanism is 'none' — unauthenticated access",
                    rule_id="ARCH006",
                )
            if listener.get('tls_enabled') is False:
                add_warning(
                    f"component '{comp.get('id', '?')}' listener '{listener.get('id', '?')}': "
                    f"tls_enabled is false — unencrypted traffic",
                    rule_id="ARCH007",
                )

    # --- 11. Orphaned entity detection (components, containers, zones) ---
    # 11a. Orphaned components — no relationships referencing them
    connected = set()
    for rel in system.get('component_relationships', []):
        if isinstance(rel, dict):
            if rel.get('source_component'):
                connected.add(rel['source_component'])
            if rel.get('target_component'):
                connected.add(rel['target_component'])
    for comp_id in components:
        if comp_id not in connected:
            add_warning(f"component '{comp_id}' has no relationships (orphaned)", rule_id="ARCH008")

    # 11a-ii. Orphaned containers — no components reference them
    referenced_containers = {comp.get('container_id') for comp in components.values() if comp.get('container_id')}
    for cont_id in containers:
        if cont_id not in referenced_containers:
            add_warning(
                f"container '{cont_id}' has no components assigned to it (orphaned)",
                rule_id="ARCH008",
            )

    # 11a-iii. Orphaned zones — no deployment placements or infra resources reference them
    if networks and zones:
        referenced_zones = set()
        # From infrastructure_resources
        for res in networks.get('infrastructure_resources', []):
            if isinstance(res, dict) and res.get('zone_id'):
                referenced_zones.add(res['zone_id'])
        # From trust_boundaries
        for tb in system.get('trust_boundaries', []):
            if isinstance(tb, dict):
                for field in ('source_zone', 'target_zone'):
                    if tb.get(field):
                        referenced_zones.add(tb[field])
        for zone_id in zones:
            if zone_id not in referenced_zones:
                add_warning(
                    f"network_zone '{zone_id}' has no infrastructure resources or trust boundary references (orphaned)",
                    rule_id="ARCH008",
                    file=nw_file,
                )

    # --- 11b. Data entity and external system referential integrity ---
    data_entities = {d['id']: d for d in system.get('data_entities', []) if isinstance(d, dict) and 'id' in d}
    for rel in system.get('component_relationships', []):
        if not isinstance(rel, dict):
            continue
        for de_ref in rel.get('data_entities', []):
            if isinstance(de_ref, str) and de_ref not in data_entities:
                add_warning(
                    f"component_relationship '{rel.get('id', '?')}': data_entity '{de_ref}' "
                    f"not found in system.yaml data_entities (may be in security overlay)",
                    rule_id="ARCH002",
                )

    # --- 11c. Trust boundary zone references ---
    for tb in system.get('trust_boundaries', []):
        if not isinstance(tb, dict):
            continue
        for zone_field in ('source_zone', 'target_zone'):
            zone_ref = tb.get(zone_field, '')
            if zone_ref and zones and zone_ref not in zones:
                add_warning(
                    f"trust_boundary '{tb.get('id', '?')}': {zone_field} '{zone_ref}' "
                    f"not found in networks.yaml network_zones",
                    rule_id="ARCH002",
                )

    # --- 11d. Context external_system_id references ---
    for ctx in system.get('contexts', []):
        if not isinstance(ctx, dict):
            continue
        ext_ref = ctx.get('external_system_id', '')
        if ext_ref and ext_ref not in external_systems:
            add_error(
                f"context '{ctx.get('id', '?')}': external_system_id '{ext_ref}' "
                f"does not exist in external_systems",
                rule_id="ARCH002",
            )

    # --- 12. Cross-entity consistency checks (hallucination detection) ---
    # A component in an external context (internal=false) is suspicious
    for comp_id, comp in components.items():
        cont_id = comp.get('container_id', '')
        container = containers.get(cont_id, {})
        ctx_id = container.get('context_id', '')
        context = contexts.get(ctx_id, {})
        if context and not context.get('internal', True):
            add_warning(
                f"component '{comp_id}' is in external context '{ctx_id}' via container '{cont_id}' "
                f"— external contexts typically represent third-party systems without internal components",
                rule_id="ARCH010",
            )

    # --- 13. Cardinality checks (model quality / extraction gap detection) ---
    for cont_id, container in containers.items():
        comp_count = sum(1 for c in components.values() if c.get('container_id') == cont_id)
        if comp_count > 50:
            add_warning(
                f"container '{cont_id}' has {comp_count} components — this may indicate "
                f"an extraction error or wrong abstraction level",
                rule_id="ARCH011",
            )

    for comp_id, comp in components.items():
        listener_count = len(comp.get('listeners', []))
        if listener_count > 10:
            add_warning(
                f"component '{comp_id}' has {listener_count} listeners — this is unusually high "
                f"and may indicate an extraction error",
                rule_id="ARCH011",
            )

    # --- 14. Security overlay cross-reference validation ---
    if security_path:
        try:
            with open(security_path) as f:
                sec_data = yaml.safe_load(f) or {}
        except Exception as e:
            add_error(f"Cannot load security YAML: {e}", rule_id="ARCH001", file=security_path)
            sec_data = {}

        # Build listener index: (comp_id, listener_id) -> True
        listener_ids: set[tuple[str, str]] = set()
        for comp in system.get('components', []):
            if isinstance(comp, dict):
                cid = comp.get('id', '')
                for listener in comp.get('listeners', []):
                    if isinstance(listener, dict):
                        listener_ids.add((cid, listener.get('id', '')))

        rel_ids = {r.get('id', '') for r in system.get('component_relationships', []) if isinstance(r, dict)}
        ext_ids = {e.get('id', '') for e in system.get('external_systems', []) if isinstance(e, dict)}
        sec_comp_ids: set[str] = set()

        for cs in sec_data.get('component_security', []):
            cid = cs.get('component_id', '')
            sec_comp_ids.add(cid)
            if cid and cid not in components:
                add_error(
                    f"system-security.yaml: component_id '{cid}' does not exist in system.yaml",
                    rule_id="ARCH012", file=security_path)
            for ls in cs.get('listener_security', []):
                lid = ls.get('listener_id', '')
                if lid and (cid, lid) not in listener_ids:
                    add_error(
                        f"system-security.yaml: listener_id '{lid}' on component '{cid}' "
                        f"does not exist in system.yaml",
                        rule_id="ARCH012", file=security_path)

        for rs in sec_data.get('relationship_security', []):
            rid = rs.get('relationship_id', '')
            if rid and rid not in rel_ids:
                add_error(
                    f"system-security.yaml: relationship_id '{rid}' does not exist in system.yaml",
                    rule_id="ARCH012", file=security_path)

        for es in sec_data.get('external_system_security', []):
            eid = es.get('external_system_id', '')
            if eid and eid not in ext_ids:
                add_error(
                    f"system-security.yaml: external_system_id '{eid}' does not exist in system.yaml",
                    rule_id="ARCH012", file=security_path)

        # Coverage warnings — components without security annotations
        for comp_id in components:
            if comp_id not in sec_comp_ids:
                add_warning(
                    f"component '{comp_id}' has no security annotation in system-security.yaml",
                    rule_id="ARCH013", file=security_path)

    if networks_security_path and networks:
        try:
            with open(networks_security_path) as f:
                net_sec = yaml.safe_load(f) or {}
        except Exception as e:
            add_error(f"Cannot load networks-security YAML: {e}", rule_id="ARCH001",
                      file=networks_security_path)
            net_sec = {}

        for zs in net_sec.get('zone_security', []):
            zid = zs.get('zone_id', '')
            if zid and zid not in zones:
                add_error(
                    f"networks-security.yaml: zone_id '{zid}' does not exist in networks.yaml",
                    rule_id="ARCH012", file=networks_security_path)

    # --- 15. Predictive gap analysis ---
    # 15a. Missing architecture files
    system_dir = Path(system_path).parent
    arch_root = system_dir if system_dir.name != "." else system_dir.parent

    expected_files = {
        "networks.yaml": "Network zone definitions",
        "system-security.yaml": "Security annotations for system components",
        "networks-security.yaml": "Security annotations for network zones",
    }
    for fname, description in expected_files.items():
        candidate = arch_root / fname
        if not candidate.exists():
            # Also check parent directory
            alt = arch_root.parent / fname
            if not alt.exists():
                add_warning(
                    f"Missing architecture file: {fname} ({description})",
                    rule_id="ARCH014",
                )

    # 15b. Missing threat coverage — components with listeners but no threat findings
    # We check by looking for threat-report files
    threat_report = arch_root / "threat-report.sarif"
    threat_report_alt = arch_root.parent / "threat-report.sarif"
    has_threat_report = threat_report.exists() or threat_report_alt.exists()

    components_with_listeners = [
        comp_id for comp_id, comp in components.items()
        if comp.get("listeners")
    ]
    if components_with_listeners and not has_threat_report:
        add_warning(
            f"{len(components_with_listeners)} component(s) with listeners have no threat "
            f"report — run tools/threat-rules.py to generate threat analysis",
            rule_id="ARCH015",
        )

    # 15c. Staleness detection — last_review_date older than 6 months
    last_review = metadata.get("last_review_date", "") if isinstance(metadata, dict) else ""
    if last_review:
        try:
            from datetime import datetime, timezone
            review_str = str(last_review).replace("Z", "+00:00")
            review_date = datetime.fromisoformat(review_str)
            if review_date.tzinfo is None:
                review_date = review_date.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            days_since = (now - review_date).days
            if days_since > 180:
                add_warning(
                    f"Architecture model last reviewed {days_since} days ago "
                    f"(last_review_date: {last_review}) — consider re-reviewing",
                    rule_id="ARCH016",
                )
        except (ValueError, TypeError):
            pass  # Non-parseable date, skip

    # 15d. Missing coverage — components without description
    for comp_id, comp in components.items():
        if not comp.get("description"):
            add_warning(
                f"component '{comp_id}' has no description — extraction may be incomplete",
                rule_id="ARCH017",
            )

    # 15e. Listeners without security configuration
    for comp_id, comp in components.items():
        for listener in comp.get("listeners", []):
            if not isinstance(listener, dict):
                continue
            has_authn = listener.get("authn_mechanism") and listener["authn_mechanism"] != "none"
            has_tls = listener.get("tls_enabled")
            if not has_authn and not has_tls:
                add_warning(
                    f"component '{comp_id}' listener '{listener.get('id', '?')}' has neither "
                    f"authentication nor TLS configured",
                    rule_id="ARCH017",
                )

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


def _check_unique_ids(entity_type: str, items: list, errors: list, file: str) -> None:
    """Check that all IDs are unique within their entity type."""
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict) or 'id' not in item:
            continue
        if item['id'] in seen:
            errors.append({
                "message": f"Duplicate {entity_type} id: '{item['id']}'",
                "rule_id": "ARCH003",
                "file": file,
            })
        seen.add(item['id'])


def _check_kebab_case(id_value: str, entity_type: str, warnings: list, file: str) -> None:
    """Check that an ID follows kebab-case convention."""
    if id_value and not KEBAB_CASE_RE.match(id_value):
        warnings.append({
            "message": f"{entity_type} id '{id_value}' is not kebab-case (expected: lowercase-with-hyphens)",
            "rule_id": "ARCH005",
            "file": file,
        })


# --- Output formatters ---

def format_json(result: dict) -> str:
    """Format result as JSON (backward-compatible with original output)."""
    compat = {
        "valid": result["valid"],
        "errors": [item["message"] for item in result["errors"]],
        "warnings": [item["message"] for item in result["warnings"]],
    }
    return json.dumps(compat, indent=2)


def format_table(result: dict) -> str:
    """Format result as a human-readable table."""
    lines = []
    lines.append("=" * 72)
    lines.append(f"  Doc2ArchAgent Validation Report")
    lines.append(f"  Status: {'PASS' if result['valid'] else 'FAIL'}")
    lines.append(f"  Errors: {len(result['errors'])}  |  Warnings: {len(result['warnings'])}")
    lines.append("=" * 72)

    if result["errors"]:
        lines.append("")
        lines.append("ERRORS:")
        for i, item in enumerate(result["errors"], 1):
            lines.append(f"  {i}. [{item['rule_id']}] {item['message']}")
            if item.get("file"):
                lines.append(f"     File: {item['file']}")

    if result["warnings"]:
        lines.append("")
        lines.append("WARNINGS:")
        for i, item in enumerate(result["warnings"], 1):
            lines.append(f"  {i}. [{item['rule_id']}] {item['message']}")
            if item.get("file"):
                lines.append(f"     File: {item['file']}")

    if not result["errors"] and not result["warnings"]:
        lines.append("")
        lines.append("  No issues found.")

    lines.append("")
    return "\n".join(lines)


def format_sarif(result: dict) -> str:
    """Format result as SARIF 2.1.0 JSON for GitHub Security tab."""
    # Collect used rules
    used_rule_ids = set()
    for item in result["errors"] + result["warnings"]:
        used_rule_ids.add(item["rule_id"])

    rules = [SARIF_RULES[rid] for rid in sorted(used_rule_ids) if rid in SARIF_RULES]

    sarif_results = []
    for item in result["errors"] + result["warnings"]:
        file_uri = item.get("file", "unknown")
        # Make path relative if absolute
        if file_uri.startswith("/"):
            try:
                file_uri = str(Path(file_uri).relative_to(Path.cwd()))
            except ValueError:
                pass

        level = "error" if item in result["errors"] else "warning"
        fingerprint = hashlib.md5(
            f"{item['rule_id']}:{item['message']}:{file_uri}".encode(),
            usedforsecurity=False,
        ).hexdigest()

        sarif_results.append({
            "ruleId": item["rule_id"],
            "level": level,
            "message": {"text": item["message"]},
            "locations": [{
                "physicalLocation": {
                    "artifactLocation": {"uri": file_uri},
                    "region": {"startLine": 1, "startColumn": 1},
                }
            }],
            "partialFingerprints": {
                "primaryLocationLineHash": fingerprint
            },
        })

    sarif = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {
                "driver": {
                    "name": "Doc2ArchAgent-Validate",
                    "version": "0.2.0",
                    "informationUri": "https://github.com/Michael-JRead/Doc2ArchAgent",
                    "rules": rules,
                }
            },
            "results": sarif_results,
        }],
    }
    return json.dumps(sarif, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Validate Doc2ArchAgent architecture YAML files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("system_yaml", help="Path to system.yaml file")
    parser.add_argument("networks_yaml", nargs="?", default=None, help="Path to networks.yaml file (optional)")
    parser.add_argument("--security", dest="security_yaml", default=None,
                        help="Path to system-security.yaml (optional)")
    parser.add_argument("--networks-security", dest="networks_security_yaml", default=None,
                        help="Path to networks-security.yaml (optional)")
    parser.add_argument("--deployment-security", dest="deployment_security_yaml", default=None,
                        help="Path to deployment-security.yaml (optional)")
    parser.add_argument(
        "--format", dest="output_format", choices=["json", "table", "sarif"],
        default="json", help="Output format (default: json)",
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="Treat warnings as errors (exit code 2 if only warnings)",
    )

    args = parser.parse_args()

    # Auto-detect networks.yaml if not provided
    networks_path = args.networks_yaml
    if not networks_path:
        system_dir = Path(args.system_yaml).parent
        candidate = system_dir.parent / 'networks.yaml'
        if candidate.exists():
            networks_path = str(candidate)

    # Auto-detect security files if not provided
    security_path = args.security_yaml
    if not security_path:
        candidate = Path(args.system_yaml).parent / 'system-security.yaml'
        if candidate.exists():
            security_path = str(candidate)

    networks_security_path = args.networks_security_yaml
    if not networks_security_path and networks_path:
        candidate = Path(networks_path).parent / 'networks-security.yaml'
        if candidate.exists():
            networks_security_path = str(candidate)

    deployment_security_path = args.deployment_security_yaml

    result = validate(args.system_yaml, networks_path,
                      security_path=security_path,
                      networks_security_path=networks_security_path,
                      deployment_security_path=deployment_security_path)

    # Format output
    formatters = {
        "json": format_json,
        "table": format_table,
        "sarif": format_sarif,
    }
    print(formatters[args.output_format](result))

    # Exit code logic
    if result["errors"]:
        sys.exit(1)
    elif args.strict and result["warnings"]:
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
