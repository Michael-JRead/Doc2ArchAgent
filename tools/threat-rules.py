#!/usr/bin/env python3
# Copyright (c) 2026 Michael J. Read. All rights reserved.
# SPDX-License-Identifier: BUSL-1.1
"""Deterministic threat rule engine for Doc2ArchAgent.

Loads YAML-based threat rules from context/threat-rules.yaml and evaluates
them against architecture models. Same input always produces same output.

Usage:
    python tools/threat-rules.py <system.yaml> [--networks <networks.yaml>]
        [--deployment <deployment.yaml>] [--format json|table|sarif]
        [--environment production|staging|development|dr]
        [--confidence-threshold 0.95]

Exit codes:
    0 — No findings above threshold
    1 — Findings found
"""

import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Error: pyyaml required. pip install pyyaml", file=sys.stderr)
    sys.exit(1)

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
RULES_FILE = PROJECT_ROOT / "context" / "threat-rules.yaml"
APPLICABILITY_FILE = PROJECT_ROOT / "context" / "threat-applicability.yaml"

SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}
SEVERITY_RISK_SCORE = {"critical": 9.0, "high": 7.0, "medium": 5.0, "low": 3.0, "info": 1.0}
COMPLIANCE_MAPPING_FILE = PROJECT_ROOT / "context" / "compliance-rule-mapping.yaml"


# =============================================================================
# Security Overlay Merge
# =============================================================================


def merge_security_overlays(system: dict, networks: dict | None,
                            deployment: dict | None,
                            sys_security: dict | None = None,
                            net_security: dict | None = None,
                            dep_security: dict | None = None) -> tuple[dict, dict | None, dict | None]:
    """Merge security overlay files into their base dicts by ID-matching.

    This is additive-only: existing inline fields are preserved. The merged
    result is identical in structure to the old inline format so ArchModel
    and rule evaluation require zero changes.
    """
    if sys_security:
        system = _merge_system_security(system, sys_security)
    if net_security and networks is not None:
        networks = _merge_network_security(networks, net_security)
    if dep_security and deployment is not None:
        deployment = _merge_deployment_security(deployment, dep_security)
    return system, networks, deployment


def _merge_system_security(system: dict, sec: dict) -> dict:
    """Merge system-security.yaml into system dict."""
    import copy
    system = copy.deepcopy(system)

    # Merge security_metadata into metadata
    sec_meta = sec.get("security_metadata", {})
    meta = system.setdefault("metadata", {})
    for key in ("compliance_frameworks", "business_criticality",
                "data_sensitivity_level", "threat_model_version",
                "last_review_date", "reviewer"):
        if key in sec_meta and key not in meta:
            meta[key] = sec_meta[key]

    # Index components and listeners by ID for fast lookup
    comp_index = {}
    for comp in system.get("components", []):
        comp_index[comp.get("id", "")] = comp
        for listener in comp.get("listeners", []):
            listener_key = (comp.get("id", ""), listener.get("id", ""))
            comp_index[listener_key] = listener

    # Merge component_security
    for cs in sec.get("component_security", []):
        comp_id = cs.get("component_id", "")
        comp = comp_index.get(comp_id)
        if not comp:
            continue
        for key, val in cs.items():
            if key in ("component_id", "listener_security"):
                continue
            if key not in comp:
                comp[key] = val
        # Merge listener_security
        for ls in cs.get("listener_security", []):
            lid = ls.get("listener_id", "")
            listener = comp_index.get((comp_id, lid))
            if not listener:
                continue
            for key, val in ls.items():
                if key == "listener_id":
                    continue
                if key not in listener:
                    listener[key] = val

    # Merge relationship_security
    rel_index = {r.get("id", ""): r for r in system.get("component_relationships", [])}
    for rs in sec.get("relationship_security", []):
        rel = rel_index.get(rs.get("relationship_id", ""))
        if not rel:
            continue
        for key, val in rs.items():
            if key == "relationship_id":
                continue
            if key not in rel:
                rel[key] = val

    # Merge external_system_security
    ext_index = {e.get("id", ""): e for e in system.get("external_systems", [])}
    for es in sec.get("external_system_security", []):
        ext = ext_index.get(es.get("external_system_id", ""))
        if not ext:
            continue
        for key, val in es.items():
            if key == "external_system_id":
                continue
            if key not in ext:
                ext[key] = val

    # Merge top-level security sections (additive)
    for section in ("data_entities", "trust_boundaries", "accepted_risks"):
        sec_items = sec.get(section, [])
        if sec_items:
            existing = system.get(section, [])
            existing_ids = {item.get("id") for item in existing if isinstance(item, dict)}
            for item in sec_items:
                if item.get("id") not in existing_ids:
                    existing.append(item)
            system[section] = existing

    return system


def _merge_network_security(networks: dict, sec: dict) -> dict:
    """Merge networks-security.yaml into networks dict."""
    import copy
    networks = copy.deepcopy(networks)

    # Merge zone_security by zone_id
    zone_index = {z.get("id", ""): z for z in networks.get("network_zones", [])}
    for zs in sec.get("zone_security", []):
        zone = zone_index.get(zs.get("zone_id", ""))
        if not zone:
            continue
        for key, val in zs.items():
            if key == "zone_id":
                continue
            if key not in zone:
                zone[key] = val

    # Merge infrastructure_resources (additive)
    sec_resources = sec.get("infrastructure_resources", [])
    if sec_resources:
        existing = networks.get("infrastructure_resources", [])
        existing_ids = {r.get("id") for r in existing if isinstance(r, dict)}
        for res in sec_resources:
            if res.get("id") not in existing_ids:
                existing.append(res)
        networks["infrastructure_resources"] = existing

    return networks


def _merge_deployment_security(deployment: dict, sec: dict) -> dict:
    """Merge deployment-security.yaml into deployment dict."""
    import copy
    deployment = copy.deepcopy(deployment)

    # Merge deployment_posture into deployment_metadata
    posture = sec.get("deployment_posture", {})
    dep_meta = deployment.setdefault("deployment_metadata", {})
    for key, val in posture.items():
        if key not in dep_meta:
            dep_meta[key] = val

    # Merge container_security by container_id (and optionally zone_id)
    # Build index: container_id -> container dict in zone_placements
    container_index = {}
    for placement in deployment.get("zone_placements", []):
        zone_id = placement.get("zone_id", "")
        for container in placement.get("containers", []):
            cid = container.get("container_id", "")
            container_index[(cid, zone_id)] = container
            container_index[cid] = container  # fallback without zone

    for cs in sec.get("container_security", []):
        cid = cs.get("container_id", "")
        zid = cs.get("zone_id", "")
        container = container_index.get((cid, zid)) or container_index.get(cid)
        if not container:
            continue
        for key, val in cs.items():
            if key in ("container_id", "zone_id"):
                continue
            if key not in container:
                container[key] = val

    return deployment


# =============================================================================
# Model Loading
# =============================================================================

class ArchModel:
    """Unified architecture model loaded from system.yaml + networks.yaml + deployment.yaml."""

    def __init__(self, system: dict, networks: dict | None = None, deployment: dict | None = None):
        self.system = system
        self.networks = networks or {}
        self.deployment = deployment or {}

        # Index entities by ID for fast lookup
        self.contexts = {c["id"]: c for c in system.get("contexts", []) if "id" in c}
        self.containers = {c["id"]: c for c in system.get("containers", []) if "id" in c}
        self.components = {c["id"]: c for c in system.get("components", []) if "id" in c}
        self.data_entities = {d["id"]: d for d in system.get("data_entities", []) if "id" in d}
        self.external_systems = {e["id"]: e for e in system.get("external_systems", []) if "id" in e}
        self.trust_boundaries = {t["id"]: t for t in system.get("trust_boundaries", []) if "id" in t}
        self.accepted_risks = system.get("accepted_risks", [])

        # Relationships
        self.component_relationships = system.get("component_relationships", [])
        self.container_relationships = system.get("container_relationships", [])

        # Networks
        self.zones = {z["id"]: z for z in self.networks.get("network_zones", []) if "id" in z}
        self.infra_resources = self.networks.get("infrastructure_resources", [])

        # Deployment
        self.environment = (deployment or {}).get("deployment_metadata", {}).get("environment", "production")
        self.zone_placements = (deployment or {}).get("zone_placements", [])

        # Build derived indexes
        self._build_component_zone_map()
        self._build_zone_resource_map()
        self._build_relationship_index()
        self._build_listener_index()

    def _build_component_zone_map(self):
        """Map component_id -> zone_id from deployment zone_placements."""
        self.component_to_zone = {}
        self.container_to_zone = {}
        for placement in self.zone_placements:
            zone_id = placement.get("zone_id", "")
            for container in placement.get("containers", []):
                cid = container.get("container_id", "")
                self.container_to_zone[cid] = zone_id
                for comp in container.get("components", []):
                    self.component_to_zone[comp.get("component_id", "")] = zone_id

    def _build_zone_resource_map(self):
        """Map zone_id -> set of resource types."""
        self.zone_resources = {}
        for res in self.infra_resources:
            zid = res.get("zone_id", "")
            if zid not in self.zone_resources:
                self.zone_resources[zid] = set()
            self.zone_resources[zid].add(res.get("resource_type", ""))

    def _build_relationship_index(self):
        """Index relationships by source and target component."""
        self.incoming_rels = {}
        self.outgoing_rels = {}
        for rel in self.component_relationships:
            src = rel.get("source_component", "")
            tgt = rel.get("target_component", "")
            self.outgoing_rels.setdefault(src, []).append(rel)
            self.incoming_rels.setdefault(tgt, []).append(rel)

    def _build_listener_index(self):
        """Index listener_id -> (component_id, listener_dict)."""
        self.listener_index = {}
        for comp_id, comp in self.components.items():
            for listener in comp.get("listeners", []):
                lid = listener.get("id", "")
                self.listener_index[lid] = (comp_id, listener)

    def get_zone_for_component(self, comp_id: str) -> dict | None:
        zone_id = self.component_to_zone.get(comp_id)
        return self.zones.get(zone_id) if zone_id else None

    def get_zone_for_container(self, cont_id: str) -> dict | None:
        zone_id = self.container_to_zone.get(cont_id)
        return self.zones.get(zone_id) if zone_id else None

    def zone_has_resource(self, zone_id: str, resource_type: str) -> bool:
        return resource_type in self.zone_resources.get(zone_id, set())

    def get_data_classification_for_component(self, comp_id: str) -> str | None:
        """Highest data classification from relationships involving this component."""
        classifications = []
        for rel in self.incoming_rels.get(comp_id, []) + self.outgoing_rels.get(comp_id, []):
            dc = rel.get("data_classification")
            if dc:
                classifications.append(dc)
        if not classifications:
            return None
        order = {"restricted": 4, "confidential": 3, "internal": 2, "public": 1}
        return max(classifications, key=lambda c: order.get(c, 0))

    def component_has_cross_zone_incoming(self, comp_id: str) -> bool:
        """Check if any incoming relationship crosses a zone boundary."""
        my_zone = self.component_to_zone.get(comp_id)
        if not my_zone:
            return False
        for rel in self.incoming_rels.get(comp_id, []):
            src_zone = self.component_to_zone.get(rel.get("source_component", ""))
            if src_zone and src_zone != my_zone:
                return True
        return False

    def relationship_crosses_trust_boundary(self, rel: dict) -> bool:
        """Check if a relationship crosses a trust boundary."""
        src_zone_id = self.component_to_zone.get(rel.get("source_component", ""))
        tgt_zone_id = self.component_to_zone.get(rel.get("target_component", ""))
        if not src_zone_id or not tgt_zone_id or src_zone_id == tgt_zone_id:
            return False
        src_zone = self.zones.get(src_zone_id, {})
        tgt_zone = self.zones.get(tgt_zone_id, {})
        return src_zone.get("trust") != tgt_zone.get("trust")

    def get_relationship_count(self, comp_id: str) -> int:
        return len(self.incoming_rels.get(comp_id, [])) + len(self.outgoing_rels.get(comp_id, []))


# =============================================================================
# Rule Engine
# =============================================================================

class Finding:
    """A single threat finding produced by a rule."""

    def __init__(self, rule_id: str, title: str, severity: str, stride: str | None,
                 cwe: int | None, cwe_name: str | None, description: str,
                 entity_type: str, entity_id: str, remediation: str,
                 severity_reason: str = "", file_path: str = "",
                 confidence: str = "high"):
        self.rule_id = rule_id
        self.title = title
        self.severity = severity
        self.stride = stride
        self.cwe = cwe
        self.cwe_name = cwe_name
        self.description = description
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.remediation = remediation
        self.severity_reason = severity_reason
        self.file_path = file_path
        self.confidence = confidence  # high, medium, low
        self.risk_score = SEVERITY_RISK_SCORE.get(severity, 1.0)
        self.compliance = []  # populated post-evaluation

    def to_dict(self) -> dict:
        d = {
            "rule_id": self.rule_id,
            "title": self.title,
            "severity": self.severity,
            "confidence": self.confidence,
            "risk_score": self.risk_score,
            "stride": self.stride,
            "cwe": self.cwe,
            "cwe_name": self.cwe_name,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "description": self.description.strip(),
            "remediation": self.remediation,
            "severity_reason": self.severity_reason,
        }
        if self.compliance:
            d["compliance"] = self.compliance
        return d


def load_rules() -> list[dict]:
    """Load threat rules from YAML."""
    if not RULES_FILE.exists():
        return []
    with open(RULES_FILE) as f:
        data = yaml.safe_load(f)
    return data.get("rules", [])


def load_compliance_mapping() -> dict:
    """Load decoupled compliance rule mappings."""
    if not COMPLIANCE_MAPPING_FILE.exists():
        return {}
    with open(COMPLIANCE_MAPPING_FILE) as f:
        data = yaml.safe_load(f) or {}
    return data.get("rule_mappings", {})


def load_applicability() -> dict:
    """Load threat applicability conditions."""
    if not APPLICABILITY_FILE.exists():
        return {}
    with open(APPLICABILITY_FILE) as f:
        return yaml.safe_load(f) or {}


def evaluate_rules(model: ArchModel, rules: list[dict], applicability: dict,
                   environment: str | None = None, file_path: str = "") -> list[Finding]:
    """Evaluate all rules against the model and return findings."""
    env = environment or model.environment
    env_thresholds = applicability.get("environment_thresholds", {})
    min_severity = env_thresholds.get(env, {}).get("minimum_severity", "info")
    min_sev_val = SEVERITY_ORDER.get(min_severity, 0)

    component_exceptions = applicability.get("component_type_exceptions", {})
    devops_adjustments = applicability.get("devops_adjustments", [])

    findings = []

    for rule in rules:
        rule_id = rule.get("id", "unknown")
        iterate_over = rule.get("iterate_over", "")

        if iterate_over == "listeners":
            findings.extend(_evaluate_listener_rule(rule, model, component_exceptions, file_path))
        elif iterate_over == "components":
            findings.extend(_evaluate_component_rule(rule, model, component_exceptions, file_path))
        elif iterate_over == "relationships":
            findings.extend(_evaluate_relationship_rule(rule, model, devops_adjustments, file_path))
        elif iterate_over == "zones":
            findings.extend(_evaluate_zone_rule(rule, model, file_path))
        elif iterate_over == "containers":
            findings.extend(_evaluate_container_rule(rule, model, file_path))

    # Apply environment threshold filter
    findings = [f for f in findings if SEVERITY_ORDER.get(f.severity, 0) >= min_sev_val]

    # Apply accepted risk filter
    findings = _filter_accepted_risks(findings, model.accepted_risks)

    return findings


def _evaluate_listener_rule(rule: dict, model: ArchModel, exceptions: dict,
                            file_path: str) -> list[Finding]:
    """Evaluate a rule that iterates over listeners."""
    findings = []
    for comp_id, comp in sorted(model.components.items()):
        if comp.get("out_of_scope"):
            continue

        comp_type = comp.get("component_type", "")
        suppressed_rules = exceptions.get(comp_type, {}).get("suppress_rules", [])
        if rule["id"] in suppressed_rules:
            continue

        zone = model.get_zone_for_component(comp_id)
        data_class = model.get_data_classification_for_component(comp_id)

        for listener in comp.get("listeners", []):
            if _check_listener_conditions(rule.get("conditions", []), listener, comp, zone, data_class):
                severity = _compute_severity(rule, comp, zone, listener, data_class)
                findings.append(Finding(
                    rule_id=rule["id"],
                    title=rule.get("title", rule["id"]),
                    severity=severity,
                    stride=rule.get("stride"),
                    cwe=rule.get("cwe"),
                    cwe_name=rule.get("cwe_name"),
                    description=rule.get("description", ""),
                    entity_type="listener",
                    entity_id=f"{comp_id}.{listener.get('id', '')}",
                    remediation=rule.get("remediation", ""),
                    file_path=file_path,
                ))
    return findings


def _evaluate_component_rule(rule: dict, model: ArchModel, exceptions: dict,
                             file_path: str) -> list[Finding]:
    """Evaluate a rule that iterates over components."""
    findings = []
    for comp_id, comp in sorted(model.components.items()):
        if comp.get("out_of_scope"):
            continue

        comp_type = comp.get("component_type", "")
        suppressed_rules = exceptions.get(comp_type, {}).get("suppress_rules", [])
        if rule["id"] in suppressed_rules:
            continue

        zone = model.get_zone_for_component(comp_id)
        data_class = model.get_data_classification_for_component(comp_id)

        if _check_component_conditions(rule.get("conditions", []), comp, zone, model, data_class):
            severity = _compute_severity(rule, comp, zone, None, data_class)
            findings.append(Finding(
                rule_id=rule["id"],
                title=rule.get("title", rule["id"]),
                severity=severity,
                stride=rule.get("stride"),
                cwe=rule.get("cwe"),
                cwe_name=rule.get("cwe_name"),
                description=rule.get("description", ""),
                entity_type="component",
                entity_id=comp_id,
                remediation=rule.get("remediation", ""),
                file_path=file_path,
            ))
    return findings


def _evaluate_relationship_rule(rule: dict, model: ArchModel, devops_adj: list,
                                file_path: str) -> list[Finding]:
    """Evaluate a rule that iterates over component relationships."""
    findings = []
    for rel in model.component_relationships:
        src_comp = model.components.get(rel.get("source_component", ""), {})
        tgt_comp = model.components.get(rel.get("target_component", ""), {})

        if src_comp.get("out_of_scope") or tgt_comp.get("out_of_scope"):
            continue

        # Resolve target listener
        target_listener = None
        tlr = rel.get("target_listener_ref")
        if tlr and tlr in model.listener_index:
            _, target_listener = model.listener_index[tlr]

        tgt_zone = model.get_zone_for_component(rel.get("target_component", ""))
        crosses_boundary = model.relationship_crosses_trust_boundary(rel)

        ctx = {
            "relationship": rel,
            "target_listener": target_listener,
            "crosses_trust_boundary": crosses_boundary,
            "zone": tgt_zone,
        }

        if _check_relationship_conditions(rule.get("conditions", []), ctx):
            severity = rule.get("severity", "medium")

            # Apply devops severity cap
            usage = rel.get("usage", "business")
            for adj in devops_adj:
                cond = adj.get("condition", "")
                if "usage" in cond and usage in ["devops", "monitoring"]:
                    cap = adj.get("severity_cap", "medium")
                    if SEVERITY_ORDER.get(severity, 0) > SEVERITY_ORDER.get(cap, 0):
                        severity = cap

            rel_id = rel.get("id", f"{rel.get('source_component', '')}-to-{rel.get('target_component', '')}")
            findings.append(Finding(
                rule_id=rule["id"],
                title=rule.get("title", rule["id"]),
                severity=severity,
                stride=rule.get("stride"),
                cwe=rule.get("cwe"),
                cwe_name=rule.get("cwe_name"),
                description=rule.get("description", ""),
                entity_type="relationship",
                entity_id=rel_id,
                remediation=rule.get("remediation", ""),
                file_path=file_path,
            ))
    return findings


def _evaluate_zone_rule(rule: dict, model: ArchModel, file_path: str) -> list[Finding]:
    """Evaluate a rule that iterates over network zones."""
    findings = []
    for zone_id, zone in sorted(model.zones.items()):
        enriched_zone = dict(zone)
        resources = model.zone_resources.get(zone_id, set())
        enriched_zone["has_waf"] = "waf" in resources
        enriched_zone["has_logging"] = "logging" in resources or "siem" in resources or "log_aggregator" in resources
        enriched_zone["has_monitoring"] = "monitoring" in resources or "apm" in resources

        if _check_zone_conditions(rule.get("conditions", []), enriched_zone):
            severity = rule.get("severity", "medium")
            # Check severity overrides
            for override in rule.get("severity_overrides", []):
                if _evaluate_override_when(override.get("when", ""), zone=enriched_zone):
                    severity = override.get("then", severity)
            findings.append(Finding(
                rule_id=rule["id"],
                title=rule.get("title", rule["id"]),
                severity=severity,
                stride=rule.get("stride"),
                cwe=rule.get("cwe"),
                cwe_name=rule.get("cwe_name"),
                description=rule.get("description", ""),
                entity_type="zone",
                entity_id=zone_id,
                remediation=rule.get("remediation", ""),
                file_path=file_path,
            ))
    return findings


def _evaluate_container_rule(rule: dict, model: ArchModel, file_path: str) -> list[Finding]:
    """Placeholder for container-level rules."""
    return []


# =============================================================================
# Condition Evaluation
# =============================================================================

def _check_listener_conditions(conditions: list, listener: dict, comp: dict,
                               zone: dict | None, data_class: str | None) -> bool:
    """Check all conditions for a listener rule."""
    for cond in conditions:
        field = cond.get("field", "")
        op = cond.get("operator", "")
        val = cond.get("value")

        actual = _resolve_field(field, listener=listener, component=comp,
                                zone=zone, data_classification=data_class)

        if not _compare(actual, op, val):
            return False
    return True


def _check_component_conditions(conditions: list, comp: dict, zone: dict | None,
                                model: ArchModel, data_class: str | None) -> bool:
    """Check all conditions for a component rule."""
    comp_id = comp.get("id", "")
    for cond in conditions:
        field = cond.get("field", "")
        op = cond.get("operator", "")
        val = cond.get("value")

        if field == "has_cross_zone_incoming":
            actual = model.component_has_cross_zone_incoming(comp_id)
        elif field == "relationship_count":
            actual = model.get_relationship_count(comp_id)
        elif field == "zone.has_waf":
            zone_id = model.component_to_zone.get(comp_id, "")
            actual = model.zone_has_resource(zone_id, "waf")
        elif field == "zone.has_logging":
            zone_id = model.component_to_zone.get(comp_id, "")
            actual = model.zone_has_resource(zone_id, "logging") or model.zone_has_resource(zone_id, "siem")
        else:
            actual = _resolve_field(field, component=comp, zone=zone,
                                    data_classification=data_class)

        if not _compare(actual, op, val):
            return False
    return True


def _check_relationship_conditions(conditions: list, ctx: dict) -> bool:
    """Check all conditions for a relationship rule."""
    for cond in conditions:
        field = cond.get("field", "")
        op = cond.get("operator", "")
        val = cond.get("value")

        if field == "crosses_trust_boundary":
            actual = ctx.get("crosses_trust_boundary", False)
        elif field.startswith("target_listener."):
            prop = field.split(".", 1)[1]
            tl = ctx.get("target_listener")
            actual = tl.get(prop) if tl else None
        elif field.startswith("relationship."):
            prop = field.split(".", 1)[1]
            actual = ctx.get("relationship", {}).get(prop)
        else:
            actual = None

        if not _compare(actual, op, val):
            return False
    return True


def _check_zone_conditions(conditions: list, zone: dict) -> bool:
    """Check all conditions for a zone rule."""
    for cond in conditions:
        field = cond.get("field", "")
        op = cond.get("operator", "")
        val = cond.get("value")

        prop = field.replace("zone.", "")
        actual = zone.get(prop)

        if not _compare(actual, op, val):
            return False
    return True


def _resolve_field(field: str, listener: dict | None = None, component: dict | None = None,
                   zone: dict | None = None, data_classification: str | None = None) -> object:
    """Resolve a dotted field path to a value."""
    if field.startswith("listener."):
        return (listener or {}).get(field.split(".", 1)[1])
    elif field.startswith("component."):
        return (component or {}).get(field.split(".", 1)[1])
    elif field.startswith("zone."):
        return (zone or {}).get(field.split(".", 1)[1])
    elif field == "data_classification":
        return data_classification
    return None


def _compare(actual, op: str, expected) -> bool:
    """Compare a value using an operator."""
    if op == "equals":
        return actual == expected
    elif op == "not_equals":
        return actual != expected
    elif op == "in":
        if isinstance(expected, list):
            return actual in expected
        return False
    elif op == "not_in":
        if isinstance(expected, list):
            return actual not in expected
        return False
    elif op == "greater_than":
        return (actual or 0) > (expected or 0)
    elif op == "less_than":
        return (actual or 0) < (expected or 0)
    return False


# =============================================================================
# Severity Computation
# =============================================================================

def _compute_severity(rule: dict, comp: dict, zone: dict | None,
                      listener: dict | None, data_class: str | None) -> str:
    """Compute effective severity with overrides."""
    base = rule.get("severity", "medium")

    for override in rule.get("severity_overrides", []):
        when = override.get("when", "")
        if _evaluate_override_when(when, comp=comp, zone=zone,
                                   listener=listener, data_class=data_class):
            base = override.get("then", base)

    return base


def _evaluate_override_when(when: str, comp: dict | None = None, zone: dict | None = None,
                            listener: dict | None = None, data_class: str | None = None) -> bool:
    """Evaluate a 'when' condition string from severity_overrides."""
    # Split on ' and ' for compound conditions
    parts = [p.strip() for p in when.split(" and ")]

    for part in parts:
        if not _evaluate_single_condition(part, comp, zone, listener, data_class):
            return False
    return True


def _evaluate_single_condition(cond: str, comp: dict | None, zone: dict | None,
                               listener: dict | None, data_class: str | None) -> bool:
    """Evaluate a single condition like 'zone.trust equals "trusted"'."""

    # Handle 'X in [a, b, c]'
    in_match = re.match(r'(.+?)\s+in\s+\[(.+?)\]', cond)
    if in_match:
        field = in_match.group(1).strip()
        values = [v.strip().strip('"').strip("'") for v in in_match.group(2).split(",")]
        actual = _resolve_override_field(field, comp, zone, listener, data_class)
        return actual in values

    # Handle 'X equals Y'
    eq_match = re.match(r'(.+?)\s+equals\s+(.+)', cond)
    if eq_match:
        field = eq_match.group(1).strip()
        value = eq_match.group(2).strip().strip('"').strip("'")
        actual = _resolve_override_field(field, comp, zone, listener, data_class)
        if value == "true":
            return actual is True
        elif value == "false":
            return actual is False
        return str(actual) == value

    return False


def _resolve_override_field(field: str, comp: dict | None, zone: dict | None,
                            listener: dict | None, data_class: str | None) -> object:
    """Resolve field references in override conditions."""
    if field.startswith("component."):
        return (comp or {}).get(field.split(".", 1)[1])
    elif field.startswith("zone."):
        return (zone or {}).get(field.split(".", 1)[1])
    elif field.startswith("listener."):
        return (listener or {}).get(field.split(".", 1)[1])
    elif field == "data_classification":
        return data_class
    return None


# =============================================================================
# Risk Acceptance Filtering
# =============================================================================

def _filter_accepted_risks(findings: list[Finding], accepted_risks: list[dict]) -> list[Finding]:
    """Remove findings that match accepted risk entries (unless expired)."""
    if not accepted_risks:
        return findings

    today = date.today().isoformat()
    active_acceptances = []
    for ar in accepted_risks:
        expires = ar.get("expires", "")
        if expires and expires < today:
            continue  # Expired — re-report
        active_acceptances.append(ar)

    if not active_acceptances:
        return findings

    filtered = []
    for finding in findings:
        suppressed = False
        for ar in active_acceptances:
            pattern = ar.get("finding_pattern", "")
            entity = ar.get("entity_id", "")
            if pattern == finding.rule_id:
                if not entity or entity in finding.entity_id:
                    suppressed = True
                    break
        if not suppressed:
            filtered.append(finding)

    return filtered


# =============================================================================
# Post-Evaluation Enrichment
# =============================================================================


def _infer_confidence(finding: Finding, model: ArchModel) -> str:
    """Infer confidence based on whether the triggering entity has explicit data.

    Returns 'high' if the entity has explicit security-relevant fields,
    'medium' if fields are absent (finding triggered on defaults/missing data),
    'low' for entities with minimal data.
    """
    entity_id = finding.entity_id
    # For listener findings (entity_id = "comp_id.listener_id")
    if finding.entity_type == "listener" and "." in entity_id:
        comp_id = entity_id.rsplit(".", 1)[0]
        comp = model.components.get(comp_id, {})
        listeners = comp.get("listeners", [])
        lid = entity_id.rsplit(".", 1)[1]
        listener = next((l for l in listeners if l.get("id") == lid), {})
        # If key security fields are explicitly set, high confidence
        explicit_fields = sum(1 for k in ("authn_mechanism", "tls_enabled", "authz_required")
                              if k in listener)
        if explicit_fields >= 2:
            return "high"
        elif explicit_fields >= 1:
            return "medium"
        return "low"
    elif finding.entity_type == "component":
        comp = model.components.get(entity_id, {})
        if comp.get("listeners") or comp.get("security_context"):
            return "high"
        return "medium"
    elif finding.entity_type == "zone":
        zone = model.zones.get(entity_id, {})
        if zone.get("trust") and zone.get("internet_routable") is not None:
            return "high"
        return "medium"
    return "high"


def enrich_findings(findings: list[Finding], compliance_map: dict,
                    model: ArchModel | None = None) -> list[Finding]:
    """Enrich findings with compliance mappings, confidence, and convergence scoring."""
    # 0. Infer confidence from entity data completeness
    if model:
        for finding in findings:
            finding.confidence = _infer_confidence(finding, model)

    # 1. Attach compliance framework references
    for finding in findings:
        mapping = compliance_map.get(finding.rule_id, {})
        if mapping:
            frameworks = []
            for framework, controls in mapping.items():
                if framework == "cwe":
                    continue  # Already in finding.cwe
                for ctrl in controls:
                    frameworks.append({"framework": framework, "control": ctrl})
            finding.compliance = frameworks

    # 2. Convergence scoring — boost risk for entities with multiple findings
    entity_findings: dict[str, list[Finding]] = {}
    for finding in findings:
        entity_findings.setdefault(finding.entity_id, []).append(finding)

    for entity_id, entity_group in entity_findings.items():
        count = len(entity_group)
        if count >= 3:
            # Convergence multiplier: 3+ distinct rules on same entity = high-confidence attack surface
            multiplier = min(1.5, 1.0 + (count - 2) * 0.1)
            for f in entity_group:
                f.risk_score = round(min(10.0, f.risk_score * multiplier), 1)
                if count >= 5:
                    f.confidence = "high"  # Multiple vectors confirm the issue

    return findings


# =============================================================================
# Output Formatters
# =============================================================================

def format_json(findings: list[Finding]) -> str:
    """JSON output."""
    return json.dumps({
        "findings_count": len(findings),
        "findings": [f.to_dict() for f in findings],
    }, indent=2)


def format_table(findings: list[Finding]) -> str:
    """Human-readable table output."""
    lines = []
    lines.append("=" * 80)
    lines.append("  Doc2ArchAgent Threat Analysis Report")

    severity_counts = {}
    for f in findings:
        severity_counts[f.severity] = severity_counts.get(f.severity, 0) + 1

    count_str = "  |  ".join(f"{s.upper()}: {c}" for s, c in
                             sorted(severity_counts.items(),
                                    key=lambda x: SEVERITY_ORDER.get(x[0], 0), reverse=True))
    lines.append(f"  Total Findings: {len(findings)}  |  {count_str}" if findings else "  No findings.")
    lines.append("=" * 80)

    if not findings:
        return "\n".join(lines)

    # Group by severity
    for sev in ["critical", "high", "medium", "low", "info"]:
        sev_findings = [f for f in findings if f.severity == sev]
        if not sev_findings:
            continue
        lines.append(f"\n  [{sev.upper()}]")
        for i, f in enumerate(sev_findings, 1):
            cwe_str = f"CWE-{f.cwe}" if f.cwe else "N/A"
            stride_str = f.stride.upper() if f.stride else "N/A"
            lines.append(f"  {i}. [{f.rule_id}] {f.title}")
            lines.append(f"     Entity: {f.entity_type}:{f.entity_id}")
            lines.append(f"     STRIDE: {stride_str}  |  CWE: {cwe_str}  |  Confidence: {f.confidence}  |  Risk: {f.risk_score}")
            if f.compliance:
                frameworks = set(c["framework"] for c in f.compliance)
                lines.append(f"     Compliance: {', '.join(sorted(frameworks))}")
            if f.severity_reason:
                lines.append(f"     Reason: {f.severity_reason}")
            lines.append(f"     Fix: {f.remediation}")
            lines.append("")

    return "\n".join(lines)


def format_sarif(findings: list[Finding], file_path: str = "") -> str:
    """SARIF 2.1.0 output for GitHub Security tab."""
    rules = {}
    results = []

    for f in findings:
        if f.rule_id not in rules:
            rule_def = {
                "id": f.rule_id,
                "name": f.title,
                "shortDescription": {"text": f.title},
                "fullDescription": {"text": f.description.strip()},
                "defaultConfiguration": {
                    "level": {"critical": "error", "high": "error", "medium": "warning",
                              "low": "note", "info": "note"}.get(f.severity, "warning")
                },
                "properties": {},
            }
            tags = []
            if f.cwe:
                tags.append(f"CWE-{f.cwe}")
            if f.stride:
                tags.append(f"STRIDE:{f.stride}")
                rule_def["properties"]["stride"] = f.stride
            if tags:
                rule_def["properties"]["tags"] = tags
            rule_def["properties"]["precision"] = "high"
            rules[f.rule_id] = rule_def

        fingerprint = hashlib.md5(
            f"{f.rule_id}:{f.entity_type}:{f.entity_id}".encode(),
            usedforsecurity=False,
        ).hexdigest()

        result_props = {
            "severity": f.severity,
            "confidence": f.confidence,
            "risk_score": f.risk_score,
        }
        if f.compliance:
            result_props["compliance"] = [
                f"{c['framework']}:{c['control']}" for c in f.compliance
            ]

        results.append({
            "ruleId": f.rule_id,
            "level": {"critical": "error", "high": "error", "medium": "warning",
                      "low": "note", "info": "note"}.get(f.severity, "warning"),
            "message": {"text": f"{f.title} — {f.entity_type}:{f.entity_id}. {f.remediation}"},
            "locations": [{
                "physicalLocation": {
                    "artifactLocation": {"uri": file_path or "system.yaml"},
                    "region": {"startLine": 1}
                }
            }],
            "fingerprints": {"primaryLocationLineHash": fingerprint},
            "properties": result_props,
        })

    sarif = {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/sarif-2.1/schema/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {
                "driver": {
                    "name": "Doc2ArchAgent Threat Rules",
                    "version": "1.0.0",
                    "informationUri": "https://github.com/Michael-JRead/Doc2ArchAgent",
                    "rules": list(rules.values()),
                }
            },
            "results": results,
        }]
    }
    return json.dumps(sarif, indent=2)


# =============================================================================
# CLI
# =============================================================================

def _load_security_file(explicit_path: str | None, base_path: str | None,
                        default_name: str) -> dict | None:
    """Load a security overlay YAML file. Auto-detects sibling if not explicit."""
    if explicit_path:
        try:
            with open(explicit_path) as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"Warning: Cannot load security file {explicit_path}: {e}", file=sys.stderr)
            return None
    if base_path:
        candidate = Path(base_path).parent / default_name
        if candidate.exists():
            with open(candidate) as f:
                return yaml.safe_load(f) or {}
    return None


def main():
    parser = argparse.ArgumentParser(description="Deterministic threat rule engine for Doc2ArchAgent.")
    parser.add_argument("system_yaml", help="Path to system.yaml")
    parser.add_argument("--networks", help="Path to networks.yaml")
    parser.add_argument("--deployment", help="Path to deployment YAML")
    parser.add_argument("--security", help="Path to system-security.yaml")
    parser.add_argument("--networks-security", help="Path to networks-security.yaml")
    parser.add_argument("--deployment-security", help="Path to deployment-security.yaml")
    parser.add_argument("--format", choices=["json", "table", "sarif"], default="table")
    parser.add_argument("--environment", choices=["development", "staging", "production", "dr"])
    parser.add_argument("--confidence-threshold", type=float, default=0.95,
                        help="Confidence threshold (0.0-1.0). Default 0.95")
    args = parser.parse_args()

    # Load base files
    try:
        with open(args.system_yaml) as f:
            system = yaml.safe_load(f) or {}
    except Exception as e:
        print(json.dumps({"error": f"Cannot load system YAML: {e}"}))
        sys.exit(1)

    networks = None
    if args.networks:
        with open(args.networks) as f:
            networks = yaml.safe_load(f) or {}

    deployment = None
    if args.deployment:
        with open(args.deployment) as f:
            deployment = yaml.safe_load(f) or {}

    # Load security overlay files (explicit or auto-detect)
    sys_sec = _load_security_file(args.security, args.system_yaml, "system-security.yaml")
    net_sec = _load_security_file(
        getattr(args, "networks_security", None),
        args.networks, "networks-security.yaml") if args.networks else None
    dep_sec = _load_security_file(
        getattr(args, "deployment_security", None),
        args.deployment, "deployment-security.yaml") if args.deployment else None

    # Merge security overlays into base dicts (additive, before model construction)
    system, networks, deployment = merge_security_overlays(
        system, networks, deployment, sys_sec, net_sec, dep_sec)

    # Build model
    model = ArchModel(system, networks, deployment)

    # Load rules and applicability
    rules = load_rules()
    applicability = load_applicability()

    # Evaluate
    findings = evaluate_rules(model, rules, applicability,
                              environment=args.environment, file_path=args.system_yaml)

    # Post-evaluation enrichment: compliance mappings, confidence, convergence scoring
    compliance_map = load_compliance_mapping()
    findings = enrich_findings(findings, compliance_map, model)

    # Sort by risk score (highest first), then severity
    findings.sort(key=lambda f: (SEVERITY_ORDER.get(f.severity, 0), f.risk_score), reverse=True)

    # Output
    if args.format == "json":
        print(format_json(findings))
    elif args.format == "sarif":
        print(format_sarif(findings, args.system_yaml))
    else:
        print(format_table(findings))

    # Exit code
    has_errors = any(SEVERITY_ORDER.get(f.severity, 0) >= SEVERITY_ORDER.get("high", 3) for f in findings)
    sys.exit(1 if has_errors else 0)


if __name__ == "__main__":
    main()
