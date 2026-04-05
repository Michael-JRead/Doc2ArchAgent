<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->

# Derived Links

After zone placement, automatically compute:

## Zone Crossing Links
For each component relationship:
1. Resolve source component → source zone (from placement)
2. Resolve target component → target zone (from placement)
3. If source zone != target zone → zone crossing link
4. Include: protocol, port, TLS status, auth mechanism from the target listener

## Trust Level Transitions
For each zone crossing:
- Compare `trust` levels of source and target zones
- Flag transitions from higher trust to lower trust
- Flag transitions from lower trust to higher trust (potential privilege escalation)

## Internet Boundary Crossings
Identify relationships where one side is `internet_routable: true` and the other isn't.

## Derived Link Report

Present to user as confirmation before writing:
```
DERIVED LINKS — prod-us-east
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Zone Crossings: 3 | Internal: 5 | Internet Boundary: 1

| Source → Target | Source Zone → Target Zone | Trust | Protocol | Port |
|---|---|---|---|---|
| api-gw → auth-svc | dmz → app-tier | semi→trusted | HTTPS | 443 |
```

These links are informational — they help security review and diagram generation but don't modify the source architecture data.
