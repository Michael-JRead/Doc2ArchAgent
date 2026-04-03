---
name: diagram-workflow
description: End-to-end diagram generation workflow from architecture YAML to rendered output in all supported formats
allowed-tools: ['read']
---

# Diagram Generation Workflow Skill

Documents the three-phase diagram generation pipeline used by `@diagram-generator` and its 5 renderer sub-agents.

## Three-Phase Pipeline

### Phase 1: Read Architecture YAML

Read the source YAML files to understand what to diagram:

- `system.yaml` — Contexts, containers, components, relationships
- `networks.yaml` — Network zones, infrastructure resources
- `deployment.yaml` — Zone placements
- Security overlays: `system-security.yaml`, `networks-security.yaml`, `deployment-security.yaml`

### Phase 2: Build Layout Plan

Generate `layout-plan.yaml` — the intermediate representation that all renderers consume.

The authoritative schema is defined in `diagram-generator.agent.md`. Key structure:

```yaml
system_id: payment-platform
system_name: Payment Processing Platform
generated: "2026-04-03T12:00:00Z"
complexity: simple | medium | complex

colors:
  person: "#08427b"
  system: "#1168BD"
  container: "#438DD5"
  component: "#85BBF0"
  external: "#999999"
  infra: "#ff8f00"

diagrams:
  - level: context | container | component | deployment
    title: "Payment Platform — Container Diagram"
    nodes:
      - id: payment-gateway          # kebab-case
        type: container              # person | system | system_ext | container | container_ext | container_db | container_queue | component | infra | deployment_node
        label: "Payment Gateway"     # max 30 chars
        technology: "Java 17"
        description: "Handles payments"  # max 60 chars
        boundary_id: payment-platform    # parent boundary, if inside one
        grid_col: 2                  # 0-based, left-to-right
        grid_row: 0                  # 0-based, top-to-bottom
        confidence: high             # only if provenance.yaml exists
    boundaries:
      - id: payment-platform
        label: "Payment Platform"
        type: system                 # enterprise | system | container | zone
        trust: trusted               # only for zone type
        contains: [payment-gateway, app-core, data-tier]
    edges:
      - id: gw-to-app
        source: payment-gateway      # node id (kebab-case)
        target: app-core
        label: "Routes requests"     # max 25 chars
        protocol: "HTTPS"            # max 40 chars, empty at context level
        sync: true
        data_classification: confidential
        warnings: []                 # zone_crossing, trust_boundary, no_tls, no_authn
    legend:
      elements:
        - color: "#438DD5"
          label: "Container"
      flows:
        - style: solid
          label: "Synchronous request"
```

### Phase 3: Dispatch to Renderers

`@diagram-generator` dispatches the layout plan to one or more renderer agents:

| Renderer | Output | File Extension |
|----------|--------|---------------|
| `@diagram-mermaid` | Mermaid flowchart/subgraph | `.md` |
| `@diagram-plantuml` | PlantUML C4 diagrams | `.puml` |
| `@diagram-drawio` | Draw.io XML (Lucidchart import) | `.drawio` |
| `@diagram-structurizr` | Structurizr DSL | `.dsl` |
| `@diagram-d2` | D2 language diagrams | `.d2` |

## Diagram Types

| Type | C4 Level | Shows |
|------|----------|-------|
| `context` | L1 | System contexts and external systems |
| `container` | L2 | Containers within a context |
| `component` | L3 | Components within a container |
| `deployment` | L4 | Containers placed in network zones |

## Output Locations

### For architecture systems
```
architecture/<system-id>/diagrams/
  _index.yaml          # Diagram catalog
  layout-plan.yaml     # Intermediate layout plan
  <diagram-type>.md    # Mermaid
  <diagram-type>.puml  # PlantUML
  <diagram-type>.drawio # Draw.io
  <diagram-type>.dsl   # Structurizr
  <diagram-type>.d2    # D2
```

### For deployment compositions
```
deployments/<deployment-id>/diagrams/
  _index.yaml
  layout-plan.yaml
  custom/              # Hand-crafted diagrams (never overwritten)
```

### For patterns
```
patterns/<type>/<region-or-category>/<pattern-id>/contexts/diagrams/
  _index.yaml
  layout-plan.yaml
```

## Diagram Index

Every diagram directory must have `_index.yaml` conforming to `schemas/diagram-index.schema.json`:

```yaml
diagrams:
  - id: container-diagram
    title: "Payment Platform - Container View"
    type: container
    formats:
      - format: mermaid
        path: container.md
      - format: plantuml
        path: container.puml
```

## Security Overlay Visualization

When security overlays are present, diagrams should include:

- **Trust boundaries** — Visual borders around zones with trust levels
- **Encrypted connections** — Lock icons or TLS labels on edges
- **Confidence indicators** — Color-coding by confidence level (green=HIGH, yellow=MEDIUM, red=LOW)
- **Authentication markers** — Auth method labels on listener nodes
