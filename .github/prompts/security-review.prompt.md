---
description: Run a comprehensive security review of the architecture
---

Perform a comprehensive security review:

1. **Deterministic analysis first**: Run `python tools/threat-rules.py` on the system.yaml with `--networks` and `--deployment` flags. This provides the baseline of codified findings.

2. **STRIDE analysis**: For each trust boundary crossing in the architecture, evaluate all 6 STRIDE categories using `context/stride-to-attack.yaml` for ATT&CK technique enrichment.

3. **Compliance check**: Cross-reference findings against `context/compliance-mappings.yaml` for PCI-DSS, SOC2, GDPR, and HIPAA control gaps.

4. **Blast radius**: For each HIGH or CRITICAL finding, trace the blast radius up to depth 3 — what other components are reachable from the affected entity?

5. **Risk scoring**: Apply the methodology from `context/risk-scoring.yaml` to assign likelihood × impact scores.

6. **Output**: Write findings to `architecture/<system-id>/docs/security-findings.md` with CWE references, ATT&CK technique IDs, and recommended remediations.

Check `accepted_risks` in system.yaml before reporting — do not re-report accepted, non-expired risks.
