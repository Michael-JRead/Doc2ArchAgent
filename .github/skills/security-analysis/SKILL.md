---
name: security-analysis
description: STRIDE threat analysis, firewall ACL generation, blast radius analysis, and trust boundary evaluation for architecture models
allowed-tools: ['read', 'execute']
---

# Security Analysis Skill

Comprehensive security analysis methodology for architecture YAML models. Used by `@security-reviewer` and referenced by `@orchestrator` for pipeline coordination.

## When to Use
- Running security review on an architecture
- Generating STRIDE threat analysis
- Computing firewall ACL rules
- Analyzing blast radius for a compromised container
- Evaluating trust boundary crossings

## Analysis Pipeline

1. **Deterministic baseline** — Run `python tools/threat-rules.py` for codified, reproducible findings
2. **LLM enrichment** — Add findings for threats codified rules cannot detect (business logic flaws, implicit trust assumptions)
3. **False positive reduction** — Apply gates (trust boundary, data classification, component type, defense-in-depth)
4. **Report generation** — Write findings, STRIDE analysis, firewall ACLs

## Files in This Skill
- `stride-methodology.md` — Per-relationship STRIDE evaluation with DFD mapping
- `firewall-acl-generation.md` — ACL rule generation from listeners and deployment placements
- `blast-radius-analysis.md` — Container compromise impact and lateral movement
- `trust-boundary-analysis.md` — Zone crossing detection and trust level evaluation

## Enrichment Context Files
- `context/stride-to-attack.yaml` — STRIDE → CAPEC → ATT&CK mapping
- `context/cwe-mappings.yaml` — CWE identifiers by finding category
- `context/compliance-mappings.yaml` — Compliance framework control mapping
- `context/risk-scoring.yaml` — Likelihood × Impact quantification
