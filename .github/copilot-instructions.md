# Doc2ArchAgent — Copilot Custom Instructions

## Project Overview

Doc2ArchAgent is a suite of 15 specialized GitHub Copilot agents that extract, model, validate, and visualize software architecture from existing documentation. It follows the C4 model (Context, Container, Component, Deployment) with additional layers for network zones, trust boundaries, security analysis, and compliance mapping.

## Core Principles

### Zero-Hallucination Invariant
Every architecture entity extracted from documents MUST have a verifiable source citation in `provenance.yaml`. If the source document does not explicitly state something, it does not exist in the architecture model. Never infer, assume, or fill in "typical" architecture patterns.

### Separation Principle
- **Extraction:** LLM agents (`@doc-extractor`, `@doc-collector`)
- **Validation:** Deterministic Python code (`tools/validate.py`, `tools/threat-rules.py`) — same input always produces same output
- **Rendering:** Template-based agents (`@diagram-*`)

### Confidence Threshold
The default confidence threshold is **0.95** (95%). Entities below this threshold require human verification before inclusion. Users can adjust this in `metadata.confidence_threshold`.

## Naming Conventions

- All YAML entity IDs use **kebab-case**: `^[a-z][a-z0-9]*(-[a-z0-9]+)*$`
- File names: lowercase with hyphens (e.g., `payment-platform`, `prod-us-east.yaml`)
- Agent files: `<name>.agent.md` in `.github/agents/`
- Schema files: `<name>.schema.json` in `schemas/`

## File Structure

```
architecture/<system-id>/
  system.yaml          # C4 model (contexts, containers, components, relationships)
  provenance.yaml      # Per-field source citations and confidence scores
  deployments/         # Environment-specific zone placements
  diagrams/            # Generated diagrams (Mermaid, PlantUML, Draw.io, D2, Structurizr)
  docs/                # Generated documentation (HLDD, security findings)
architecture/
  networks.yaml        # Shared network zones and infrastructure resources
```

## Schema Validation

All YAML files are validated against JSON Schemas in `schemas/`:
- `system.schema.json` — system.yaml
- `networks.schema.json` — networks.yaml
- `deployment.schema.json` — deployment YAML
- `provenance.schema.json` — provenance.yaml

Run validation: `python tools/validate.py <system.yaml> [networks.yaml] --format table`

## Enum Values (Use ONLY These)

### container_type
`api_gateway`, `application_server`, `web_app`, `database`, `message_queue`, `cache`, `file_storage`, `cdn`, `reverse_proxy`, `load_balancer`, `batch_processor`, `stream_processor`, `search_engine`, `monitoring`, `logging`, `identity_provider`, `other`

### component_type
`api`, `service`, `database`, `cache`, `message_consumer`, `message_producer`, `scheduled_task`, `web_frontend`, `worker`, `proxy`, `function`, `health_check`, `metrics`, `other`

### authn_mechanism
`none`, `api_key`, `basic`, `oauth2`, `oidc`, `saml`, `mtls`, `certificate`, `jwt`, `mfa`, `password`, `custom`

### data_classification
`public`, `internal`, `confidential`, `restricted`

### environment
`development`, `staging`, `production`, `dr`

### trust
`trusted`, `semi_trusted`, `untrusted`

### encryption_at_rest
`none`, `aes-256`, `aes-128`, `rsa`, `envelope`, `platform_managed`, `customer_managed`

### encryption_key_management
`provider_managed`, `customer_managed`, `byok`, `hsm`, `vault`

### confidentiality / integrity / availability (CIA triad)
`critical`, `high`, `medium`, `low`

### business_criticality
`mission_critical`, `critical`, `important`, `operational`, `archive`

### dfd_element_type (STRIDE-per-element)
`process`, `data_store`, `external_entity`

### cipher_suite_policy
`modern`, `intermediate`, `legacy`, `custom`

### certificate_type
`dv`, `ov`, `ev`, `self_signed`, `internal_ca`, `none`

### mtls_mode
`none`, `optional`, `strict`

### tls_termination_point
`self`, `load_balancer`, `api_gateway`, `service_mesh`, `cdn`

### exposure (listener scope)
`public`, `partner`, `internal`, `localhost`

### api_type
`rest`, `graphql`, `grpc`, `soap`, `websocket`, `tcp_raw`, `udp`

### error_detail_exposure
`none`, `generic`, `detailed`, `stack_trace`

### cors_policy
`none`, `restrictive`, `permissive`, `wildcard`

### throttle_by
`ip`, `api_key`, `user`, `tenant`, `none`

### external_system category
`partner`, `vendor`, `saas`, `open_source`, `government`, `customer`, `other`

### sla_tier
`platinum`, `gold`, `silver`, `bronze`, `none`

### trust_boundary boundary_type
`network`, `process`, `privilege`, `jurisdiction`, `vendor`

### trust_boundary enforcement_mechanism
`firewall`, `api_gateway`, `service_mesh`, `iam_policy`, `physical`, `none`

### interaction_type (component_relationships)
`request_response`, `publish_subscribe`, `fire_and_forget`, `streaming`, `batch`

### input_validation
`none`, `schema`, `allowlist`, `waf`, `custom`

### data_entity data_subject_type
`customer`, `employee`, `partner`, `public`, `system`

### data_entity origin
`user_input`, `system_generated`, `third_party`, `derived`

### data_entity volume
`low`, `medium`, `high`, `very_high`

### zone segmentation_type
`physical`, `vlan`, `vpc`, `subnet`, `namespace`, `security_group`, `microsegment`, `none`

### deployment shared_responsibility_model
`iaas`, `paas`, `saas`, `on_prem`

### deployment tenant_isolation
`dedicated`, `shared`, `hybrid`

### deployment runtime_user
`root`, `non_root`, `unknown`

## Security-Enriched Fields Summary

### For Security Leads — Key Fields That Drive Threat Analysis

**Components:** `confidentiality`, `integrity`, `availability` (CIA triad), `dfd_element_type` (STRIDE-per-element), `stores_data`, `processes_pii`, `audit_logging`, `encryption_at_rest`, `encryption_key_management`, `slsa_level`, `sbom_available`, `rto_minutes`, `rpo_minutes`

**Listeners:** `cipher_suite_policy`, `forward_secrecy_required`, `certificate_type`, `mtls_mode`, `tls_termination_point`, `rate_limiting_enabled`, `rate_limit_rps`, `throttle_by`, `exposure`, `api_type`, `admin_interface`, `session_timeout_minutes`, `error_detail_exposure`, `cors_policy`

**Relationships:** `interaction_type`, `mutual_authentication`, `input_validation`, `replay_protection`, `data_masking`

**External Systems:** `trust_level`, `data_classification`, `authn_mechanism`, `tls_required`, `sla_tier`, `vendor_security_assessed`, `vendor_security_assessment_date`, `data_residency`

**Data Entities:** `contains_pii`, `contains_phi`, `contains_pci`, `data_subject_type`, `retention_days`, `residency_requirements`, `masking_required`, `origin`, `volume`

**Trust Boundaries:** `boundary_type`, `enforcement_mechanism`, `inspection_enabled`, `bidirectional`

**Network Zones:** `segmentation_type`, `egress_filtered`, `ids_ips_enabled`, `dlp_enabled`, `default_deny`, `allowed_ingress_zones`, `allowed_egress_zones`

**Deployments:** `data_residency_region`, `data_residency_required`, `shared_responsibility_model`, `tenant_isolation`, `replicas`, `runtime_user`, `read_only_filesystem`, `resource_limits_set`, `network_policy_enforced`, `image_signed`, `vulnerability_scan_date`

## Build and Test Commands

```bash
# Validate architecture
python tools/validate.py architecture/*/system.yaml --format table

# Run threat rules
python tools/threat-rules.py architecture/*/system.yaml --networks architecture/networks.yaml

# Run tests
python -m pytest tests/ -v

# Sync ATT&CK data
python tools/sync-attack-data.py
```

## Security Review

The `@security-reviewer` agent is read-only — it reports findings but does not modify architecture files. Security findings reference:
- `context/cwe-mappings.yaml` — CWE identifiers
- `context/stride-to-attack.yaml` — STRIDE → ATT&CK mapping
- `context/compliance-mappings.yaml` — PCI-DSS, SOC2, GDPR, HIPAA controls
- `context/risk-scoring.yaml` — Likelihood × Impact methodology
- `context/threat-rules.yaml` — Codified deterministic threat rules
- `context/threat-applicability.yaml` — Conditions for when threats apply

## License

BSL 1.1 — See LICENSE file.
