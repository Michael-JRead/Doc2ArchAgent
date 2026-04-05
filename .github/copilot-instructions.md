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

# Detect available tools (cross-platform — replaces detect-tools.sh)
python tools/detect-tools.py

# Validate patterns (supports both legacy and directory formats)
python tools/validate-patterns.py patterns/networks/
python tools/validate-patterns.py patterns/products/

# Compose deployment from manifest
python tools/compose.py deployments/<id>/manifest.yaml --validate

# Migrate legacy pattern to directory format
python tools/migrate-pattern.py patterns/products/messaging/ibm-mq.pattern.yaml

# Classify document sections by concern (network vs product)
python tools/classify-sections.py <document> --dry-run
python tools/classify-sections.py <document> --output-dir <pattern-dir>/contexts/sources/
```

## Agent Coordination

### Agent Hierarchy
- **@architect** — Primary entry point and orchestrator for interactive modeling
- **@doc-collector** → **@doc-extractor** — Document ingestion pipeline
- **@diagram-generator** — Diagram orchestration hub, dispatches to 5 renderers (@diagram-mermaid, @diagram-plantuml, @diagram-drawio, @diagram-structurizr, @diagram-d2)
- **@validator** and **@security-reviewer** — Read-only analysis agents (report issues, never fix them)
- **@deployer** and **@pattern-manager** — Domain-specific modeling agents
- **@doc-writer** — Documentation generation from architecture YAML
- **@diagram-diff** — Architecture version comparison

### Handoff Protocol
When handing off to another agent:
1. Summarize current state (which files exist, what was just completed)
2. Specify the exact task for the target agent
3. List relevant file paths the target agent should read
4. Include security overlay file paths when applicable (`system-security.yaml`, `networks-security.yaml`, `deployment-security.yaml`)

### Self-Validation Rule
After any agent writes or modifies YAML, it MUST invoke validation before handing off:
```bash
python tools/validate.py <file> --format table
```
If validation fails, fix the errors before handing off. Never pass invalid YAML downstream.

## Do NOT Touch

These files and directories are protected — agents must never modify them:
- `schemas/` — Source of truth for validation (JSON Schema files)
- `context/*.yaml` — Curated threat rules, compliance mappings, risk scoring
- Generated files in `deployments/*/` marked with `GENERATED` header — modify the manifest or source patterns instead
- Custom diagrams in any `diagrams/custom/` directory — hand-crafted, never overwritten
- License files: `LICENSE`, `LICENSE-COMMERCIAL.md`, `CLA.md`, `NOTICE`

## Instincts (Shared Behavioral Patterns)

The `instincts/` directory contains behavioral rules that apply across ALL agents at ALL times:
- **zero-hallucination** — Never infer or assume; extract only stated facts
- **yaml-hygiene** — Kebab-case IDs, required fields, incremental writing
- **progress-reporting** — Consistent status indicators and progress banners
- **handoff-protocol** — Validate before handoff, include context
- **user-confirmation** — Confirm before writing files
- **error-surfacing** — Never silently swallow errors
- **scope-enforcement** — Stay within declared file scope
- **provenance-awareness** — Track information sources

## Rules (Standards & Conventions)

The `rules/` directory contains standards and conventions that define WHAT to do:
- `rules/common/` — Language-agnostic rules: YAML formatting, naming conventions, file organization, git workflow, security, testing
- `rules/yaml/` — Schema-specific rules: system.yaml, networks.yaml, deployment.yaml
- `rules/diagrams/` — Diagram format rules: Mermaid, PlantUML, Draw.io

## Skills (On-Demand Knowledge)

The `.github/skills/` directory contains task-specific guidance loaded when relevant. Skills tell agents HOW to do things:
- **validate-yaml** — Deterministic validation commands and output interpretation
- **threat-analysis** — STRIDE threat evaluation and compliance mapping
- **confidence-scoring** — Provenance confidence assessment framework
- **diagram-workflow** — End-to-end diagram generation process
- **yaml-schema-guide** — Schema structure, required fields, and enum reference
- **document-ingestion** — Document collection and extraction pipeline
- **pattern-composition** — Deployment composition from patterns
- **c4-modeling** — 6-layer C4 modeling process (contexts → review)
- **security-analysis** — STRIDE methodology, ACL generation, blast radius, trust boundaries
- **deployment-mapping** — Zone placement and derived link computation
- **documentation-generation** — HLDD template and Confluence format
- **handoff-protocol** — Standardized agent-to-agent handoff format

## Shell Configuration

**Before running any `execute` commands**, read `.github/shell-config.yaml` to determine the user's shell.

- If the file does **not** exist, ask the user:
  > What shell/CLI does your VS Code terminal use?
  > 1. Linux (bash/sh/zsh)
  > 2. Mac (zsh/bash)
  > 3. Windows (PowerShell)
  > 4. Windows (cmd.exe)
  > 5. Other (describe it)

  Then create `.github/shell-config.yaml` with their choice.

- If the file exists, read `shell_type` and adapt commands per the table below.

### Command Translation Table

| Action | linux / mac | windows (PowerShell) | cmd |
|--------|-------------|----------------------|-----|
| List files | `ls <dir>` | `Get-ChildItem <dir>` | `dir <dir>` |
| Detect tools | `python tools/detect-tools.py` | `python tools/detect-tools.py` | `python tools/detect-tools.py` |
| Temp directory | `/tmp/` | `$env:TEMP/` | `%TEMP%\` |
| File redirect | `> /tmp/file.yaml` | `\| Out-File $env:TEMP/file.yaml` | `> %TEMP%\file.yaml` |
| Path separator | `/` | `/` (PowerShell handles both) | `\` |
| Python | `python` | `python` | `python` |
| Pip install | `pip install X` | `pip install X` | `pip install X` |

### When shell_type is "other"
Read `custom_shell_notes` for guidance. Default to Python-only execution (safest).
Ask the user before running any non-Python command.

### Universal Rule
All `tools/*.py` scripts are cross-platform. **Always prefer `python tools/X.py` over shell-specific commands.**

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

patterns/
  networks/
    _catalog.yaml                    # Hierarchical catalog of network patterns
    <region>/<pattern-id>/
      pattern.meta.yaml             # Pattern metadata and composition contract
      networks.yaml                 # Standalone networks.yaml (conforms to networks.schema.json)
  products/
    _catalog.yaml                    # Hierarchical catalog of product patterns
    <category>/<pattern-id>/
      pattern.meta.yaml             # Pattern metadata and composition contract
      system.yaml                   # Standalone system.yaml (conforms to system.schema.json)

deployments/
  _catalog.yaml                      # Catalog of deployment compositions
  <deployment-id>/
    manifest.yaml                    # Declares: 1 network + N products + placements
    networks.yaml                    # GENERATED — zone topology (read-only)
    networks-security.yaml           # GENERATED — zone security posture, infra resources (read-only)
    system.yaml                      # GENERATED — architecture core (read-only)
    system-security.yaml             # GENERATED — security overlay: CIA, TLS, auth (read-only)
    deployment.yaml                  # GENERATED — zone placements (read-only)
    deployment-security.yaml         # GENERATED — runtime security: image signing, etc. (read-only)
    diagrams/                        # Deployment-scoped diagrams
      _index.yaml                    # Diagram catalog (conforms to diagram-index.schema.json)
      custom/                        # Hand-crafted diagrams (never overwritten)
```

## Pattern System

Patterns are reusable architecture templates organized in two hierarchies:

- **Network patterns** contain a standalone `networks.yaml` defining zones and infrastructure resources
- **Product patterns** contain a standalone `system.yaml` defining contexts, containers, components, and relationships

### Unified Patterns (Multi-File)

Any pattern can optionally include BOTH `networks.yaml` AND `system.yaml`, plus dataflow files:
- **Network patterns** may include `system.yaml` (e.g., WAF, load balancer as C4 containers) and dataflow files
- **Product patterns** may include `networks.yaml` (e.g., product-specific isolation zones) and dataflow files
- Pop-and-swap is atomic — swapping a pattern removes/adds ALL its files as a unit

Each pattern directory has:
- `pattern.meta.yaml` — metadata, version, audience, files list, composition contract
- `networks.yaml` — zone definitions (required for network patterns, optional for product patterns)
- `system.yaml` — containers/components (required for product patterns, optional for network patterns)
- `app-dataflows.yaml` — **optional** application-to-application traffic flows
- `human-dataflows.yaml` — **optional** human user-facing traffic flows
- `contexts/` — per-pattern context hierarchy:
  - `_context.yaml` — C4 Level 1 context definitions for this pattern
  - `sources/` — source documents used to build this pattern
  - `sources/doc-inventory.yaml` — inventory of collected documents
  - `provenance.yaml` — entity-to-source evidence mapping

### Audience and Purpose

- **`audience`** (in `pattern.meta.yaml`): `application`, `human`, `hybrid`, or `infrastructure` — describes who the pattern serves
- **`purpose`** (in manifest `networks[]` entries): `application`, `human`, `hybrid`, `management`, or `other` — deployment-specific labeling
- **DO NOT assume audience.** Always validate with the user what audience a pattern serves.

### Dataflow Files

Both `app-dataflows.yaml` and `human-dataflows.yaml` follow `schemas/dataflows.schema.json`:
- **Zone-level flows:** `source_zone` / `target_zone` (references zones in `networks.yaml`)
- **Component-level flows:** `source_component` / `target_component` (references components in `system.yaml`)
- Both can coexist in the same file
- Each file declares `audience: application|human|hybrid|infrastructure` in `dataflow_metadata`

### Context Separation Rule

- **Network patterns:** contexts describe network topology concerns (e.g., "US East Data Center Network")
- **Product patterns:** contexts describe product functionality (e.g., "IBM MQ Messaging Platform")
- A product pattern MAY reference network requirements (ports, protocols) — this is the product's view of what it needs from the network, not the network topology itself

### Document Classification

When vendor documents contain mixed content (both network and product info), use:
```bash
python tools/classify-sections.py <document> --dry-run          # Preview classification
python tools/classify-sections.py <document> --output-dir <dir> # Split and write
```

The `@doc-collector` agent prompts users to select pattern type and auto-routes documents to the correct pattern's `contexts/sources/`.

### Composition via Deployment Manifests

Users compose deployments by selecting one or more networks + N products in a `manifest.yaml`:

```bash
python tools/compose.py deployments/<id>/manifest.yaml --validate
```

#### Multi-Network Manifests

Manifests support both singular (`network:`) and plural (`networks:`) syntax:
- `network:` — single network pattern (backward compatible)
- `networks:` — array of network patterns, each with `id_prefix`, `purpose`, and `pattern_ref`
- Use one or the other, never both
- Each `id_prefix` must be globally unique across ALL patterns (network + product)
- `cross_network_links` explicitly connect zones from different network patterns

The compose tool:
1. Resolves pattern references and verifies pinned versions
2. Applies unique `id_prefix` per pattern to prevent ID conflicts
3. Merges all network zones (from network patterns + product patterns) with collision detection
4. Merges `_context.yaml` files from all patterns into the composed system
5. Merges into composed `system.yaml` + `networks.yaml` + `deployment.yaml` + dataflow files
6. Applies cross-network links between zones from different patterns
7. Validates the composed output

**Do not hand-edit generated files.** Modify the manifest or source patterns instead.

## Diagram Hierarchy

Diagrams are stored scoped to their deployment or pattern, not in a flat global directory.

### Deployment-Scoped Diagrams
```
deployments/<deployment-id>/diagrams/
  _index.yaml              # Diagram catalog (conforms to diagram-index.schema.json)
  layout-plan.yaml         # Intermediate orchestration plan
  <scope-id>-context.md    # Mermaid context
  <scope-id>-containers.md # Mermaid containers
  <scope-id>.dsl           # Structurizr DSL (all levels)
  custom/                  # Hand-crafted diagrams (never overwritten)
```

### Pattern Reference Diagrams
```
patterns/<type>/<category>/<pattern-id>/diagrams/
  _index.yaml              # Diagram catalog for standalone pattern preview
```

### Naming Convention
`<scope-id>-<level>[-<detail>].<format>`

| Element | Values |
|---------|--------|
| scope-id | Deployment ID or pattern ID |
| level | `context`, `containers`, `component`, `deployment`, `network`, `threat-model` |
| detail | Optional: container scope for component diagrams |
| format | `.md` (Mermaid), `.puml`, `.drawio`, `.dsl`, `.d2` |

### PlantUML Security Overlay Rules
When generating security overlay `.puml` diagrams: ALL colors must use hex codes (`#2e7d32`), never named colors (`green`) — named colors cause `No such color` errors in C4 tag macros. Escape all `/` in protocol strings as `~/~/` to prevent Creole italic rendering. Use `$lineStyle=DashedLine()` (macro), not `$lineStyle="dashed"` (string). Trust zone tag names use underscores: `semi_trusted` not `semi-trusted`.

### _index.yaml
Each `diagrams/` directory contains `_index.yaml` cataloging all generated and custom diagrams. The `@doc-writer` agent reads this to discover diagrams without globbing. Schema: `diagram-index.schema.json`.

## Schema Validation

All YAML files are validated against JSON Schemas in `schemas/`:
- `system.schema.json` — system.yaml (architecture core)
- `system-security.schema.json` — system-security.yaml (security overlay: CIA, TLS, auth, compliance)
- `networks.schema.json` — networks.yaml (zone topology)
- `networks-security.schema.json` — networks-security.yaml (security overlay: zone posture, infra resources)
- `deployment.schema.json` — deployment YAML (zone placements)
- `deployment-security.schema.json` — deployment-security.yaml (security overlay: runtime hardening)
- `provenance.schema.json` — provenance.yaml
- `pattern-meta.schema.json` — pattern.meta.yaml
- `manifest.schema.json` — deployment manifest (supports both singular `network:` and plural `networks:`)
- `dataflows.schema.json` — app-dataflows.yaml / human-dataflows.yaml
- `context.schema.json` — pattern _context.yaml
- `doc-inventory.schema.json` — pattern doc-inventory.yaml
- `diagram-index.schema.json` — diagram _index.yaml catalog

Run validation: `python tools/validate.py <system.yaml> [networks.yaml] [--security system-security.yaml] [--networks-security networks-security.yaml] --format table`

## Enum Values (Use ONLY These)

### container_type
`api_gateway`, `application_server`, `web_app`, `database`, `message_queue`, `cache`, `file_storage`, `cdn`, `reverse_proxy`, `load_balancer`, `batch_processor`, `stream_processor`, `search_engine`, `monitoring`, `logging`, `identity_provider`, `other`

### component_type
`api`, `service`, `database`, `cache`, `message_consumer`, `message_producer`, `scheduled_task`, `web_frontend`, `worker`, `proxy`, `function`, `health_check`, `metrics`, `other`

### authn_mechanism
`none`, `api_key`, `basic`, `oauth2`, `oidc`, `saml`, `mtls`, `certificate`, `jwt`, `mfa`, `password`, `custom`

### authz_model
`none`, `rbac`, `abac`, `acl`, `pbac`, `rebac`, `custom`

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
