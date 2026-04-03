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
VALID_ZONE_TYPES = {'external', 'dmz', 'private', 'management', 'data', 'guest', 'disaster_recovery', 'quarantine', 'compliance', 'custom'}
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
VALID_AUDIENCES = {'application', 'human', 'hybrid', 'infrastructure'}
REQUIRED_DATAFLOW_FIELDS = ('id', 'label', 'protocol')
VALID_DATAFLOW_DIRECTIONS = {'ingress', 'egress', 'bidirectional'}
VALID_DATA_CLASSIFICATIONS = {'public', 'internal', 'confidential', 'restricted'}


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


def _validate_context_hierarchy(pattern_dir: Path, ptype: str,
                                errors: list, warnings: list):
    """Validate the contexts/ subdirectory of a pattern."""
    contexts_dir = pattern_dir / "contexts"
    dirname = pattern_dir.name

    if not contexts_dir.exists():
        # Not required, but recommended
        return

    # Validate _context.yaml if present
    context_yaml = contexts_dir / "_context.yaml"
    if context_yaml.exists():
        try:
            with open(context_yaml) as f:
                ctx_data = yaml.safe_load(f) or {}
        except Exception as e:
            errors.append(f"{dirname}/contexts/_context.yaml: cannot load: {e}")
            return

        contexts = ctx_data.get("contexts", [])
        if not contexts:
            warnings.append(f"{dirname}/contexts/_context.yaml: no contexts defined")

        context_ids: set[str] = set()
        for ctx in contexts:
            if not isinstance(ctx, dict):
                continue
            cid = ctx.get("id", "?")
            for field in ("id", "name", "description", "internal"):
                if field not in ctx:
                    errors.append(f"{dirname}/contexts/_context.yaml: context '{cid}': "
                                  f"required field '{field}' is missing")
            if cid != "?" and not KEBAB_CASE_RE.match(cid):
                warnings.append(f"{dirname}/contexts/_context.yaml: context id '{cid}' "
                                "is not kebab-case")
            if cid in context_ids:
                errors.append(f"{dirname}/contexts/_context.yaml: duplicate context id '{cid}'")
            context_ids.add(cid)

        # Validate context_relationships if present
        for rel in ctx_data.get("context_relationships", []):
            if not isinstance(rel, dict):
                continue
            relid = rel.get("id", "?")
            src = rel.get("source_context", "")
            tgt = rel.get("target_context", "")
            if src and src not in context_ids:
                errors.append(f"{dirname}/contexts/_context.yaml: relationship '{relid}': "
                              f"source_context '{src}' not found")
            if tgt and tgt not in context_ids:
                errors.append(f"{dirname}/contexts/_context.yaml: relationship '{relid}': "
                              f"target_context '{tgt}' not found")

    # Validate sources/ directory
    sources_dir = contexts_dir / "sources"
    if sources_dir.exists():
        inventory_path = sources_dir / "doc-inventory.yaml"
        if inventory_path.exists():
            try:
                with open(inventory_path) as f:
                    inv_data = yaml.safe_load(f) or {}
                if not inv_data.get("pattern_ref"):
                    warnings.append(f"{dirname}/contexts/sources/doc-inventory.yaml: "
                                    "missing pattern_ref")
                # Validate referenced files exist
                for doc in inv_data.get("documents", []):
                    if isinstance(doc, dict) and doc.get("file"):
                        doc_path = sources_dir / doc["file"]
                        if not doc_path.exists():
                            warnings.append(
                                f"{dirname}/contexts/sources/doc-inventory.yaml: "
                                f"document '{doc['file']}' listed but not found in sources/")
            except Exception as e:
                errors.append(f"{dirname}/contexts/sources/doc-inventory.yaml: "
                              f"cannot load: {e}")

    # Validate provenance.yaml if present
    provenance_path = contexts_dir / "provenance.yaml"
    if provenance_path.exists():
        try:
            with open(provenance_path) as f:
                prov_data = yaml.safe_load(f) or {}
            if not prov_data.get("extraction_date"):
                warnings.append(f"{dirname}/contexts/provenance.yaml: missing extraction_date")
        except Exception as e:
            errors.append(f"{dirname}/contexts/provenance.yaml: cannot load: {e}")


def _validate_dataflows(df_path: Path, fname: str, zone_ids: set, comp_ids: set,
                        errors: list, warnings: list):
    """Validate a dataflow file (app-dataflows.yaml or human-dataflows.yaml)."""
    try:
        with open(df_path) as f:
            data = yaml.safe_load(f) or {}
    except Exception as e:
        errors.append(f"{fname}: cannot load: {e}")
        return

    # Validate metadata
    meta = data.get("dataflow_metadata")
    if not meta or not isinstance(meta, dict):
        errors.append(f"{fname}: missing dataflow_metadata")
    else:
        audience = meta.get("audience")
        if not audience:
            errors.append(f"{fname}: dataflow_metadata.audience is required")
        elif audience not in VALID_AUDIENCES:
            errors.append(f"{fname}: dataflow_metadata.audience '{audience}' not valid")

    # Validate flows
    flows = data.get("dataflows", [])
    if not flows:
        warnings.append(f"{fname}: dataflows array is empty")
        return

    flow_ids: set[str] = set()
    for flow in flows:
        if not isinstance(flow, dict):
            continue
        fid = flow.get("id", "?")
        for field in REQUIRED_DATAFLOW_FIELDS:
            if not flow.get(field):
                errors.append(f"{fname}: dataflow '{fid}': required field '{field}' is missing")
        if fid != "?" and not KEBAB_CASE_RE.match(fid):
            warnings.append(f"{fname}: dataflow id '{fid}' is not kebab-case")
        if fid in flow_ids:
            errors.append(f"{fname}: duplicate dataflow id '{fid}'")
        flow_ids.add(fid)

        # Direction enum
        direction = flow.get("direction")
        if direction and direction not in VALID_DATAFLOW_DIRECTIONS:
            errors.append(f"{fname}: dataflow '{fid}': direction '{direction}' is not valid")

        # Data classification enum
        dc = flow.get("data_classification")
        if dc and dc not in VALID_DATA_CLASSIFICATIONS:
            errors.append(f"{fname}: dataflow '{fid}': data_classification '{dc}' is not valid")

        # Zone pair completeness
        has_src_zone = "source_zone" in flow
        has_tgt_zone = "target_zone" in flow
        if has_src_zone != has_tgt_zone:
            errors.append(f"{fname}: dataflow '{fid}': source_zone and target_zone must both be present or both absent")

        # Referential integrity (warnings only — may reference external entities)
        if has_src_zone and zone_ids and flow["source_zone"] not in zone_ids:
            warnings.append(f"{fname}: dataflow '{fid}': source_zone '{flow['source_zone']}' not in pattern zones (may be an external reference)")
        if has_tgt_zone and zone_ids and flow["target_zone"] not in zone_ids:
            warnings.append(f"{fname}: dataflow '{fid}': target_zone '{flow['target_zone']}' not in pattern zones (may be an external reference)")
        src_comp = flow.get("source_component")
        if src_comp and comp_ids and src_comp not in comp_ids:
            warnings.append(f"{fname}: dataflow '{fid}': source_component '{src_comp}' not in pattern components (may be an external reference)")
        tgt_comp = flow.get("target_component")
        if tgt_comp and comp_ids and tgt_comp not in comp_ids:
            warnings.append(f"{fname}: dataflow '{fid}': target_component '{tgt_comp}' not in pattern components (may be an external reference)")


def _validate_files_array(pattern_dir: Path, meta_path: Path,
                          errors: list, warnings: list):
    """Validate the 'files' array in pattern.meta.yaml lists real files."""
    try:
        with open(meta_path) as f:
            meta = yaml.safe_load(f) or {}
    except Exception:
        return
    files = meta.get("pattern", {}).get("files", [])
    if not files:
        return
    dirname = pattern_dir.name
    for fname in files:
        if not (pattern_dir / fname).exists():
            errors.append(f"{dirname}/pattern.meta.yaml: files entry '{fname}' does not exist on disk")


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

    # Load known context IDs from _context.yaml for referential integrity
    _ctx_path = pattern_dir / "contexts" / "_context.yaml"
    _known_ctx_ids: set[str] = set()
    if _ctx_path.exists():
        try:
            with open(_ctx_path) as f:
                _ctx_data = yaml.safe_load(f) or {}
            _known_ctx_ids = {c.get("id") for c in _ctx_data.get("contexts", [])
                              if isinstance(c, dict) and c.get("id")}
        except Exception:
            pass

    # Unified patterns: validate optional cross-files
    if ptype == 'network':
        opt_system = pattern_dir / "system.yaml"
        if opt_system.exists():
            try:
                with open(opt_system) as f:
                    opt_sys_data = yaml.safe_load(f) or {}
                _validate_product_system(opt_sys_data, f"{dirname}/system.yaml (unified)",
                                         errors, warnings, known_context_ids=_known_ctx_ids)
            except Exception as e:
                errors.append(f"{dirname}/system.yaml: cannot load: {e}")
    elif ptype == 'product':
        opt_networks = pattern_dir / "networks.yaml"
        if opt_networks.exists():
            try:
                with open(opt_networks) as f:
                    opt_net_data = yaml.safe_load(f) or {}
                _validate_network_content(opt_net_data, f"{dirname}/networks.yaml (unified)", errors, warnings)
            except Exception as e:
                errors.append(f"{dirname}/networks.yaml: cannot load: {e}")

    # Validate dataflow files
    zone_ids = set()
    comp_ids = set()
    # Collect zone/component IDs for referential integrity
    net_path = pattern_dir / "networks.yaml"
    if net_path.exists():
        try:
            with open(net_path) as f:
                nd = yaml.safe_load(f) or {}
            zone_ids = {z.get("id") for z in nd.get("network_zones", []) if isinstance(z, dict)}
        except Exception:
            pass
    sys_path = pattern_dir / "system.yaml"
    if sys_path.exists():
        try:
            with open(sys_path) as f:
                sd = yaml.safe_load(f) or {}
            comp_ids = {c.get("id") for c in sd.get("components", []) if isinstance(c, dict)}
        except Exception:
            pass
    for df_name in ("app-dataflows.yaml", "human-dataflows.yaml"):
        df_path = pattern_dir / df_name
        if df_path.exists():
            _validate_dataflows(df_path, f"{dirname}/{df_name}", zone_ids, comp_ids, errors, warnings)

    # Validate files array in pattern.meta.yaml
    _validate_files_array(pattern_dir, meta_path, errors, warnings)

    # Validate context hierarchy
    _validate_context_hierarchy(pattern_dir, ptype, errors, warnings)

    # Validate diagrams/ directory if present
    _validate_diagrams_dir(pattern_dir, errors, warnings)

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


def _validate_product_system(sys_data: dict, fname: str, errors: list, warnings: list,
                             known_context_ids: set | None = None):
    """Validate product pattern system.yaml content.

    Args:
        known_context_ids: Context IDs from _context.yaml (if loaded externally).
            Merged with inline contexts for referential integrity checks.
    """
    # Metadata
    metadata = sys_data.get('metadata', {})
    if not isinstance(metadata, dict):
        errors.append(f"{fname}: metadata is missing or not a mapping")
    else:
        for field in ('name', 'description', 'owner', 'status'):
            if not metadata.get(field):
                errors.append(f"{fname}: metadata.{field} is required")

    # Contexts (inline + external _context.yaml)
    inline_contexts = sys_data.get('contexts', [])
    all_context_ids = set(known_context_ids or set())
    for ctx in inline_contexts:
        if isinstance(ctx, dict) and ctx.get("id"):
            all_context_ids.add(ctx["id"])
    if not inline_contexts and not all_context_ids:
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


def _validate_diagrams_dir(pattern_dir: Path, errors: list, warnings: list):
    """Validate the diagrams/ subdirectory of a pattern if present."""
    diagrams_dir = pattern_dir / "diagrams"
    dirname = pattern_dir.name

    if not diagrams_dir.exists():
        return

    index_path = diagrams_dir / "_index.yaml"
    if not index_path.exists():
        warnings.append(f"{dirname}/diagrams/: directory exists but missing _index.yaml")
        return

    try:
        with open(index_path) as f:
            idx_data = yaml.safe_load(f) or {}
    except Exception as e:
        errors.append(f"{dirname}/diagrams/_index.yaml: cannot load: {e}")
        return

    # Required fields
    if not idx_data.get("scope_type"):
        errors.append(f"{dirname}/diagrams/_index.yaml: missing scope_type")
    elif idx_data["scope_type"] not in ("deployment", "pattern"):
        errors.append(f"{dirname}/diagrams/_index.yaml: scope_type must be 'deployment' or 'pattern'")

    if not idx_data.get("scope_id"):
        errors.append(f"{dirname}/diagrams/_index.yaml: missing scope_id")

    if not isinstance(idx_data.get("diagrams"), list):
        errors.append(f"{dirname}/diagrams/_index.yaml: 'diagrams' must be a list")
    else:
        for i, diag in enumerate(idx_data["diagrams"]):
            if not isinstance(diag, dict):
                continue
            if not diag.get("level"):
                errors.append(f"{dirname}/diagrams/_index.yaml: diagram[{i}] missing 'level'")
            if not diag.get("title"):
                errors.append(f"{dirname}/diagrams/_index.yaml: diagram[{i}] missing 'title'")
            if not diag.get("formats"):
                errors.append(f"{dirname}/diagrams/_index.yaml: diagram[{i}] missing 'formats'")
            elif isinstance(diag["formats"], dict):
                for fmt, fname in diag["formats"].items():
                    fpath = diagrams_dir / fname
                    if not fpath.exists():
                        warnings.append(
                            f"{dirname}/diagrams/_index.yaml: diagram[{i}] "
                            f"format '{fmt}' references '{fname}' but file not found")


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
