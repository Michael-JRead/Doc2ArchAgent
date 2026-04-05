<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->

# Firewall ACL Generation

Generate firewall rules from component relationships and deployment placements.

## Rule Generation Logic

For data flows where protocol and port are explicitly stated in component listeners:

```
component_relationship: api-gateway → auth-service
target_listener: HTTPS :443 / TLS 1.3 / oauth2
source_zone: dmz (from deployment placement)
dest_zone: private-app-tier (from deployment placement)

Generated ACL:
  PERMIT TCP FROM dmz/api-gateway TO private-app-tier/auth-service PORT 443
```

For data flows where protocol/port are NOT stated:
```
  NEEDS_SPECIFICATION — protocol and port required for ACL generation
```

**NEVER guess a port or protocol.**

## Report Format

```
FIREWALL ACL RULES — <System Name> / <Deployment Name>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

| # | Action | Proto | Source Zone / Component | Dest Zone / Component | Port | Notes |
|---|--------|-------|------------------------|----------------------|------|-------|
| 1 | PERMIT | TCP   | dmz / api-gateway      | app-tier / auth-svc  | 443  | TLS 1.3, OAuth2 |
| 2 | NEEDS_SPEC | ? | app-tier / order-svc   | data-tier / cache    | ?    | Protocol not specified |

Summary:
  Total rules: X | Fully specified: X | Needs specification: X
```

Output: `architecture/<system-id>/diagrams/firewall-acls.md`
