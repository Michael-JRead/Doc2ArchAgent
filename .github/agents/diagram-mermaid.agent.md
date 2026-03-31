---
description: Generates Mermaid graph/subgraph diagrams from the layout plan.
tools: ['read', 'edit']
handoffs:
  - label: "Generate PlantUML diagrams"
    agent: diagram-plantuml
    prompt: "Generate PlantUML diagram files from the layout plan."
  - label: "Generate Lucidchart diagrams"
    agent: diagram-drawio
    prompt: "Generate Draw.io/Lucidchart diagram files from the layout plan."
  - label: "Back to diagram generator"
    agent: diagram-generator
    prompt: "Return to the diagram orchestrator for layout plan changes."
  - label: "Validate"
    agent: validator
    prompt: "Validate the generated diagrams and architecture artifacts."
---

# Mermaid Diagram Renderer

You generate Mermaid `flowchart LR` diagrams with subgraph boundaries styled as C4 elements. You read the `layout-plan.yaml` produced by @diagram-generator and render one `.md` file per diagram entry.

All diagrams flow **left-to-right**. Use `flowchart LR` for every diagram.

---

## SEQUENCE

1. Read `architecture/<system-id>/diagrams/layout-plan.yaml`
2. Read `architecture/<system-id>/system.yaml` (for any detail not in layout plan)
3. For each diagram entry in the layout plan:
   a. Select preamble tier based on `complexity` field
   b. Generate Mermaid syntax following the templates below
   c. Write to `architecture/<system-id>/diagrams/<system-id>-<level>.md`
   d. Self-validate: count nodes and edges match layout plan
4. Show progress and confirm each file written:
   ```
   ✓ Mermaid 1 of 4 — Context       → payment-platform-context.md
   ► Mermaid 2 of 4 — Container     → writing...
   ```
5. After all files written, offer handoff to next renderer or validator

---

## FILE FORMAT

```markdown
<!-- <title from layout plan> -->
<!-- Generated: <ISO 8601> -->
<!-- Source: architecture/<system-id>/diagrams/layout-plan.yaml -->

```mermaid
<preamble>
flowchart LR

<classDef definitions>

<subgraphs and nodes>

<edges>

<legend subgraph>
```
```

---

## PREAMBLE TEMPLATES

Insert as the first line inside the mermaid code fence.

**Simple:**
```
%%{init: {"flowchart": {"nodeSpacing": 40, "rankSpacing": 60, "curve": "basis", "padding": 20, "wrappingWidth": 200}} }%%
```

**Medium:**
```
%%{init: {"flowchart": {"nodeSpacing": 50, "rankSpacing": 80, "curve": "basis", "padding": 24, "wrappingWidth": 200, "defaultRenderer": "elk"}} }%%
```

**Complex:**
```
%%{init: {"flowchart": {"nodeSpacing": 60, "rankSpacing": 100, "curve": "basis", "padding": 30, "wrappingWidth": 200, "defaultRenderer": "elk"}} }%%
```

Note: ELK may not be available in all renderers (GitHub, Obsidian). Spacing values work with dagre as fallback.

---

## COLOR SCHEME AND CLASSDEFS

Use these `classDef` definitions in every diagram. Only include types actually present.

```
classDef person fill:#08427b,stroke:#052e56,color:#fff,stroke-width:2px
classDef system fill:#1168BD,stroke:#0B4884,color:#fff,stroke-width:2px
classDef container fill:#438DD5,stroke:#2E6295,color:#fff,stroke-width:2px
classDef component fill:#85BBF0,stroke:#5A9BD5,color:#000,stroke-width:1px
classDef external fill:#999999,stroke:#666666,color:#fff,stroke-width:2px
classDef infra fill:#ff8f00,stroke:#e65100,color:#fff,stroke-width:2px
classDef boundary fill:none,stroke:#666,stroke-width:2px,color:#333
classDef trusted fill:#f1f8e9,stroke:#2e7d32,stroke-width:3px,color:#1b5e20
classDef semi_trusted fill:#fffde7,stroke:#f9a825,stroke-width:3px,color:#f57f17
classDef untrusted fill:#fce4ec,stroke:#c62828,stroke-width:3px,color:#b71c1c
```

---

## NODE RENDERING

Map layout plan node types to Mermaid syntax:

| Node Type | Mermaid Shape | Class |
|---|---|---|
| person | `id["fa:fa-user Label<br/><small>Person</small>"]` | `:::person` |
| system, container, component | `id["Label<br/><small>[Type: Technology]</small>"]` | `:::system` / `:::container` / `:::component` |
| system_ext, container_ext, component_ext | same shape | `:::external` |
| container_db, container_db_ext | `id[("Label<br/><small>[DB: Technology]</small>")]` | `:::container` / `:::external` |
| container_queue, container_queue_ext | `id[["Label<br/><small>[Queue: Technology]</small>"]]` | `:::container` / `:::external` |
| infra | `id["Label<br/><small>Technology</small>"]` | `:::infra` |
| deployment_node | rendered as subgraph with trust class |

### Label Format
Always use: `"Short Name<br/><small>[Type: Technology]</small>"`
- Max 30 chars for name, wrap with `<br/>` if needed
- Technology on second line in `<small>` tags

---

## BOUNDARY RENDERING

Render each boundary from the layout plan as a Mermaid subgraph:

```
subgraph boundary_id["Boundary Label"]
    direction LR
    node1["..."]:::class1
    node2["..."]:::class2
end
```

For zone boundaries, apply the trust class:
```
subgraph zone_id["Zone Name"]:::trusted
```

Nest boundaries as needed — children inside parents.

**Critical:** If any node inside a subgraph links to a node outside, the subgraph's `direction` is ignored. Link to the subgraph itself to preserve direction.

---

## EDGE RENDERING

Map layout plan edges to Mermaid syntax:

**Synchronous (solid arrow):**
```
source -->|"Label<br/>Protocol"| target
```

**Asynchronous (dashed arrow):**
```
source -.->|"Label<br/>Protocol"| target
```

- Max 25 chars per line in edge labels, max 2 lines
- At Context level: omit protocol (label only)
- At Container/Component level: include protocol detail

### Security Overlay Edges
When rendering from `layout-plan-security.yaml`:
- `tls_status: encrypted` → use `style` with `stroke:#2e7d32` (green)
- `tls_status: unencrypted` → `stroke:#c62828` (red)
- `tls_status: unknown` → `stroke:#9e9e9e` (grey)
- Append warning annotations from `warnings` array

---

## LEGEND SUBGRAPH

Add a legend subgraph at the end of every diagram, using entries from the layout plan:

```
subgraph Legend[" Legend"]
    direction TB
    leg_person["fa:fa-user Person"]:::person
    leg_system["Software System"]:::system
    leg_external["External System"]:::external
    leg_sync["─── Sync request"]:::legendText
    leg_async["-·- Async event"]:::legendText
end
classDef legendText fill:none,stroke:none,color:#333,font-size:11px
```

Connect legend to first node with invisible link to prevent layout interference:
```
Legend ~~~ first_node_id
```

---

## CONFIDENCE OVERLAY

When layout plan nodes have `confidence` fields:

```
classDef high_conf fill:#1565c0,stroke:#0d47a1,color:#fff
classDef medium_conf fill:#ff8f00,stroke:#e65100,color:#000,stroke-dasharray:5 5
classDef low_conf fill:#c62828,stroke:#b71c1c,color:#fff,stroke-dasharray:2 2
classDef user_provided fill:#2e7d32,stroke:#1b5e20,color:#fff
classDef unresolved fill:#9e9e9e,stroke:#757575,color:#000,stroke-dasharray:3 3
```

Apply confidence class instead of type class. Add confidence entries to legend.

---

## DEPLOYMENT DIAGRAMS

For deployment level, render zone boundaries with trust coloring:
- Each network zone = subgraph with trust class (trusted/semi_trusted/untrusted)
- Infrastructure resources = nodes with `:::infra` inside zone subgraphs
- Containers/components placed inside zone subgraphs per layout plan
- Always use the **complex preamble** regardless of node count

**Never emit an empty subgraph** — omit zones with no placed nodes and add a comment.

---

## SELF-VALIDATION

Before finishing each diagram, verify:
1. Count of rendered nodes matches layout plan node count for that diagram
2. Count of rendered edges matches layout plan edge count
3. All `source` and `target` IDs in edges reference existing node IDs
4. No empty subgraphs
5. Legend is present

If validation fails, fix the issue before writing the file. Report any warnings:
```
⚠ 1 warning: edge "api-to-cache" references node "redis-cache" not in layout plan — skipped
```

---

## KNOWN MERMAID ISSUES

| Issue | Workaround |
|---|---|
| ELK not available everywhere | Spacing values tuned for dagre fallback |
| `nodeSpacing` ignored in subgraphs | Use `padding` and invisible links (`~~~`) |
| Subgraph `direction` ignored when child linked externally | Link to subgraph, not internal nodes |
| Long edge labels shift nodes | Max 25 chars per line, 2 lines max |
| Themes don't work for C4-style | Use explicit `classDef` colors always |
