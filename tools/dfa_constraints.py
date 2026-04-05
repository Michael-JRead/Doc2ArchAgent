#!/usr/bin/env python3
# Copyright (c) 2026 Michael J. Read. All rights reserved.
# SPDX-License-Identifier: BUSL-1.1
"""
Data Flow Constraint Analysis for Doc2ArchAgent.

Defines security policies as formal constraints on architecture YAML,
then validates data flows against those policies deterministically.
Inspired by the xDECAF (DataFlowAnalysis) framework.

Usage:
    python tools/dfa_constraints.py <system.yaml> [--policies <policies.yaml>] [--format json|table]

Exit codes:
    0 — No violations
    1 — Violations found (non-critical)
    2 — Critical violations found
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


class Violation:
    """A single constraint violation."""

    def __init__(
        self,
        rule_id: str,
        severity: str,
        entity_type: str,
        entity_id: str,
        detail: str,
        recommendation: str,
    ):
        self.rule_id = rule_id
        self.severity = severity
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.detail = detail
        self.recommendation = recommendation

    def to_dict(self) -> Dict[str, str]:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "detail": self.detail,
            "recommendation": self.recommendation,
        }


def _default_policies() -> Dict[str, Any]:
    """Built-in default constraint policies."""
    return {
        "constraints": [
            {
                "id": "no-pii-to-untrusted",
                "severity": "CRITICAL",
                "enabled": True,
                "description": "Confidential/restricted data must not flow to untrusted zones",
            },
            {
                "id": "tls-at-boundary",
                "severity": "HIGH",
                "enabled": True,
                "description": "TLS required at all trust boundary crossings",
            },
            {
                "id": "auth-at-entry",
                "severity": "HIGH",
                "enabled": True,
                "description": "Authentication required on all internet-facing listeners",
            },
            {
                "id": "no-direct-db-from-dmz",
                "severity": "HIGH",
                "enabled": True,
                "description": "DMZ components must not directly access data tier",
            },
            {
                "id": "authz-on-sensitive-data",
                "severity": "HIGH",
                "enabled": True,
                "description": "Authorization required on listeners serving sensitive data",
            },
            {
                "id": "no-plaintext-credentials",
                "severity": "CRITICAL",
                "enabled": True,
                "description": "Credential-bearing flows must use TLS",
            },
            {
                "id": "zone-isolation",
                "severity": "MEDIUM",
                "enabled": True,
                "description": "Management zone should not be directly accessible from DMZ",
            },
            {
                "id": "least-privilege-ports",
                "severity": "MEDIUM",
                "enabled": True,
                "description": "No admin ports (22, 3389) exposed in DMZ",
            },
        ]
    }


class ConstraintChecker:
    """Checks architecture YAML against formal security constraints."""

    def __init__(
        self,
        system: Dict[str, Any],
        networks: Dict[str, Any],
        deployments: Optional[List[Dict[str, Any]]] = None,
        policies: Optional[Dict[str, Any]] = None,
    ):
        self.system = system or {}
        self.networks = networks or {}
        self.deployments = deployments or []
        self.policies = policies or _default_policies()
        self.violations: List[Violation] = []

    def _get_component(self, comp_id: str) -> Optional[Dict[str, Any]]:
        for comp in self.system.get("components", []):
            if comp.get("id") == comp_id:
                return comp
        return None

    def _get_container(self, cont_id: str) -> Optional[Dict[str, Any]]:
        for cont in self.system.get("containers", []):
            if cont.get("id") == cont_id:
                return cont
        return None

    def _get_zone(self, zone_id: str) -> Optional[Dict[str, Any]]:
        for zone in self.networks.get("network_zones", []):
            if zone.get("id") == zone_id:
                return zone
        return None

    def _find_component_zone(self, comp_id: str) -> Optional[Dict[str, Any]]:
        """Find which zone a component is deployed in."""
        for deploy in self.deployments:
            dep = deploy.get("deployment", deploy)
            for placement in dep.get("zone_placements", []):
                zone_id = placement.get("zone_id", "")
                for container in placement.get("containers", []):
                    for component in container.get("components", []):
                        if component.get("component_id") == comp_id:
                            return self._get_zone(zone_id)
        return None

    def _get_listener(
        self, comp_id: str, listener_ref: str
    ) -> Optional[Dict[str, Any]]:
        comp = self._get_component(comp_id)
        if comp:
            for listener in comp.get("listeners", []):
                if listener.get("id") == listener_ref:
                    return listener
        return None

    def check_no_pii_to_untrusted(self) -> None:
        """Confidential/restricted data must not flow to untrusted zones."""
        for rel in self.system.get("component_relationships", []):
            classification = rel.get("data_classification", "")
            if classification in ("confidential", "restricted", "pii"):
                target_zone = self._find_component_zone(
                    rel.get("target_component", "")
                )
                if target_zone and target_zone.get("trust") == "untrusted":
                    self.violations.append(
                        Violation(
                            "no-pii-to-untrusted",
                            "CRITICAL",
                            "component_relationship",
                            rel.get("id", "unknown"),
                            f"'{classification}' data flows from "
                            f"'{rel.get('source_component')}' to "
                            f"'{rel.get('target_component')}' in untrusted "
                            f"zone '{target_zone.get('id')}'",
                            f"Move '{rel.get('target_component')}' to a trusted "
                            f"zone, or add encryption and access controls",
                        )
                    )

    def check_tls_at_boundary(self) -> None:
        """All flows crossing trust boundaries must use TLS."""
        for rel in self.system.get("component_relationships", []):
            source_zone = self._find_component_zone(
                rel.get("source_component", "")
            )
            target_zone = self._find_component_zone(
                rel.get("target_component", "")
            )
            if source_zone and target_zone:
                if source_zone.get("trust") != target_zone.get("trust"):
                    listener_ref = rel.get("target_listener_ref")
                    if listener_ref:
                        listener = self._get_listener(
                            rel.get("target_component", ""), listener_ref
                        )
                        if listener and not listener.get("tls_enabled", False):
                            self.violations.append(
                                Violation(
                                    "tls-at-boundary",
                                    "HIGH",
                                    "component_relationship",
                                    rel.get("id", "unknown"),
                                    f"Unencrypted flow from "
                                    f"'{rel.get('source_component')}' "
                                    f"({source_zone.get('id')}/"
                                    f"{source_zone.get('trust')}) to "
                                    f"'{rel.get('target_component')}' "
                                    f"({target_zone.get('id')}/"
                                    f"{target_zone.get('trust')})",
                                    f"Enable TLS on listener '{listener_ref}' "
                                    f"of '{rel.get('target_component')}'",
                                )
                            )

    def check_auth_at_entry(self) -> None:
        """All internet-facing listeners must have authentication."""
        for comp in self.system.get("components", []):
            comp_zone = self._find_component_zone(comp.get("id", ""))
            if comp_zone and comp_zone.get("internet_routable", False):
                for listener in comp.get("listeners", []):
                    if listener.get("authn_mechanism", "none") == "none":
                        self.violations.append(
                            Violation(
                                "auth-at-entry",
                                "HIGH",
                                "listener",
                                f"{comp.get('id')}/{listener.get('id')}",
                                f"Internet-facing listener "
                                f"'{listener.get('id')}' on "
                                f"'{comp.get('id')}' in zone "
                                f"'{comp_zone.get('id')}' has no "
                                f"authentication",
                                f"Add authentication (oauth2, mtls, api_key) "
                                f"to listener '{listener.get('id')}'",
                            )
                        )

    def check_no_direct_db_from_dmz(self) -> None:
        """DMZ components must not directly access database components."""
        for rel in self.system.get("component_relationships", []):
            source_zone = self._find_component_zone(
                rel.get("source_component", "")
            )
            target_comp = self._get_component(rel.get("target_component", ""))
            if (
                source_zone
                and source_zone.get("zone_type") == "dmz"
                and target_comp
                and target_comp.get("component_type")
                in ("database", "data_store")
            ):
                self.violations.append(
                    Violation(
                        "no-direct-db-from-dmz",
                        "HIGH",
                        "component_relationship",
                        rel.get("id", "unknown"),
                        f"DMZ component '{rel.get('source_component')}' "
                        f"directly accesses database "
                        f"'{rel.get('target_component')}'",
                        "Route through an application-tier intermediary",
                    )
                )

    def check_authz_on_sensitive_data(self) -> None:
        """Authorization required on listeners serving sensitive data."""
        for rel in self.system.get("component_relationships", []):
            classification = rel.get("data_classification", "")
            if classification in ("confidential", "restricted"):
                listener_ref = rel.get("target_listener_ref")
                if listener_ref:
                    listener = self._get_listener(
                        rel.get("target_component", ""), listener_ref
                    )
                    if listener and not listener.get("authz_required", False):
                        self.violations.append(
                            Violation(
                                "authz-on-sensitive-data",
                                "HIGH",
                                "listener",
                                f"{rel.get('target_component')}/{listener_ref}",
                                f"Listener '{listener_ref}' serves "
                                f"'{classification}' data without "
                                f"authorization",
                                f"Set authz_required: true and define "
                                f"authz_model on listener '{listener_ref}'",
                            )
                        )

    def check_zone_isolation(self) -> None:
        """Management zone should not be directly accessible from DMZ."""
        for rel in self.system.get("component_relationships", []):
            source_zone = self._find_component_zone(
                rel.get("source_component", "")
            )
            target_zone = self._find_component_zone(
                rel.get("target_component", "")
            )
            if (
                source_zone
                and target_zone
                and source_zone.get("zone_type") == "dmz"
                and target_zone.get("zone_type") == "management"
            ):
                self.violations.append(
                    Violation(
                        "zone-isolation",
                        "MEDIUM",
                        "component_relationship",
                        rel.get("id", "unknown"),
                        f"DMZ component '{rel.get('source_component')}' "
                        f"directly accesses management zone component "
                        f"'{rel.get('target_component')}'",
                        "Route management traffic through a bastion host "
                        "or jump server in an intermediate zone",
                    )
                )

    def check_least_privilege_ports(self) -> None:
        """No admin ports (22, 3389) exposed in DMZ."""
        admin_ports = {22, 3389, 5900}
        for comp in self.system.get("components", []):
            comp_zone = self._find_component_zone(comp.get("id", ""))
            if comp_zone and comp_zone.get("zone_type") == "dmz":
                for listener in comp.get("listeners", []):
                    port = listener.get("port")
                    if port and int(port) in admin_ports:
                        self.violations.append(
                            Violation(
                                "least-privilege-ports",
                                "MEDIUM",
                                "listener",
                                f"{comp.get('id')}/{listener.get('id')}",
                                f"Admin port {port} exposed on "
                                f"'{comp.get('id')}' in DMZ zone "
                                f"'{comp_zone.get('id')}'",
                                f"Move admin interface to management zone "
                                f"or restrict access via VPN/bastion",
                            )
                        )

    def check_all(self) -> List[Dict[str, str]]:
        """Run all enabled constraint checks."""
        enabled = {
            p["id"]
            for p in self.policies.get("constraints", [])
            if p.get("enabled", True)
        }

        check_map = {
            "no-pii-to-untrusted": self.check_no_pii_to_untrusted,
            "tls-at-boundary": self.check_tls_at_boundary,
            "auth-at-entry": self.check_auth_at_entry,
            "no-direct-db-from-dmz": self.check_no_direct_db_from_dmz,
            "authz-on-sensitive-data": self.check_authz_on_sensitive_data,
            "zone-isolation": self.check_zone_isolation,
            "least-privilege-ports": self.check_least_privilege_ports,
        }

        for check_id, check_fn in check_map.items():
            if check_id in enabled:
                check_fn()

        return [v.to_dict() for v in self.violations]


def format_table(result: Dict[str, Any]) -> str:
    """Format results as a human-readable table."""
    ca = result["constraint_analysis"]
    lines = [
        "",
        "=" * 70,
        f"DATA FLOW CONSTRAINT ANALYSIS — {ca['system']}",
        "=" * 70,
        f"Violations: {ca['violations_found']} "
        f"(CRITICAL: {ca['critical']}, HIGH: {ca['high']}, "
        f"MEDIUM: {ca['medium']})",
        "",
    ]

    if not ca["violations"]:
        lines.append("  No violations found.")
    else:
        for v in ca["violations"]:
            lines.append(f"[{v['severity']}] {v['rule_id']}")
            lines.append(f"  Entity: {v['entity_type']} / {v['entity_id']}")
            lines.append(f"  Detail: {v['detail']}")
            lines.append(f"  Fix: {v['recommendation']}")
            lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Data Flow Constraint Analysis for architecture YAML"
    )
    parser.add_argument("system_yaml", help="Path to system.yaml")
    parser.add_argument(
        "--networks",
        help="Path to networks.yaml (default: sibling or parent directory)",
    )
    parser.add_argument("--deployment", help="Path to deployment YAML")
    parser.add_argument("--policies", help="Path to policies YAML")
    parser.add_argument(
        "--format",
        choices=["json", "table"],
        default="table",
        help="Output format (default: table)",
    )
    args = parser.parse_args()

    system_path = Path(args.system_yaml)

    # Find networks.yaml
    if args.networks:
        networks_path = Path(args.networks)
    else:
        # Try sibling, then parent directory
        networks_path = system_path.parent / "networks.yaml"
        if not networks_path.exists():
            networks_path = system_path.parent.parent / "networks.yaml"

    # Load system
    with open(system_path) as f:
        system = yaml.safe_load(f) or {}

    # Load networks
    networks: Dict[str, Any] = {}
    if networks_path.exists():
        with open(networks_path) as f:
            networks = yaml.safe_load(f) or {}

    # Load deployments
    deployments: List[Dict[str, Any]] = []
    if args.deployment:
        with open(args.deployment) as f:
            deployments.append(yaml.safe_load(f) or {})
    else:
        # Search for deployment files
        deploy_dir = system_path.parent / "deployments"
        if deploy_dir.exists():
            for dp in deploy_dir.glob("*.yaml"):
                if "security" not in dp.name:
                    with open(dp) as f:
                        data = yaml.safe_load(f)
                        if data:
                            deployments.append(data)

    # Load policies
    policies = None
    if args.policies:
        policies_path = Path(args.policies)
        if policies_path.exists():
            with open(policies_path) as f:
                policies = yaml.safe_load(f)

    # Run checks
    checker = ConstraintChecker(system, networks, deployments, policies)
    violations = checker.check_all()

    result = {
        "constraint_analysis": {
            "system": system_path.stem,
            "violations_found": len(violations),
            "critical": len(
                [v for v in violations if v["severity"] == "CRITICAL"]
            ),
            "high": len(
                [v for v in violations if v["severity"] == "HIGH"]
            ),
            "medium": len(
                [v for v in violations if v["severity"] == "MEDIUM"]
            ),
            "violations": violations,
        }
    }

    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        print(format_table(result))

    # Exit code based on severity
    if any(v["severity"] == "CRITICAL" for v in violations):
        sys.exit(2)
    elif violations:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
