<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->

# HLDD Template — 12 Sections

## Section Structure

1. **Document Control** — Version, date, author, reviewers, approval status
2. **Executive Summary** — Non-technical overview, key design decisions, scope
3. **System Overview** — Purpose, contexts, key stakeholders, compliance requirements
4. **Architecture Contexts** — C4 Level 1: systems and their relationships
5. **Container Architecture** — C4 Level 2: functional tiers, technology choices
6. **Component Architecture** — C4 Level 3: services, listeners, protocols
7. **Network Architecture** — Zones, trust levels, infrastructure resources
8. **Deployment Architecture** — Zone placements, derived links, environment details
9. **Security Architecture** — STRIDE analysis summary, trust boundaries, compliance mapping
10. **Data Architecture** — Data entities, classifications, flow annotations
11. **Integration Points** — External systems, API contracts, SLA requirements
12. **Appendices** — Diagram index, glossary, references

## Content Rules

- Every section references specific YAML entities by ID
- Include inline diagrams where available (link to generated Mermaid/PlantUML)
- Confidence annotations: flag LOW/UNCERTAIN fields with `[verify]` tags
- Never fabricate content — if a section has no data, say "Not yet modeled"

## Output Locations
- Markdown: `architecture/<system-id>/docs/<system-id>-hldd.md`
- Confluence: `architecture/<system-id>/docs/<system-id>-hldd.confluence.html`
