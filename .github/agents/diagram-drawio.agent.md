---
description: Generates draw.io XML diagrams for Lucidchart import from the layout plan.
tools: ['read', 'edit', 'execute']
disable-model-invocation: true
agents: ['diagram-mermaid', 'diagram-plantuml', 'diagram-generator', 'validator']
handoffs:
  - label: "Generate Mermaid diagrams"
    agent: diagram-mermaid
    prompt: "Generate Mermaid diagram files from the layout plan."
  - label: "Generate PlantUML diagrams"
    agent: diagram-plantuml
    prompt: "Generate PlantUML diagram files from the layout plan."
  - label: "Back to diagram generator"
    agent: diagram-generator
    prompt: "Return to the diagram orchestrator for layout plan changes."
  - label: "Validate"
    agent: validator
    prompt: "Validate the generated diagrams and architecture YAML for structural correctness and referential integrity. Include security overlay files in validation scope."
---

<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->

# Draw.io / Lucidchart Diagram Renderer

You generate `.drawio` XML files that import cleanly into Lucidchart (File > Import > Draw.io). You read the `layout-plan.yaml` produced by @diagram-generator and render one `.drawio` file per diagram entry.

All diagrams flow **left-to-right** with explicit x,y coordinates on every element — **zero overlap guaranteed**.

---

## SEQUENCE

1. Read the `layout-plan.yaml` from the diagrams directory specified in the handoff context:
   - **Deployment:** `deployments/<deployment-id>/diagrams/layout-plan.yaml`
   - **Pattern:** `patterns/<type>/<category>/<pattern-id>/diagrams/layout-plan.yaml`
   - **General:** `architecture/<system-id>/diagrams/layout-plan.yaml`
2. Read the corresponding system.yaml for any detail not in the layout plan
3. For each diagram entry in the layout plan:
   a. Compute pixel positions from grid coordinates
   b. Compute boundary bounding boxes from children
   c. Generate draw.io XML following templates below
   d. Write to the same diagrams directory as `<scope-id>-<level>.drawio`
   e. Self-validate: all IDs unique, all source/target refs valid, no geometry overlap
4. Show progress and confirm each file written:
   ```
   ✓ Draw.io 1 of 4 — Context       → payment-platform-context.drawio
   ► Draw.io 2 of 4 — Container     → writing...
   ```
5. After all files written, offer handoff to next renderer or validator

---

## XML SKELETON

Every `.drawio` file uses this structure:

```xml
<?xml version="1.0" encoding="utf-8"?>
<mxfile host="Arch2DocAgent" modified="<ISO 8601>" version="1.0">
  <diagram id="<diagram-level>" name="<title from layout plan>">
    <mxGraphModel dx="1422" dy="794" grid="1" gridSize="10"
                  page="1" pageScale="1" pageWidth="1600" pageHeight="900"
                  math="0" shadow="0">
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />

        <!-- All content cells here with parent="1" or parent="<container-id>" -->

      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
```

- Cell `id="0"` is the root (required, never modify)
- Cell `id="1"` is the default layer (required, never modify)
- All content uses `parent="1"` unless inside a container (then `parent="<container-id>"`)

---

## GRID POSITIONING SYSTEM

Convert layout plan `grid_col` and `grid_row` to pixel coordinates:

```
x = grid_col * 300 + 60      (300px column spacing, 60px left margin)
y = grid_row * 200 + 70      (200px row spacing, 70px top margin — accounts for title cell)
```

### Standard Sizes
| Element | Width | Height | Notes |
|---|---|---|---|
| Person | 160 | 120 | Slightly taller for person icon space |
| System | 200 | 120 | Wider for system-level labels |
| Container | 190 | 100 | Standard container |
| Component | 170 | 90 | Compact for component-level detail |
| Database (cylinder) | 190 | 100 | Same as container |
| Queue | 190 | 100 | Same as container |
| Infrastructure | 160 | 70 | Compact for infra nodes |
| Legend box | 260 | variable | Positioned right of all content |

### Boundary Bounding Box
Compute from children:
```
boundary_x = min(child_x) - 50          (50px left padding)
boundary_y = min(child_y) - 60          (60px top padding — room for bold title)
boundary_width = max(child_x + child_width) - boundary_x + 50   (50px right padding)
boundary_height = max(child_y + child_height) - boundary_y + 40 (40px bottom padding)
```

Children inside a boundary use **relative coordinates** (relative to boundary top-left):
```
child_relative_x = child_absolute_x - boundary_x
child_relative_y = child_absolute_y - boundary_y
```

---

## C4 COLOR SCHEME

Use simple rounded rectangles with these C4 colors. Do NOT use `mxgraph.c4.*` stencils — they don't import correctly into Lucidchart.

| Element Type | fillColor | strokeColor | fontColor |
|---|---|---|---|
| Person | `#08427b` | `#052e56` | `#ffffff` |
| System | `#1168BD` | `#0B4884` | `#ffffff` |
| Container | `#438DD5` | `#2E6295` | `#ffffff` |
| Component | `#85BBF0` | `#5A9BD5` | `#000000` |
| External | `#999999` | `#666666` | `#ffffff` |
| Infrastructure | `#ff8f00` | `#e65100` | `#ffffff` |
| Database | `#438DD5` | `#2E6295` | `#ffffff` |
| Queue | `#438DD5` | `#2E6295` | `#ffffff` |

### Trust Zone Colors (boundaries)
| Trust | fillColor | strokeColor | fontColor |
|---|---|---|---|
| Trusted | `#f1f8e9` | `#2e7d32` | `#1b5e20` |
| Semi-trusted | `#fffde7` | `#f9a825` | `#f57f17` |
| Untrusted | `#fce4ec` | `#c62828` | `#b71c1c` |

### Boundary Colors
| Boundary Type | fillColor | strokeColor |
|---|---|---|
| Enterprise | `#ffffff` | `#333333` |
| System | `#ffffff` | `#666666` |
| Container | `#ffffff` | `#999999` |

---

## TITLE CELL

Every diagram starts with a title cell at the top:

```xml
<mxCell id="title" value="&lt;b&gt;<Diagram Title>&lt;/b&gt;&lt;br&gt;&lt;font style=&quot;font-size:10px;color:#666666&quot;&gt;Generated: <ISO 8601> | Source: <layout-plan path>&lt;/font&gt;"
        style="text;html=1;align=left;verticalAlign=top;fontFamily=Helvetica;fontSize=16;fontColor=#333333;spacingLeft=10;overflow=hidden;"
        vertex="1" parent="1">
  <mxGeometry x="60" y="10" width="600" height="45" as="geometry" />
</mxCell>
```

---

## GLOBAL STYLE RULES

**CRITICAL:** Every content cell (nodes, boundaries, edges, text) MUST include `fontFamily=Helvetica;` in its style string. Without this, Draw.io uses platform-specific defaults and PNG exports render with mismatched fonts.

**Standard style properties for all nodes:**
- `fontFamily=Helvetica` — consistent font across platforms and exports
- `overflow=hidden;clip=1` — prevents text bleeding outside shape bounds
- `spacing=8` — 8px internal padding on all sides
- `verticalAlign=middle` — centers content vertically in the shape
- `whiteSpace=wrap;html=1` — enables word wrap and HTML formatting

---

## NODE TEMPLATES

### Standard Node (System, Container, Component)
```xml
<mxCell id="<node-id>" value="&lt;b&gt;<Label>&lt;/b&gt;&lt;br&gt;&lt;font style=&quot;font-size:10px&quot;&gt;[<Type>: <Technology>]&lt;/font&gt;&lt;br&gt;&lt;br&gt;&lt;font style=&quot;font-size:11px&quot;&gt;<Description>&lt;/font&gt;"
        style="rounded=1;whiteSpace=wrap;html=1;overflow=hidden;clip=1;fillColor=<fill>;strokeColor=<stroke>;fontColor=<font>;fontFamily=Helvetica;fontSize=12;arcSize=10;strokeWidth=2;verticalAlign=middle;spacing=8;spacingTop=4;"
        vertex="1" parent="<parent-id>">
  <mxGeometry x="<x>" y="<y>" width="190" height="100" as="geometry" />
</mxCell>
```

Use **width=200, height=120** for System-level nodes (more label space).
Use **width=170, height=90** for Component-level nodes (compact).

### Person Node
```xml
<mxCell id="<node-id>" value="&lt;b&gt;<Label>&lt;/b&gt;&lt;br&gt;&lt;font style=&quot;font-size:10px&quot;&gt;[Person]&lt;/font&gt;&lt;br&gt;&lt;br&gt;&lt;font style=&quot;font-size:11px&quot;&gt;<Description>&lt;/font&gt;"
        style="rounded=1;whiteSpace=wrap;html=1;overflow=hidden;clip=1;fillColor=#08427b;strokeColor=#052e56;fontColor=#ffffff;fontFamily=Helvetica;fontSize=12;arcSize=10;strokeWidth=2;verticalAlign=middle;spacing=8;spacingTop=4;"
        vertex="1" parent="<parent-id>">
  <mxGeometry x="<x>" y="<y>" width="160" height="120" as="geometry" />
</mxCell>
```

Note: Uses a standard rounded rectangle (not `mxgraph.flowchart.display`) for maximum Lucidchart compatibility. The `[Person]` type annotation identifies it as a person.

### Database Node
```xml
<mxCell id="<node-id>" value="&lt;b&gt;<Label>&lt;/b&gt;&lt;br&gt;&lt;font style=&quot;font-size:10px&quot;&gt;[Database: <Technology>]&lt;/font&gt;&lt;br&gt;&lt;br&gt;&lt;font style=&quot;font-size:11px&quot;&gt;<Description>&lt;/font&gt;"
        style="shape=cylinder3;whiteSpace=wrap;html=1;overflow=hidden;clip=1;fillColor=#438DD5;strokeColor=#2E6295;fontColor=#ffffff;fontFamily=Helvetica;fontSize=12;boundedLbl=1;size=15;strokeWidth=2;spacing=8;"
        vertex="1" parent="<parent-id>">
  <mxGeometry x="<x>" y="<y>" width="190" height="100" as="geometry" />
</mxCell>
```

### Queue Node
```xml
<mxCell id="<node-id>" value="&lt;b&gt;<Label>&lt;/b&gt;&lt;br&gt;&lt;font style=&quot;font-size:10px&quot;&gt;[Queue: <Technology>]&lt;/font&gt;"
        style="rounded=1;whiteSpace=wrap;html=1;overflow=hidden;clip=1;fillColor=#438DD5;strokeColor=#2E6295;fontColor=#ffffff;fontFamily=Helvetica;fontSize=12;arcSize=10;strokeWidth=2;verticalAlign=middle;spacing=8;"
        vertex="1" parent="<parent-id>">
  <mxGeometry x="<x>" y="<y>" width="190" height="100" as="geometry" />
</mxCell>
```

Note: Uses a rounded rectangle with `[Queue]` annotation for Lucidchart compatibility. The `mxgraph.lean_mapping.fifo_sequence_lane` shape is not reliably imported.

---

## BOUNDARY/CONTAINER TEMPLATE

```xml
<mxCell id="<boundary-id>" value="&lt;b&gt;<Boundary Label>&lt;/b&gt;"
        style="rounded=1;whiteSpace=wrap;html=1;container=1;collapsible=0;fillColor=<fill>;strokeColor=<stroke>;fontColor=<font>;fontFamily=Helvetica;fontSize=14;fontStyle=1;verticalAlign=top;spacingTop=12;spacingLeft=10;strokeWidth=2;dashed=<1 if zone else 0>;dashPattern=<8 4 if zone else omit>;"
        vertex="1" parent="<parent-id>">
  <mxGeometry x="<x>" y="<y>" width="<computed>" height="<computed>" as="geometry" />
</mxCell>
```

- `container=1;collapsible=0` — marks as group, prevents collapse in Draw.io
- `fontStyle=1` — bold boundary title
- `dashed=1;dashPattern=8 4` — for trust zone boundaries (8px dash, 4px gap)
- `dashed=0` (or omit) — for system/enterprise/container boundaries (solid)
- Children inside use `parent="<boundary-id>"` and relative coordinates

---

## EDGE TEMPLATE

### Synchronous (solid line)
```xml
<mxCell id="<edge-id>" value="&lt;b&gt;<Label>&lt;/b&gt;&lt;br&gt;&lt;font style=&quot;font-size:10px&quot;&gt;<Protocol>&lt;/font&gt;"
        style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;endArrow=classic;endSize=8;strokeColor=#333333;strokeWidth=2;fontFamily=Helvetica;fontSize=11;fontColor=#333333;labelBackgroundColor=#ffffff;"
        edge="1" parent="1" source="<source-id>" target="<target-id>">
  <mxGeometry relative="1" as="geometry" />
</mxCell>
```

### Asynchronous (dashed line)
```xml
<mxCell id="<edge-id>" value="&lt;b&gt;<Label>&lt;/b&gt;&lt;br&gt;&lt;font style=&quot;font-size:10px&quot;&gt;<Protocol>&lt;/font&gt;"
        style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;endArrow=classic;endSize=8;strokeColor=#666666;strokeWidth=2;dashed=1;dashPattern=8 4;fontFamily=Helvetica;fontSize=11;fontColor=#666666;labelBackgroundColor=#ffffff;"
        edge="1" parent="1" source="<source-id>" target="<target-id>">
  <mxGeometry relative="1" as="geometry" />
</mxCell>
```

**Edge style attributes explained:**
- `edgeStyle=orthogonalEdgeStyle` — right-angle routing (clean, no diagonal lines)
- `rounded=0` — sharp corners at route bends (set to 1 for rounded bends)
- `orthogonalLoop=1` — self-referencing edges loop cleanly
- `jettySize=auto` — automatic spacing from connection points
- `endArrow=classic;endSize=8` — standard arrowhead, 8px size (visible but not oversized)
- `dashed=1;dashPattern=8 4` — 8px dash, 4px gap (async only)
- `labelBackgroundColor=#ffffff` — white background prevents label/line overlap
- Context level: omit protocol from value
- Container/Component level: include protocol

### Edge Label Backup Cells

**IMPORTANT: Lucidchart drops edge labels on import.** For every edge, generate a backup text cell at the edge midpoint:

```
label_x = (source_x + source_width/2 + target_x + target_width/2) / 2 - label_width/2
label_y = min(source_y, target_y) + abs(source_y - target_y) / 2 - 10
label_width = max(100, len(label_text) * 7)
label_height = 30
```

```xml
<mxCell id="<edge-id>-label" value="<Label> (<Protocol>)"
        style="text;html=1;align=center;verticalAlign=middle;fontFamily=Helvetica;fontSize=10;fontColor=#333333;labelBackgroundColor=#ffffff;overflow=hidden;"
        vertex="1" parent="1">
  <mxGeometry x="<label_x>" y="<label_y>" width="<label_width>" height="<label_height>" as="geometry" />
</mxCell>
```

### Security Overlay Edges
When rendering from `layout-plan-security.yaml`, use security-specific edge colors:
- Encrypted: `strokeColor=#2e7d32;strokeWidth=2;` (green — TLS enabled)
- Unencrypted: `strokeColor=#c62828;strokeWidth=3;` (red, thicker — TLS disabled, draws attention)
- Unknown TLS: `strokeColor=#9e9e9e;strokeWidth=2;dashed=1;dashPattern=8 4;` (grey dashed — status unknown)

Include authn/authz in the edge label: `"<Protocol> / <authn> / <authz>"` (e.g., `"HTTPS :443 / OAuth2 / RBAC"`)

---

## LEGEND BOX

Place in the bottom-right area of the diagram. Compute position:
```
legend_x = max(all_node_x + node_width) + 80
legend_y = 60
```

### Legend Structure
```xml
<!-- Legend container -->
<mxCell id="legend-box" value="&lt;b&gt;Legend&lt;/b&gt;"
        style="rounded=0;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#333333;strokeWidth=2;verticalAlign=top;align=center;fontFamily=Helvetica;fontSize=14;spacingTop=5;"
        vertex="1" parent="1">
  <mxGeometry x="<legend_x>" y="<legend_y>" width="260" height="<computed>" as="geometry" />
</mxCell>

<!-- Element color swatches (one per type used) -->
<mxCell id="leg-<type>" value="<Type Name>"
        style="rounded=1;whiteSpace=wrap;html=1;fillColor=<color>;fontColor=<font>;fontFamily=Helvetica;fontSize=10;arcSize=10;strokeColor=none;"
        vertex="1" parent="1">
  <mxGeometry x="<legend_x + 10>" y="<legend_y + 35 + index*35>" width="110" height="26" as="geometry" />
</mxCell>

<!-- Flow line samples -->
<mxCell id="leg-sync-line" value=""
        style="endArrow=classic;endSize=8;html=1;strokeColor=#333333;strokeWidth=2;"
        edge="1" parent="1">
  <mxGeometry relative="1" as="geometry">
    <mxPoint x="<legend_x + 10>" y="<sync_y>" as="sourcePoint" />
    <mxPoint x="<legend_x + 80>" y="<sync_y>" as="targetPoint" />
  </mxGeometry>
</mxCell>
<mxCell id="leg-sync-text" value="Synchronous request"
        style="text;html=1;align=left;verticalAlign=middle;fontFamily=Helvetica;fontSize=11;fontColor=#333333;"
        vertex="1" parent="1">
  <mxGeometry x="<legend_x + 90>" y="<sync_y - 10>" width="150" height="20" as="geometry" />
</mxCell>

<mxCell id="leg-async-line" value=""
        style="endArrow=classic;endSize=8;html=1;strokeColor=#666666;strokeWidth=2;dashed=1;dashPattern=8 4;"
        edge="1" parent="1">
  <mxGeometry relative="1" as="geometry">
    <mxPoint x="<legend_x + 10>" y="<async_y>" as="sourcePoint" />
    <mxPoint x="<legend_x + 80>" y="<async_y>" as="targetPoint" />
  </mxGeometry>
</mxCell>
<mxCell id="leg-async-text" value="Asynchronous event"
        style="text;html=1;align=left;verticalAlign=middle;fontFamily=Helvetica;fontSize=11;fontColor=#333333;"
        vertex="1" parent="1">
  <mxGeometry x="<legend_x + 90>" y="<async_y - 10>" width="150" height="20" as="geometry" />
</mxCell>
```

Legend height = 35 (title) + (element_count * 35) + (flow_count * 35) + 20 (bottom padding)

---

## CONFIDENCE OVERLAY

When layout plan nodes have `confidence` fields, override the fill color:

| Confidence | fillColor | fontColor |
|---|---|---|
| high | `#1565c0` | `#ffffff` |
| medium | `#ff8f00` | `#000000` |
| low | `#c62828` | `#ffffff` |
| user_provided | `#2e7d32` | `#ffffff` |
| unresolved | `#9e9e9e` | `#000000` |

Add confidence entries to the legend.

---

## SECURITY OVERLAY

When rendering from `layout-plan-security.yaml`, apply security-specific styling to nodes, edges, and boundaries.

### Security Node Labels

Append authn/authz info to the node HTML label:

```xml
value="&lt;b&gt;<Label>&lt;/b&gt;&lt;br&gt;&lt;font style=&quot;font-size:10px&quot;&gt;[<Type>: <Technology>]&lt;/font&gt;&lt;br&gt;&lt;font style=&quot;font-size:9px;color:#cccccc&quot;&gt;<authn_mechanism> / <authz_model>&lt;/font&gt;&lt;br&gt;&lt;br&gt;&lt;font style=&quot;font-size:11px&quot;&gt;<Description>&lt;/font&gt;"
```

- If `authn_mechanism` is `none` or missing: append `&lt;br&gt;&lt;font style=&quot;font-size:9px;color:#ff6666&quot;&gt;[NO AUTHN]&lt;/font&gt;`
- If `authz_model` is `none` or missing: append `&lt;br&gt;&lt;font style=&quot;font-size:9px;color:#ff6666&quot;&gt;[NO AUTHZ]&lt;/font&gt;`
- If both present: append `&lt;br&gt;&lt;font style=&quot;font-size:9px;color:#aaffaa&quot;&gt;[<AUTHN> / <AUTHZ>]&lt;/font&gt;` (e.g., `[OAuth2 / RBAC]`)

### Security Edge Colors

| TLS Status | strokeColor | strokeWidth | Extra Style |
|---|---|---|---|
| Encrypted | `#2e7d32` | 2 | — |
| Unencrypted | `#c62828` | 3 | — (thicker draws attention) |
| Unknown | `#9e9e9e` | 2 | `dashed=1;dashPattern=8 4;` |

### Security Edge Labels

Format: `"<Protocol> :<Port> / TLS <version> / <authn> / <authz>"`

Example: `"HTTPS :443 / TLS 1.3 / OAuth2 / RBAC"`

If data classification present, append: `" [<classification>]"` (e.g., `" [RESTRICTED]"`)

```xml
<mxCell id="<edge-id>" value="&lt;b&gt;<Label>&lt;/b&gt;&lt;br&gt;&lt;font style=&quot;font-size:9px&quot;&gt;<Protocol> :<Port> / TLS <ver> / <authn> / <authz>&lt;/font&gt;"
        style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;endArrow=classic;endSize=8;strokeColor=<tls_color>;strokeWidth=<tls_width>;fontFamily=Helvetica;fontSize=10;fontColor=#333333;labelBackgroundColor=#ffffff;"
        edge="1" parent="1" source="<source-id>" target="<target-id>">
  <mxGeometry relative="1" as="geometry" />
</mxCell>
```

### Trust Zone Boundaries

Use trust zone colors from the C4 Color Scheme table above with dashed borders:

```xml
<mxCell id="<zone-id>" value="&lt;b&gt;<Zone Name>&lt;/b&gt;&lt;br&gt;&lt;font style=&quot;font-size:10px;color:<trust_fontColor>&quot;&gt;[<trust_level>]&lt;/font&gt;"
        style="rounded=1;whiteSpace=wrap;html=1;container=1;collapsible=0;fillColor=<trust_fill>;strokeColor=<trust_stroke>;fontColor=<trust_font>;fontFamily=Helvetica;fontSize=14;fontStyle=1;verticalAlign=top;spacingTop=12;spacingLeft=10;strokeWidth=2;dashed=1;dashPattern=8 4;"
        vertex="1" parent="<parent-id>">
  <mxGeometry x="<x>" y="<y>" width="<computed>" height="<computed>" as="geometry" />
</mxCell>
```

### Security Legend Entries

Add these to the legend when rendering security overlays:

```xml
<!-- TLS Status -->
<mxCell id="leg-encrypted-line" value=""
        style="endArrow=classic;endSize=8;html=1;strokeColor=#2e7d32;strokeWidth=2;"
        edge="1" parent="1">
  <mxGeometry relative="1" as="geometry">
    <mxPoint x="<legend_x + 10>" y="<enc_y>" as="sourcePoint" />
    <mxPoint x="<legend_x + 80>" y="<enc_y>" as="targetPoint" />
  </mxGeometry>
</mxCell>
<mxCell id="leg-encrypted-text" value="TLS Encrypted"
        style="text;html=1;align=left;verticalAlign=middle;fontFamily=Helvetica;fontSize=11;fontColor=#2e7d32;"
        vertex="1" parent="1">
  <mxGeometry x="<legend_x + 90>" y="<enc_y - 10>" width="150" height="20" as="geometry" />
</mxCell>

<mxCell id="leg-unencrypted-line" value=""
        style="endArrow=classic;endSize=8;html=1;strokeColor=#c62828;strokeWidth=3;"
        edge="1" parent="1">
  <mxGeometry relative="1" as="geometry">
    <mxPoint x="<legend_x + 10>" y="<unenc_y>" as="sourcePoint" />
    <mxPoint x="<legend_x + 80>" y="<unenc_y>" as="targetPoint" />
  </mxGeometry>
</mxCell>
<mxCell id="leg-unencrypted-text" value="Unencrypted"
        style="text;html=1;align=left;verticalAlign=middle;fontFamily=Helvetica;fontSize=11;fontColor=#c62828;"
        vertex="1" parent="1">
  <mxGeometry x="<legend_x + 90>" y="<unenc_y - 10>" width="150" height="20" as="geometry" />
</mxCell>

<mxCell id="leg-tls-unknown-line" value=""
        style="endArrow=classic;endSize=8;html=1;strokeColor=#9e9e9e;strokeWidth=2;dashed=1;dashPattern=8 4;"
        edge="1" parent="1">
  <mxGeometry relative="1" as="geometry">
    <mxPoint x="<legend_x + 10>" y="<unk_y>" as="sourcePoint" />
    <mxPoint x="<legend_x + 80>" y="<unk_y>" as="targetPoint" />
  </mxGeometry>
</mxCell>
<mxCell id="leg-tls-unknown-text" value="TLS Unknown"
        style="text;html=1;align=left;verticalAlign=middle;fontFamily=Helvetica;fontSize=11;fontColor=#9e9e9e;"
        vertex="1" parent="1">
  <mxGeometry x="<legend_x + 90>" y="<unk_y - 10>" width="150" height="20" as="geometry" />
</mxCell>

<!-- Trust Zones -->
<mxCell id="leg-trusted" value="Trusted Zone"
        style="rounded=1;whiteSpace=wrap;html=1;fillColor=#f1f8e9;strokeColor=#2e7d32;fontColor=#1b5e20;fontFamily=Helvetica;fontSize=10;dashed=1;dashPattern=8 4;"
        vertex="1" parent="1">
  <mxGeometry x="<legend_x + 10>" y="<tz_y>" width="110" height="26" as="geometry" />
</mxCell>
<mxCell id="leg-semi-trusted" value="Semi-Trusted"
        style="rounded=1;whiteSpace=wrap;html=1;fillColor=#fffde7;strokeColor=#f9a825;fontColor=#f57f17;fontFamily=Helvetica;fontSize=10;dashed=1;dashPattern=8 4;"
        vertex="1" parent="1">
  <mxGeometry x="<legend_x + 130>" y="<tz_y>" width="110" height="26" as="geometry" />
</mxCell>
<mxCell id="leg-untrusted" value="Untrusted"
        style="rounded=1;whiteSpace=wrap;html=1;fillColor=#fce4ec;strokeColor=#c62828;fontColor=#b71c1c;fontFamily=Helvetica;fontSize=10;dashed=1;dashPattern=8 4;"
        vertex="1" parent="1">
  <mxGeometry x="<legend_x + 10>" y="<tz_y + 32>" width="110" height="26" as="geometry" />
</mxCell>
```

---

## DEPLOYMENT DIAGRAMS

Deployment diagrams place containers and components into network zones with infrastructure resources.

### Zone Boundaries
- Use trust zone colors from the Trust Zone Colors table
- All zone boundaries: `dashed=1;dashPattern=8 4;` (dashed border)
- Zone title includes trust level: `"<Zone Name> [<trust_level>]"`
- Nest infrastructure resources (WAF, load balancer, IDS) inside their zone

### Infrastructure Resource Nodes
```xml
<mxCell id="<infra-id>" value="&lt;b&gt;<Name>&lt;/b&gt;&lt;br&gt;&lt;font style=&quot;font-size:10px&quot;&gt;[<resource_type>: <Technology>]&lt;/font&gt;"
        style="rounded=1;whiteSpace=wrap;html=1;overflow=hidden;clip=1;fillColor=#ff8f00;strokeColor=#e65100;fontColor=#ffffff;fontFamily=Helvetica;fontSize=12;arcSize=10;strokeWidth=2;verticalAlign=middle;spacing=8;"
        vertex="1" parent="<zone-id>">
  <mxGeometry x="<x>" y="<y>" width="160" height="70" as="geometry" />
</mxCell>
```

### Container/Component Placement
- Place inside their assigned zone boundary using `parent="<zone-id>"`
- Use relative coordinates within the zone
- Apply same node templates as non-deployment diagrams

### Derived Links
- Include full protocol detail: `"<Protocol> :<Port>"`
- Add warning annotations from the layout plan (e.g., zone crossing warnings)
- Warning edges use `strokeColor=#ff8f00;` (orange) with a warning icon in the label:
  `"&lt;font color=&quot;#ff8f00&quot;&gt;&#9888;&lt;/font&gt; <warning text>"`

---

## LUCIDCHART COMPATIBILITY NOTES

### What works
1. **Use simple shapes** — rounded rectangles, cylinders, text. Avoid `mxgraph.c4.*` stencils (Lucidchart maps shapes to its own library, custom stencils are lost)
2. **Set explicit x,y on everything** — never rely on auto-layout (Lucidchart does not auto-layout imported diagrams)
3. **Use `orthogonalEdgeStyle`** — produces clean right-angle edges (note: elbow points may not be perfectly preserved)
4. **Use `labelBackgroundColor=#ffffff`** on edges — prevents label/line overlap
5. **Container children use relative coords** — `parent="<container-id>"` with x,y relative to container
6. **Basic shapes, text content, and connectors** import cleanly
7. **Multi-page diagrams** are supported

### Known Lucidchart import limitations (confirmed from help center/community)
1. **CRITICAL: Edge labels are NOT preserved** — Lucidchart drops `value` text from edge cells during import. Workaround: Add a separate text `mxCell` positioned along the edge path as a label overlay (vertex, not edge)
2. **Rectangles may import as text shapes** — uncompressed XML rectangles sometimes become text objects. Use `rounded=1` in style to help Lucidchart classify correctly
3. **Custom mxGraph stencils are lost** — Lucidchart maps to its own shape library, not mxGraph stencils. This is why we avoid `mxgraph.c4.*`
4. **Visual fidelity is approximate** — Lucidchart prioritizes functional fidelity over visual fidelity; colors/fonts/spacing may differ slightly
5. **No round-trip** — Lucidchart can import Draw.io XML but cannot export back to Draw.io format
6. **No API import** — Draw.io import only works through the Lucidchart editor UI, not the REST API
7. **Blank page on import** — if this occurs, try switching between compressed/uncompressed XML format

### Edge label workaround
Since edge labels are dropped on import, add critical labels as separate positioned text cells:

```xml
<!-- Edge (label will be lost in Lucidchart) -->
<mxCell id="edge-1" value="&lt;b&gt;Routes requests&lt;/b&gt;&lt;br&gt;HTTPS"
        style="edgeStyle=orthogonalEdgeStyle;html=1;endArrow=classic;strokeColor=#333333;strokeWidth=2;"
        edge="1" parent="1" source="api-tier" target="app-core">
  <mxGeometry relative="1" as="geometry" />
</mxCell>

<!-- Backup label as text cell (survives Lucidchart import) -->
<mxCell id="edge-1-label" value="Routes requests (HTTPS)"
        style="text;html=1;align=center;verticalAlign=middle;fontSize=10;fontColor=#333333;labelBackgroundColor=#ffffff;"
        vertex="1" parent="1">
  <mxGeometry x="450" y="85" width="130" height="20" as="geometry" />
</mxCell>
```

Position the text cell at the midpoint of the edge path.

### Test import workflow
1. Open `.drawio` file in diagrams.net (draw.io) first — verify rendering
2. Import into Lucidchart via `File > Import > Draw.io`
3. Check: shapes rendered correctly, edge connections preserved, text labels visible
4. Manual fix: re-add any edge labels that were dropped

### Lucidchart Standard Import API (alternative path)

Lucidchart offers a programmatic **Standard Import API** using a JSON-based `.lucid` format (ZIP file containing `document.json` + optional images/data). This bypasses Draw.io XML limitations entirely.

**API endpoint:** `POST https://api.lucid.co/v1/documents`
- Content type: `x-application/vnd.lucid.standardImport`
- Creates new documents (cannot edit existing)

**Key format differences from Draw.io XML:**
- Shapes use JSON with `id`, `type`, `boundingBox` (x, y, w, h), `style`, `text`
- Lines use `lineType` (straight/elbow/curved), `endpoint1`/`endpoint2` with 24 arrow styles
- Line text is positioned with `position` (0.0-1.0) — **labels are preserved**
- Containers use `magnetize` property for child movement
- Shape libraries: standard, flowchart, container, BPMN 2.0, table

**C4 element mapping to Lucid Standard Import:**
- Person/System/Container/Component → `rectangle` with rounded style + C4 colors
- Database → `database` from flowchart library
- Boundary → `rectangleContainer` from container library
- Edges → `elbow` line type with `arrow` endpoint style

This is a future enhancement opportunity: generate `.lucid` JSON directly instead of Draw.io XML for guaranteed Lucidchart fidelity.

---

## SELF-VALIDATION

Before finishing each diagram, verify:
1. All `id` attributes are unique across the entire XML
2. All `source` and `target` attributes on edges reference existing vertex IDs
3. No two nodes have overlapping geometry (check x,y,width,height don't intersect)
4. All children of containers have coordinates within the container bounds
5. Legend is present and positioned to the right of all content
6. XML is well-formed (proper nesting, all tags closed)
7. All content cells include `fontFamily=Helvetica` in their style string
8. No node has width < 120 or height < 60 (text would clip)
9. Every edge with a `value` attribute has a corresponding `-label` backup text cell
10. Security overlay edges use correct TLS status colors (green/red/grey)

Report warnings:
```
⚠ 1 warning: nodes "api-gw" and "auth-svc" would overlap at (340,60) — shifted auth-svc to row 1
```

---

## DETERMINISTIC VALIDATION

After writing each diagram file, run the syntax validator to catch errors deterministically:

```bash
python tools/validate-diagram.py drawio <file.drawio>
```

The validator checks:
- XML well-formedness
- `mxfile > diagram > mxGraphModel > root` hierarchy
- Required cells with `id="0"` and `id="1"`
- All cell IDs are unique
- All edge `source`/`target` reference existing vertex IDs
- All vertices have `<mxGeometry>` elements
- All `parent` references point to existing cells
- No overlapping vertex geometries (same-parent siblings)

**Fix ALL errors** (exit code 1) before completing. Warnings should be reviewed.

To validate all diagrams in a directory at once:
```bash
python tools/validate-diagram.py all <diagrams-directory>
```
