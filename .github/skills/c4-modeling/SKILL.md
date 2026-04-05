---
name: c4-modeling
description: Guides the 6-layer C4 modeling process for system architecture — contexts, containers, components, networks, external systems, and review
allowed-tools: ['read', 'edit']
---

# C4 Architecture Modeling Skill

Guides the layer-by-layer C4 modeling process used by `@architect` to build structured YAML models from developer conversations.

## When to Use
- User asks to model a system architecture
- User says "start fresh" or "model a [system name]"
- `@architect` agent is invoked
- Extending an existing architecture model

## Layer Progression

Always proceed layer-by-layer in order (1→6). Never skip ahead.

| Layer | Name | What It Captures | Output |
|-------|------|------------------|--------|
| 1 | Contexts | High-level systems (internal/external) and context relationships | `system.yaml`: metadata, contexts, context_relationships |
| 2 | Containers | Functional tiers within each context, container relationships | `system.yaml`: containers, container_relationships |
| 3 | Components | Individual services with listeners and relationships | `system.yaml`: components, listeners, component_relationships |
| 4 | Networks | Network zones and infrastructure resources | `networks.yaml` |
| 5 | External Systems | External systems, data entities, trust boundaries | `system.yaml`: external_systems, data_entities, trust_boundaries |
| 6 | Review | Summarize, validate, offer handoffs | Summary + handoff menu |

## Key Rules

1. Show YAML after each entity is captured. Get user confirmation before proceeding.
2. Auto-generate kebab-case IDs from names.
3. Required fields are never skipped. Optional fields can be deferred with "skip" or "later".
4. Security properties (CIA triad, DFD element type) are captured at component level in Layer 3.
5. Listener targeting for container relationships is deferred until components exist in Layer 3.

## Files in This Skill
- `context-layer.md` — Layer 1: System contexts and metadata
- `container-layer.md` — Layer 2: Containers within contexts
- `component-layer.md` — Layer 3: Components, listeners, and relationships
- `network-layer.md` — Layer 4: Network zones and infrastructure
- `external-systems.md` — Layer 5: External systems, data entities, trust boundaries
- `review-layer.md` — Layer 6: Review and handoff
