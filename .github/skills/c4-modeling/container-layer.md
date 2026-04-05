<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->

# Layer 2 — Containers

Containers are logical groupings of related components within an internal context. They represent functional tiers or architectural boundaries — not individual services.

## Examples
- "Control Plane" (control_plane)
- "Data Plane" (data_plane)
- "Proxy Tier" (custom)
- "Ingestion Pipeline" (data_plane)

## Capture Sequence

For each internal context:

### 1. Define Containers
For each container, capture:
- `name`, `description`
- `container_type` — functional tier classification
- `technology` — primary technology (e.g., Spring Boot, Express.js)
- `status` — default: `active`
- `external` — default: `false`

Containers do NOT define listeners directly — listeners are defined at component level (Layer 3) and aggregated up.

### 2. Container Relationships
For each relationship between containers:
- Select source container
- Select target container
- `label` — describes the interaction
- `synchronous` — sync vs async
- `data_entities` — what data flows
- `data_classification` — `public` | `internal` | `confidential` | `restricted`
- `trust_boundary_crossing` — does this cross a trust boundary?

Note: `target_listener_ref` is deferred until components exist in Layer 3.

Capture all containers and relationships for a context before moving to the next context.

## Output
Append to `architecture/<system-id>/system.yaml`:
```yaml
containers:
  - id: api-tier
    name: API Tier
    context_id: payment-platform
    container_type: gateway
    technology: Kong Gateway
    status: active
container_relationships:
  - id: cr-api-to-app
    source_container: api-tier
    target_container: app-core
    label: routes requests to
    synchronous: true
```
