---
name: threat-analysis
description: Run deterministic STRIDE threat rule evaluation against architecture models with ATT&CK mapping and compliance analysis
allowed-tools: ['execute', 'read']
---

# Threat Analysis Skill

Run deterministic threat rule evaluation against Doc2ArchAgent architecture models. Uses YAML-based rules from `context/threat-rules.yaml` — no LLM involvement, same input always produces same output.

## Commands

### Basic threat analysis

```bash
python tools/threat-rules.py architecture/<system-id>/system.yaml --format table
```

### Full analysis with networks and deployment

```bash
python tools/threat-rules.py architecture/<system-id>/system.yaml \
    --networks architecture/networks.yaml \
    --deployment architecture/<system-id>/deployments/<env>.yaml \
    --format table
```

### Environment-specific analysis

```bash
python tools/threat-rules.py <system.yaml> \
    --networks <networks.yaml> \
    --environment production \
    --format table
```

Valid environments: `production`, `staging`, `development`, `dr`

### With confidence threshold

```bash
python tools/threat-rules.py <system.yaml> --confidence-threshold 0.90 --format table
```

### SARIF output for GitHub Security tab

```bash
python tools/threat-rules.py <system.yaml> --format sarif > threat-results.sarif
```

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | No findings above threshold |
| `1` | Findings found |

## STRIDE Methodology

The engine evaluates threats using STRIDE-per-element:

| Category | Target | Example |
|----------|--------|---------|
| **S**poofing | Authentication | Unauthenticated listeners, weak auth |
| **T**ampering | Integrity | Unencrypted data flows, missing signing |
| **R**epudiation | Audit | Missing audit logging |
| **I**nformation Disclosure | Confidentiality | Internet-exposed data stores, unencrypted channels |
| **D**enial of Service | Availability | Single points of failure, missing rate limits |
| **E**levation of Privilege | Authorization | Missing authorization, trust boundary violations |

## Context Files

The threat engine uses these deterministic rule files:

| File | Purpose |
|------|---------|
| `context/threat-rules.yaml` | Codified threat conditions and severity |
| `context/threat-applicability.yaml` | When each threat applies |
| `context/compliance-mappings.yaml` | PCI-DSS, SOC2, GDPR, HIPAA control mappings |
| `context/compliance-rule-mapping.yaml` | Threat rules to compliance requirements |
| `context/cwe-mappings.yaml` | CWE identifiers for each threat rule |
| `context/stride-to-attack.yaml` | STRIDE to MITRE ATT&CK tactic/technique mapping |
| `context/risk-scoring.yaml` | Likelihood x Impact scoring methodology |

## Security Overlay Files

The engine automatically merges security overlays when present:

- `system-security.yaml` — CIA triad, TLS, authentication, compliance tags
- `networks-security.yaml` — Zone segmentation, IDS/IPS, ACL rules
- `deployment-security.yaml` — Runtime security (image signing, read-only FS, etc.)

## Severity Levels

Findings are grouped by severity: `critical`, `high`, `medium`, `low`, `info`

Context-aware overrides apply automatically (e.g., health check endpoints get lower severity).

## Rule Types Evaluated

- Unauthenticated listeners
- Weak authentication (basic, password)
- Missing authorization on sensitive endpoints
- Unencrypted listeners and data flows
- Internet-exposed high-value assets
- Trust boundary violations
- Sensitive data flows across trust boundaries without encryption
- Data residency violations
- Orphaned components (no connections = unmonitored)
- Blast radius analysis (failure impact scope)
