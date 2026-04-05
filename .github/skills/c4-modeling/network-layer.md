<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->

# Layer 4 — Networks

Network zones define the network topology and infrastructure resources that containers/components deploy into.

## Capture Sequence

### 1. Network Zones
For each zone, capture:
- `name`, `zone_type` (`dmz` | `private` | `public` | `management` | `data` | `restricted`)
- `internet_routable` — is this zone reachable from the internet?
- `trust` — `trusted` | `semi_trusted` | `untrusted`
- **Security properties**: `segmentation_type`, `egress_filtered`, `ids_ips_enabled`, `dlp_enabled`, `default_deny`, `allowed_ingress_zones`, `allowed_egress_zones`

### 2. Infrastructure Resources
For each zone, capture infrastructure resources (WAF, load balancers, IDS/IPS, logging):
- `name`, `resource_type`, `technology`
- **Security properties**: `version`, `high_availability`, `encryption_key_management`, `compliance_certified`

## Output
Write to `architecture/networks.yaml`:
```yaml
network_zones:
  - id: dmz
    name: DMZ
    zone_type: dmz
    internet_routable: true
    trust: semi_trusted
    infrastructure_resources:
      - id: waf-01
        name: Web Application Firewall
        resource_type: waf
        technology: AWS WAF
```

## Pattern Integration
If the user wants to use a pre-built network pattern, hand off to `@pattern-manager` to load it instead of building from scratch.
