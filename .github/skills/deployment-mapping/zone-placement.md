<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->

# Zone Placement

## Placement Process

1. Read `system.yaml` for containers and components
2. Read `networks.yaml` for available zones
3. For each container, ask which zone it belongs in
4. Components inherit their container's zone unless explicitly overridden
5. Write placement to `deployment.yaml`

## Multi-Network Awareness

Deployments may use multiple network patterns:
- Group zones by source pattern and purpose when presenting options
- Highlight zones from product patterns (unified) vs. network patterns
- Show cross-network links between zones from different patterns
- Indicate which network each zone belongs to

## Placement Warnings

Flag these automatically:
- Internet-facing component without authentication
- Database component in DMZ zone
- Component with `confidential` data in `untrusted` zone
- Missing TLS on zone boundary crossing
- Component placed in a zone with no infrastructure resources (no WAF, no logging)

## Output Format

```yaml
deployment:
  metadata:
    deployment_id: prod-us-east
    name: Production US East
    environment: production
    status: active
  zone_placements:
    - zone_id: dmz
      containers:
        - container_id: api-tier
          components:
            - component_id: api-gateway
```
