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
