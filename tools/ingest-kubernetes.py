#!/usr/bin/env python3
# Copyright (c) 2026 Michael J. Read. All rights reserved.
# SPDX-License-Identifier: BUSL-1.1
"""Deterministic Kubernetes manifest → Doc2ArchAgent YAML converter.

Parses Kubernetes YAML manifests to extract:
  - Deployments/StatefulSets/DaemonSets → Components
  - Services → Listeners (protocol, port, targetPort)
  - NetworkPolicies → Trust boundaries / firewall rules
  - Ingress/IngressRoute → Internet-routable zone placement
  - Namespaces → Network zones
  - ConfigMaps/Secrets → Data entities (metadata only, no values)

Usage:
    python tools/ingest-kubernetes.py <path-to-manifests> [--output <dir>]

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


def parse_kubernetes_manifests(content: str) -> dict:
    """Parse Kubernetes YAML manifests and extract architecture entities.

    Handles multi-document YAML files (separated by ---).
    """
    entities = {
        "containers": [],
        "components": [],
        "network_zones": [],
        "infrastructure_resources": [],
        "listeners": [],
        "data_entities": [],
        "trust_boundaries": [],
        "metadata": {"source_format": "kubernetes", "parser": "k8s-yaml"},
    }

    # Parse multi-document YAML
    docs = []
    try:
        for doc in yaml.safe_load_all(content):
            if doc and isinstance(doc, dict):
                docs.append(doc)
    except yaml.YAMLError:
        return entities

    # First pass: index services by selector for cross-referencing
    services_by_selector = {}
    for doc in docs:
        kind = doc.get("kind", "")
        if kind == "Service":
            metadata = doc.get("metadata", {})
            spec = doc.get("spec", {})
            selector = spec.get("selector", {})
            if selector:
                key = _selector_key(selector)
                services_by_selector[key] = {
                    "name": metadata.get("name", "unknown"),
                    "namespace": metadata.get("namespace", "default"),
                    "spec": spec,
                }

    # Second pass: process all resources
    for doc in docs:
        kind = doc.get("kind", "")
        metadata = doc.get("metadata", {})
        spec = doc.get("spec", {})

        if kind in ("Deployment", "StatefulSet", "DaemonSet"):
            _process_workload(kind, metadata, spec, services_by_selector, entities)
        elif kind == "Service":
            _process_service(metadata, spec, entities)
        elif kind == "Namespace":
            _process_namespace(metadata, entities)
        elif kind == "NetworkPolicy":
            _process_network_policy(metadata, spec, entities)
        elif kind in ("Ingress", "IngressRoute"):
            _process_ingress(kind, metadata, spec, entities)
        elif kind in ("ConfigMap", "Secret"):
            _process_config_or_secret(kind, metadata, entities)
        elif kind == "PersistentVolumeClaim":
            _process_pvc(metadata, spec, entities)

    return entities


def _process_workload(kind: str, metadata: dict, spec: dict, services: dict, entities: dict):
    """Map Deployment/StatefulSet/DaemonSet to a component or container."""
    name = metadata.get("name", "unknown")
    namespace = metadata.get("namespace", "default")
    labels = metadata.get("labels", {})
    rid = _to_kebab(name)

    # Extract container images from pod template
    pod_spec = spec.get("template", {}).get("spec", {})
    containers = pod_spec.get("containers", [])
    images = [c.get("image", "unknown") for c in containers]

    # Determine technology from image names
    technology = _infer_technology(images)

    # Check if this workload has a matching service
    selector_key = _selector_key(labels)
    matched_service = services.get(selector_key)

    component_type = "service"
    if kind == "StatefulSet":
        component_type = "stateful_service"
    elif kind == "DaemonSet":
        component_type = "daemon"

    component = {
        "id": rid,
        "name": name,
        "component_type": component_type,
        "technology": technology,
        "namespace": namespace,
        "replicas": spec.get("replicas", 1),
        "images": images,
        "_source": f"kubernetes:{kind}.{namespace}.{name}",
    }

    # Extract container ports
    ports = []
    for container in containers:
        for port in container.get("ports", []):
            ports.append({
                "name": port.get("name", ""),
                "containerPort": port.get("containerPort"),
                "protocol": port.get("protocol", "TCP"),
            })
    if ports:
        component["ports"] = ports

    # Extract resource requests/limits
    for container in containers:
        resources = container.get("resources", {})
        if resources:
            component["resources"] = resources
            break  # Use first container's resources

    # Extract security context (pod-level + first container-level)
    pod_security_ctx = pod_spec.get("securityContext", {})
    container_security_ctx = containers[0].get("securityContext", {}) if containers else {}
    capabilities = container_security_ctx.get("capabilities", {})

    security_context = {}
    # Pod-level fields
    if "runAsNonRoot" in pod_security_ctx:
        security_context["run_as_non_root"] = pod_security_ctx["runAsNonRoot"]
    if "runAsUser" in pod_security_ctx:
        security_context["run_as_user"] = pod_security_ctx["runAsUser"]
    # Container-level fields (override pod-level)
    if "runAsNonRoot" in container_security_ctx:
        security_context["run_as_non_root"] = container_security_ctx["runAsNonRoot"]
    if "privileged" in container_security_ctx:
        security_context["privileged"] = container_security_ctx["privileged"]
    if "readOnlyRootFilesystem" in container_security_ctx:
        security_context["read_only_root_filesystem"] = container_security_ctx["readOnlyRootFilesystem"]
    if "allowPrivilegeEscalation" in container_security_ctx:
        security_context["allow_privilege_escalation"] = container_security_ctx["allowPrivilegeEscalation"]
    if capabilities.get("drop"):
        security_context["capabilities_drop"] = capabilities["drop"]
    if capabilities.get("add"):
        security_context["capabilities_add"] = capabilities["add"]

    # Map to deployment-security schema fields
    if security_context:
        component["security_context"] = security_context
        # Map to our standard fields for downstream threat rules
        component["runtime_user"] = (
            str(pod_security_ctx.get("runAsUser", "")) if pod_security_ctx.get("runAsUser") else ""
        )
        component["read_only_filesystem"] = security_context.get("read_only_root_filesystem", False)
        component["resource_limits_set"] = bool(component.get("resources", {}).get("limits"))

    # Extract host namespace sharing (security-relevant)
    if pod_spec.get("hostNetwork"):
        component["host_network"] = True
    if pod_spec.get("hostPID"):
        component["host_pid"] = True
    if pod_spec.get("hostIPC"):
        component["host_ipc"] = True

    # Check automountServiceAccountToken
    if pod_spec.get("automountServiceAccountToken") is False:
        component["automount_service_account_token"] = False

    entities["components"].append(component)


def _process_service(metadata: dict, spec: dict, entities: dict):
    """Map Service to listener entries."""
    name = metadata.get("name", "unknown")
    namespace = metadata.get("namespace", "default")
    rid = _to_kebab(name)
    svc_type = spec.get("type", "ClusterIP")

    for port in spec.get("ports", []):
        listener = {
            "id": f"{rid}-{port.get('port', 0)}",
            "service_name": name,
            "namespace": namespace,
            "service_type": svc_type,
            "protocol": port.get("protocol", "TCP"),
            "port": port.get("port"),
            "target_port": port.get("targetPort"),
            "node_port": port.get("nodePort"),
            "internet_facing": svc_type in ("LoadBalancer", "NodePort"),
            "_source": f"kubernetes:Service.{namespace}.{name}",
        }
        entities["listeners"].append(listener)


def _process_namespace(metadata: dict, entities: dict):
    """Map Namespace to a network zone."""
    name = metadata.get("name", "unknown")
    labels = metadata.get("labels", {})
    rid = _to_kebab(name)

    entities["network_zones"].append({
        "id": rid,
        "name": name,
        "zone_type": "namespace",
        "internet_routable": False,  # Conservative default
        "trust": _infer_trust_from_labels(labels, name),
        "description": f"Kubernetes namespace: {name}",
        "labels": labels,
        "_source": f"kubernetes:Namespace.{name}",
    })


def _process_network_policy(metadata: dict, spec: dict, entities: dict):
    """Map NetworkPolicy to trust boundary rules."""
    name = metadata.get("name", "unknown")
    namespace = metadata.get("namespace", "default")
    rid = _to_kebab(name)

    pod_selector = spec.get("podSelector", {})
    policy_types = spec.get("policyTypes", [])
    ingress_rules = spec.get("ingress", [])
    egress_rules = spec.get("egress", [])

    boundary = {
        "id": rid,
        "name": name,
        "namespace": namespace,
        "pod_selector": pod_selector.get("matchLabels", {}),
        "policy_types": policy_types,
        "ingress_rules": [],
        "egress_rules": [],
        "_source": f"kubernetes:NetworkPolicy.{namespace}.{name}",
    }

    for rule in ingress_rules:
        parsed_rule = {"ports": [], "from": []}
        for port in rule.get("ports", []):
            parsed_rule["ports"].append({
                "protocol": port.get("protocol", "TCP"),
                "port": port.get("port"),
            })
        for from_entry in rule.get("from", []):
            if "namespaceSelector" in from_entry:
                parsed_rule["from"].append({
                    "type": "namespace",
                    "selector": from_entry["namespaceSelector"].get("matchLabels", {}),
                })
            if "podSelector" in from_entry:
                parsed_rule["from"].append({
                    "type": "pod",
                    "selector": from_entry["podSelector"].get("matchLabels", {}),
                })
            if "ipBlock" in from_entry:
                parsed_rule["from"].append({
                    "type": "ipBlock",
                    "cidr": from_entry["ipBlock"].get("cidr", ""),
                    "except": from_entry["ipBlock"].get("except", []),
                })
        boundary["ingress_rules"].append(parsed_rule)

    for rule in egress_rules:
        parsed_rule = {"ports": [], "to": []}
        for port in rule.get("ports", []):
            parsed_rule["ports"].append({
                "protocol": port.get("protocol", "TCP"),
                "port": port.get("port"),
            })
        for to_entry in rule.get("to", []):
            if "namespaceSelector" in to_entry:
                parsed_rule["to"].append({
                    "type": "namespace",
                    "selector": to_entry["namespaceSelector"].get("matchLabels", {}),
                })
            if "podSelector" in to_entry:
                parsed_rule["to"].append({
                    "type": "pod",
                    "selector": to_entry["podSelector"].get("matchLabels", {}),
                })
            if "ipBlock" in to_entry:
                parsed_rule["to"].append({
                    "type": "ipBlock",
                    "cidr": to_entry["ipBlock"].get("cidr", ""),
                    "except": to_entry["ipBlock"].get("except", []),
                })
        boundary["egress_rules"].append(parsed_rule)

    entities["trust_boundaries"].append(boundary)


def _process_ingress(kind: str, metadata: dict, spec: dict, entities: dict):
    """Map Ingress to internet-facing infrastructure resource."""
    name = metadata.get("name", "unknown")
    namespace = metadata.get("namespace", "default")
    rid = _to_kebab(name)
    annotations = metadata.get("annotations", {})

    # Detect TLS
    tls_configs = spec.get("tls", [])
    tls_enabled = len(tls_configs) > 0

    # Extract hosts and paths
    rules = spec.get("rules", [])
    hosts = []
    paths = []
    for rule in rules:
        host = rule.get("host", "")
        if host:
            hosts.append(host)
        http = rule.get("http", {})
        for path_entry in http.get("paths", []):
            paths.append({
                "path": path_entry.get("path", "/"),
                "path_type": path_entry.get("pathType", "Prefix"),
                "backend_service": _extract_ingress_backend(path_entry.get("backend", {})),
            })

    entities["infrastructure_resources"].append({
        "id": rid,
        "name": name,
        "namespace": namespace,
        "resource_type": "ingress",
        "technology": _detect_ingress_controller(annotations),
        "internet_facing": True,
        "tls_enabled": tls_enabled,
        "hosts": hosts,
        "paths": paths,
        "zone_id": "unknown",
        "_source": f"kubernetes:{kind}.{namespace}.{name}",
    })


def _process_config_or_secret(kind: str, metadata: dict, entities: dict):
    """Map ConfigMap/Secret to data entity (metadata only, never values)."""
    name = metadata.get("name", "unknown")
    namespace = metadata.get("namespace", "default")
    rid = _to_kebab(name)

    entities["data_entities"].append({
        "id": rid,
        "name": name,
        "namespace": namespace,
        "entity_type": kind.lower(),
        "classification": "confidential" if kind == "Secret" else "internal",
        "description": f"Kubernetes {kind} in namespace {namespace}",
        "_source": f"kubernetes:{kind}.{namespace}.{name}",
    })


def _process_pvc(metadata: dict, spec: dict, entities: dict):
    """Map PersistentVolumeClaim to infrastructure resource."""
    name = metadata.get("name", "unknown")
    namespace = metadata.get("namespace", "default")
    rid = _to_kebab(name)

    entities["infrastructure_resources"].append({
        "id": rid,
        "name": name,
        "namespace": namespace,
        "resource_type": "storage",
        "technology": "PersistentVolumeClaim",
        "storage_class": spec.get("storageClassName", ""),
        "access_modes": spec.get("accessModes", []),
        "storage_size": spec.get("resources", {}).get("requests", {}).get("storage", ""),
        "zone_id": "unknown",
        "_source": f"kubernetes:PVC.{namespace}.{name}",
    })


def _selector_key(labels: dict) -> str:
    """Create a deterministic key from label selectors for service matching."""
    if not labels:
        return ""
    return "|".join(f"{k}={v}" for k, v in sorted(labels.items()))


def _infer_technology(images: list[str]) -> str:
    """Infer technology stack from container image names."""
    if not images:
        return "unknown"

    image = images[0].lower()
    tech_hints = {
        "nginx": "Nginx",
        "node": "Node.js",
        "python": "Python",
        "golang": "Go",
        "java": "Java",
        "openjdk": "Java",
        "postgres": "PostgreSQL",
        "mysql": "MySQL",
        "redis": "Redis",
        "mongo": "MongoDB",
        "elasticsearch": "Elasticsearch",
        "rabbitmq": "RabbitMQ",
        "kafka": "Apache Kafka",
        "envoy": "Envoy Proxy",
        "istio": "Istio",
        "traefik": "Traefik",
    }
    for hint, tech in tech_hints.items():
        if hint in image:
            return tech

    return "Kubernetes workload"


def _infer_trust_from_labels(labels: dict, name: str) -> str:
    """Infer trust level from namespace labels or well-known namespace names."""
    untrusted_names = {"public", "external", "dmz", "edge", "ingress"}
    semi_trusted_names = {"staging", "dev", "test", "sandbox"}

    if name in untrusted_names:
        return "untrusted"
    if name in semi_trusted_names:
        return "semi_trusted"

    # Check Istio/Linkerd injection labels as indicator of mesh trust
    if labels.get("istio-injection") == "enabled":
        return "trusted"

    return "trusted"


def _extract_ingress_backend(backend: dict) -> str:
    """Extract backend service name from Ingress backend spec."""
    # v1 format
    service = backend.get("service", {})
    if service:
        return service.get("name", "unknown")
    # Legacy format
    return backend.get("serviceName", "unknown")


def _detect_ingress_controller(annotations: dict) -> str:
    """Detect ingress controller type from annotations."""
    class_annotation = annotations.get("kubernetes.io/ingress.class", "")
    if class_annotation:
        return f"{class_annotation} Ingress Controller"

    if any("nginx" in k.lower() for k in annotations):
        return "Nginx Ingress Controller"
    if any("traefik" in k.lower() for k in annotations):
        return "Traefik Ingress Controller"
    if any("alb" in k.lower() or "aws" in k.lower() for k in annotations):
        return "AWS ALB Ingress Controller"

    return "Kubernetes Ingress"


def _to_kebab(name: str) -> str:
    """Convert a resource name to kebab-case."""
    s = re.sub(r'[A-Z]', lambda m: '-' + m.group(0).lower(), name)
    s = re.sub(r'[^a-z0-9-]', '-', s.lower())
    s = re.sub(r'-+', '-', s).strip('-')
    return s or "unknown"


def entities_to_yaml(entities: dict, output_dir: str):
    """Write extracted entities to Doc2ArchAgent YAML files."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    # Write networks.yaml
    if entities["network_zones"] or entities["infrastructure_resources"] or entities["trust_boundaries"]:
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
        if entities["trust_boundaries"]:
            networks["trust_boundaries"] = [
                {k: v for k, v in b.items() if not k.startswith("_")}
                for b in entities["trust_boundaries"]
            ]
        with open(output / "networks.yaml", "w") as f:
            f.write("# Auto-generated from Kubernetes manifests by ingest-kubernetes.py\n")
            f.write("# Review and refine with @architect before use.\n\n")
            yaml.dump(networks, f, default_flow_style=False, sort_keys=False)

    # Write system.yaml
    system = {"metadata": {
        "name": "Imported from Kubernetes",
        "description": "Auto-extracted from Kubernetes manifests",
        "owner": "TODO",
        "status": "proposed",
    }}
    if entities["components"]:
        system["components"] = [
            {k: v for k, v in c.items() if not k.startswith("_") and v is not None}
            for c in entities["components"]
        ]
    if entities["data_entities"]:
        system["data_entities"] = [
            {k: v for k, v in d.items() if not k.startswith("_")}
            for d in entities["data_entities"]
        ]
    with open(output / "system.yaml", "w") as f:
        f.write("# Auto-generated from Kubernetes manifests by ingest-kubernetes.py\n")
        f.write("# Review and refine with @architect before use.\n\n")
        yaml.dump(system, f, default_flow_style=False, sort_keys=False)

    print(json.dumps({
        "success": True,
        "output_dir": str(output),
        "entities": {
            "components": len(entities["components"]),
            "network_zones": len(entities["network_zones"]),
            "infrastructure_resources": len(entities["infrastructure_resources"]),
            "listeners": len(entities["listeners"]),
            "data_entities": len(entities["data_entities"]),
            "trust_boundaries": len(entities["trust_boundaries"]),
        },
    }, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Convert Kubernetes manifests to Doc2ArchAgent YAML.")
    parser.add_argument("path", help="Path to Kubernetes manifest file or directory")
    parser.add_argument("--output", help="Output directory for YAML files")
    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(json.dumps({"error": f"Path not found: {args.path}"}))
        sys.exit(1)

    # Collect files
    files = []
    if path.is_dir():
        files = list(path.glob("*.yaml")) + list(path.glob("*.yml"))
    else:
        files = [path]

    if not files:
        print(json.dumps({"error": f"No YAML files found at {args.path}"}))
        sys.exit(1)

    # Parse all files
    all_entities = {
        "containers": [], "components": [], "network_zones": [],
        "infrastructure_resources": [], "listeners": [], "data_entities": [],
        "trust_boundaries": [],
        "metadata": {"source_format": "kubernetes", "parser": "k8s-yaml"},
    }

    for f in files:
        content = f.read_text()
        entities = parse_kubernetes_manifests(content)
        for key in ("containers", "components", "network_zones", "infrastructure_resources",
                     "listeners", "data_entities", "trust_boundaries"):
            all_entities[key].extend(entities.get(key, []))

    if args.output:
        entities_to_yaml(all_entities, args.output)
    else:
        print(json.dumps(all_entities, indent=2, default=str))


if __name__ == "__main__":
    main()
