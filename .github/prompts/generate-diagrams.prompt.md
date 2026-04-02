---
description: Generate architecture diagrams from YAML model
---

Generate architecture diagrams from the system.yaml model:

1. Read the system.yaml and networks.yaml files
2. Build a layout plan at `diagrams/layout-plan.yaml` with grid coordinates
3. Generate diagrams in the requested format(s):
   - **Mermaid** (.md) — for GitHub rendering and documentation
   - **PlantUML** (.puml) — for detailed C4 diagrams
   - **Draw.io** (.drawio) — for Lucidchart/Draw.io import
   - **Structurizr** (.dsl) — for Structurizr ecosystem
   - **D2** (.d2) — for modern diagram rendering

If no format is specified, generate Mermaid diagrams by default.

Generate these diagram levels:
- **Context** — C4 Level 1 showing systems and external actors
- **Container** — C4 Level 2 showing containers within the system
- **Component** — C4 Level 3 showing components within containers (if components exist)
- **Deployment** — Zone placement view (if deployment YAML exists)
