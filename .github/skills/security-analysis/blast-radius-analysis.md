<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->

# Blast Radius & Lateral Movement Analysis

Analyze the impact of a compromised container by tracing relationship paths.

## Analysis Steps

### Step 1: Direct Reach (Depth 1)
Find all container and component relationships where the compromised container (or its components) is source OR target.

### Step 2: Lateral Movement Paths (Depth 2+)
From the compromised container, follow relationship edges transitively:
- **Depth 1:** Directly connected components
- **Depth 2:** One intermediate hop
- **Depth N:** Continue until no new components or depth limit (5) reached

### Step 3: Data Exposure Scope
For each reachable component, list all data entities accessible via the relationship chain and their classifications.

### Step 4: Maximum Privilege Escalation
Determine the highest trust zone reachable from the compromised container by following relationship paths through deployment placements.

### Step 5: Affected Deployments
Find all deployments where this container is placed.

## Report Format

```markdown
# Blast Radius — <container-name>

## Direct Reach (Depth 1)
| Target | Relationship | Data Classification | Trust Zone |

## Lateral Movement Paths (Depth 2+)
| Path | Max Depth | Final Target | Data Exposed | Max Trust Zone |

## Data Exposure Summary
| Data Entity | Classification | Reachable Via |

## Privilege Escalation
- Starting zone: <zone> (<trust-level>)
- Maximum reachable zone: <zone> (<trust-level>)
- Escalation: <yes/no>
```

Output: `architecture/<system-id>/diagrams/blast-radius-<container-id>.md`
