<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->

# Trust Boundary Analysis

Detect and evaluate zone crossings and trust level transitions in the architecture.

## Network Crossing Detection

For a given deployment:
1. Derive all component-to-component relationships
2. Resolve source and target zones from placements
3. Classify each relationship:
   - **Zone crossing** — source zone != target zone
   - **Internal** — source zone == target zone
   - **Internet boundary crossing** — one zone has `internet_routable: true`, the other doesn't
   - **Trust boundary crossing** — zones have different `trust` levels

## Report Format

### Zone Crossings
| Source | Source Zone | Target | Target Zone | Protocol | Port | TLS | Auth |

### Internal (same zone)
| Source | Zone | Target | Protocol | Port | TLS | Auth |

### Summary
- Total relationships: X
- Zone crossings: X
- Internal: X
- Internet boundary crossings: X
- Trust boundary crossings: X

Output: `architecture/<system-id>/diagrams/<deployment-id>-network-crossings.md`

## False Positive Reduction

### Trust Boundary Gate
Only escalate to HIGH if the flow crosses a trust boundary. Same-zone, same-trust findings cap at MEDIUM.

### Data Classification Gate
Flows involving only "public" data cap at INFO.

### Component Type Exceptions
- Health check endpoints with `authn_mechanism: none` → INFO
- Metrics endpoints with `authn_mechanism: none` → INFO
- K8s readiness/liveness probes → expected unauthenticated

### Defense-in-Depth Credit
If mitigated by another control (WAF with TLS termination, NetworkPolicy isolation), note the compensating control and cap at MEDIUM.
