<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->

# networks.yaml Rules

Schema source of truth: `schemas/networks.schema.json`

## Required Structure
- `network_zones` — array of zone definitions

## Zone Fields
- `id`: kebab-case zone identifier
- `name`: Human-readable zone name
- `zone_type`: `dmz` | `private` | `public` | `management` | `data` | `restricted`
- `trust`: `trusted` | `semi_trusted` | `untrusted`
- `internet_routable`: boolean — is this zone reachable from the internet?

## Infrastructure Resources
Zones may include `infrastructure_resources` for WAF, load balancers, IDS/IPS, logging:
- Each resource has `id`, `name`, `resource_type`, `technology`
- Resources are zone-scoped — they belong to one zone

## Cross-Zone Rules
- DMZ zones should have `internet_routable: true`, `trust: semi_trusted` or `untrusted`
- Data zones should have `internet_routable: false`, `trust: trusted`
- Management zones should not be directly accessible from DMZ
- Network patterns define topology; security posture goes in `networks-security.yaml`
