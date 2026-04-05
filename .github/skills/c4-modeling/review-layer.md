<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->

# Layer 6 — Review and Handoff

## Review Checklist

Before offering handoffs, verify:

1. **Metadata complete** — name, description, owner, status all populated
2. **All contexts defined** — at least one internal context
3. **All containers placed** — every internal context has at least one container
4. **All components defined** — every container has at least one component
5. **Listeners defined** — every component has at least one listener
6. **Relationships connected** — component relationships reference valid listeners
7. **Networks defined** — at least one network zone
8. **IDs are kebab-case** — all entity IDs match `^[a-z][a-z0-9]*(-[a-z0-9]+)*$`

## Summary Display

Show a final summary:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ARCHITECTURE COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ System: <name>
✓ Contexts: X (Y internal, Z external)
✓ Containers: X
✓ Components: X with Y listeners
✓ Relationships: X component, Y container, Z context
✓ Network Zones: X
✓ External Systems: X
✓ Trust Boundaries: X
```

## Handoff Targets

After review, offer these options:
1. **@deployer** — "Place containers into network zones"
2. **@security-reviewer** — "Analyze security posture"
3. **@diagram-generator** — "Generate architecture diagrams"
4. **@validator** — "Validate YAML structure"
5. **@doc-writer** — "Generate documentation"
6. **@pattern-manager** — "Save as reusable pattern"
