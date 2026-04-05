<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->

# deployment.yaml Rules

Schema source of truth: `schemas/deployment.schema.json`

## Required Structure
- `deployment.metadata` — deployment_id, name, environment, status
- `deployment.zone_placements` — array mapping containers/components to zones

## Zone Placement Rules
- Every container must be placed in exactly one zone
- Components inherit their container's zone placement unless explicitly overridden
- All referenced `zone_id` values must exist in the deployment's `networks.yaml`
- All referenced `container_id` and `component_id` values must exist in `system.yaml`

## Status Values
`proposed` | `approved` | `active` | `deprecated` | `example`

## Derived Links
After placement, the deployer agent computes derived links:
- Which container-to-container relationships cross zone boundaries
- Which relationships require trust boundary crossings
- These are informational — they help security review but don't modify source data

## Multi-Network Deployments
- A manifest may reference multiple network patterns
- Each network has a unique `id_prefix` to namespace zone IDs
- Cross-network links connect zones from different network patterns
- Group zones by source pattern when presenting placement options
