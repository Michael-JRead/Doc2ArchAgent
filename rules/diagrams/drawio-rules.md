<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->

# Draw.io Diagram Rules

## File Format
- Output: `*.drawio` files (XML format)
- One diagram per file
- File naming: `<system-id>-<level>.drawio`

## XML Structure
- Root element: `<mxfile>`
- Single `<diagram>` per file
- `<mxGraphModel>` with `<root>` containing `<mxCell>` elements
- Cell ID 0 = root, Cell ID 1 = default parent layer

## Coordinate System
- All nodes require explicit `x`, `y`, `width`, `height` in `<mxGeometry>`
- Use grid-based positioning from layout-plan.yaml
- Grid cell size: 200px width, 120px height, 40px gap
- Title cell at y=0, legend at bottom

## Styling
- Use `style` attribute with semicolon-separated key=value pairs
- C4 color scheme applied via `fillColor` and `fontColor`
- Boundaries: `dashed=1`, `rounded=1`
- Edges: `edgeStyle=orthogonalEdgeStyle`

## Lucidchart Compatibility
- Use standard shape types for import compatibility
- Avoid custom shapes that don't translate
- Test import in both Draw.io and Lucidchart
