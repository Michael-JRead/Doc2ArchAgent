<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->

# Mermaid Diagram Rules

## File Format
- Output: `*.md` files with fenced Mermaid code blocks
- One diagram per file
- File naming: `<system-id>-<level>.md` (e.g., `payment-platform-context.md`)

## Syntax Rules
- Use `flowchart LR` for context and container diagrams
- Use `flowchart TB` for component diagrams
- Node IDs must be valid Mermaid identifiers (no spaces, no special characters)
- Convert kebab-case IDs to camelCase or underscored for Mermaid compatibility

## Styling
- Use `classDef` for C4 color scheme (person, system, container, component, external, infra)
- Apply classes with `:::className` syntax
- Always include a legend subgraph

## Boundaries
- Use `subgraph` for context and zone boundaries
- Label subgraphs with the entity name
- End every subgraph with `end`

## Known Limitations
- Mermaid does not support nested subgraphs well in all renderers
- Avoid more than 3 levels of nesting
- Test rendered output in GitHub and VS Code preview
