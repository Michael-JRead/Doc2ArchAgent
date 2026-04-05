<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->

# Naming Conventions

## Entity IDs
- **Pattern**: `^[a-z][a-z0-9]*(-[a-z0-9]+)*$` (kebab-case)
- **Auto-generate** from entity names: "Payment Gateway" → `payment-gateway`
- **Examples**: `payment-gateway`, `prod-us-east`, `private-app-tier`, `api-gateway`

## File Names
- Lowercase with hyphens: `payment-platform.yaml`, `prod-us-east.yaml`
- Agent files: `<name>.agent.md`
- Schema files: `<name>.schema.json`
- Pattern directories: `<pattern-id>/`
- Deployment directories: `<deployment-id>/`

## Directory Structure
- System architectures: `architecture/<system-id>/`
- Patterns by type: `patterns/networks/<region>/<pattern-id>/`, `patterns/products/<category>/<pattern-id>/`
- Deployments: `deployments/<deployment-id>/`

## References
- Cross-entity references use the target entity's `id` field
- `context_id`, `container_id`, `component_id` — always kebab-case, must resolve to existing entities
- `target_listener_ref` — references a listener `id` within the target component
