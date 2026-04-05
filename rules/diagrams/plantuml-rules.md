<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->

# PlantUML Diagram Rules

## File Format
- Output: `*.puml` files
- One diagram per file
- File naming: `<system-id>-<level>.puml`

## C4 Stdlib
- Always include: `!include <C4_Context>`, `!include <C4_Container>`, `!include <C4_Component>`, `!include <C4_Deployment>`
- Use the correct macro for each element type (see diagram-plantuml.agent.md for exact signatures)

## Alias Rules
- Convert kebab-case IDs to valid PlantUML aliases
- Pattern: replace `-` with `_`, ensure starts with a letter
- Example: `payment-gateway` → `payment_gateway`

## Syntax Constraints
- `Boundary()` and `System_Boundary()` MUST use `{` `}` block syntax
- Never nest `Boundary` inside `Rel()` arguments
- `Lay_D()`, `Lay_R()` helpers for layout control — use sparingly
- Escape special characters in labels with Creole syntax

## Security Overlays
- Use hex color codes from C4 color scheme
- Confidence coloring: GREEN (#28a745) for HIGH, YELLOW (#ffc107) for MEDIUM, RED (#dc3545) for LOW
- Trust boundaries shown as dashed boundary lines
