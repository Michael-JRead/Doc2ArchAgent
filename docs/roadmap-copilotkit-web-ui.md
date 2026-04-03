# Roadmap: CopilotKit Web UI for Doc2ArchAgent

> **Status:** Future roadmap consideration
> **Date:** 2026-04-03
> **Research basis:** Deep analysis of [CopilotKit](https://github.com/CopilotKit/CopilotKit), AG-UI protocol, LangGraph, and Doc2ArchAgent internals

---

## Executive Summary

This document outlines how to build a full web UI for Doc2ArchAgent using **CopilotKit** (React) + **LangGraph** (Python), replacing the VS Code Copilot Chat dependency while keeping all 25+ Python tools completely unchanged.

**Key finding:** VS Code Copilot `.agent.md` files have **no API** — they cannot be invoked programmatically from outside VS Code. The solution is to replicate the agent orchestration in LangGraph using the same prompts and Python tools, then connect a CopilotKit React frontend for a full web experience.

**What stays unchanged:** All 25+ Python CLI tools (`validate.py`, `threat-rules.py`, `compose.py`, `ingest-*.py`, etc.)

**What changes:** The orchestration layer moves from "VS Code Copilot Chat manages conversations" to "LangGraph manages conversations + CopilotKit provides the web UI."

---

## Why CopilotKit

[CopilotKit](https://github.com/CopilotKit/CopilotKit) is the leading open-source SDK for building full-stack agentic applications with rich web UIs. It was chosen for this roadmap because:

1. **AG-UI Protocol** — Industry-standard event-based protocol (adopted by Google, LangChain, AWS, Microsoft) for streaming agent state to frontends via Server-Sent Events (SSE)
2. **LangGraph Integration** — First-class Python SDK (`copilotkit` PyPI package) with `LangGraphAgent` adapter
3. **Rich UI Components** — `CopilotChat`, `CopilotSidebar`, `CopilotPopup` with slots-based customization
4. **Bidirectional State** — `useCopilotReadable` (app → agent) and `useCopilotAction` (agent → app) hooks
5. **Generative UI** — Agents can render custom React components (diagrams, tables, dashboards) directly in chat
6. **Human-in-the-Loop** — Agents can pause for user approval, matching Doc2ArchAgent's "approve each layer" workflow
7. **Multi-Agent Support** — LangGraph subgraphs for coordinating specialized agents

### Alternatives Considered

| Project | Why Not Primary Choice |
|---------|----------------------|
| **A2UI** (Google) | Declarative UI spec only — no runtime, no agent orchestration |
| **assistant-ui** | Chat library only — no agent framework integration |
| **Letta** | Memory-focused agent platform — no frontend components |
| **Custom WebSocket** | Too much protocol/streaming work to build from scratch |
| **VS Code WebView Extension** | Stays in VS Code — doesn't solve "full web UI" requirement |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│  FRONTEND (Next.js + React + CopilotKit)            │
│  ┌──────────┐ ┌──────────────┐ ┌─────────────────┐ │
│  │ Chat     │ │ Diagram      │ │ YAML Editor     │ │
│  │ Sidebar  │ │ Viewer       │ │ + Validation    │ │
│  │(CopilotKit│ │ (mermaid.js) │ │ (Monaco)        │ │
│  └──────────┘ └──────────────┘ └─────────────────┘ │
│         ↕ AG-UI Protocol (SSE)                      │
├─────────────────────────────────────────────────────┤
│  BACKEND (FastAPI + CopilotKit Python SDK)          │
│  ┌──────────────────────────────────────────┐       │
│  │ LangGraph StateGraph (supervisor pattern)│       │
│  │ ┌──────────┐ ┌──────────┐ ┌───────────┐ │       │
│  │ │architect │ │validator │ │diagram_gen│ │       │
│  │ │deployer  │ │security  │ │doc_writer │ │       │
│  │ │doc_*     │ │pattern_* │ │renderers  │ │       │
│  │ └──────────┘ └──────────┘ └───────────┘ │       │
│  └──────────────────────────────────────────┘       │
│         ↕ subprocess calls                          │
│  ┌──────────────────────────────────────────┐       │
│  │ Existing Python Tools (UNCHANGED)         │       │
│  │ validate.py, threat-rules.py, compose.py │       │
│  │ ingest-*.py, confidence.py, etc.         │       │
│  └──────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────┘
```

### Protocol Stack

```
CopilotKit React Hooks ──── useCopilotReadable (app state → agent)
         │                  useCopilotAction   (agent → app UI)
         │
    AG-UI Protocol ──────── Server-Sent Events over HTTP
         │                  Token streaming, tool calls, state deltas (JSON Patch)
         │
CopilotKit Python SDK ───── LangGraphAgent adapter
         │
    LangGraph ───────────── StateGraph with supervisor routing
         │                  Nodes = agents, Edges = handoffs
         │
    Python Tools ────────── subprocess.run() wrappers (unchanged CLI tools)
```

---

## Project Structure

```
doc2archagent/
├── tools/                     # EXISTING — 25+ Python tools, UNCHANGED
├── schemas/                   # EXISTING — 12 JSON schemas, UNCHANGED
├── .github/agents/            # EXISTING — kept as reference/documentation
│
├── backend/                   # NEW
│   ├── pyproject.toml
│   └── app/
│       ├── main.py            # FastAPI + CopilotKit SDK mount
│       ├── config.py          # LLM provider settings
│       ├── agents/
│       │   ├── graph.py       # Master LangGraph StateGraph
│       │   ├── state.py       # AgentState TypedDict
│       │   ├── router.py      # Supervisor routing logic
│       │   ├── nodes/         # One module per agent (11 nodes)
│       │   │   ├── architect.py
│       │   │   ├── doc_collector.py
│       │   │   ├── doc_extractor.py
│       │   │   ├── deployer.py
│       │   │   ├── security_reviewer.py
│       │   │   ├── validator.py
│       │   │   ├── pattern_manager.py
│       │   │   ├── diagram_generator.py
│       │   │   ├── diagram_renderers.py  # 5 renderers consolidated
│       │   │   ├── diagram_diff.py
│       │   │   └── doc_writer.py
│       │   └── prompts/       # System prompts extracted from .agent.md
│       ├── tools/
│       │   └── wrappers.py    # LangGraph @tool wrappers for CLI tools
│       ├── projects/
│       │   └── manager.py     # Server-side file/project storage
│       └── copilotkit/
│           └── setup.py       # CopilotKit + LangGraphAgent config
│
├── frontend/                  # NEW
│   ├── package.json
│   ├── next.config.js
│   └── src/
│       ├── app/
│       │   ├── layout.tsx     # CopilotKit provider
│       │   └── page.tsx       # Main workspace page
│       ├── components/
│       │   ├── ArchitectureWorkspace.tsx  # Multi-panel layout
│       │   ├── ChatPanel.tsx             # CopilotSidebar wrapper
│       │   ├── DiagramViewer.tsx         # mermaid.js live renderer
│       │   ├── YamlEditor.tsx            # Monaco editor with JSON Schema
│       │   ├── ValidationPanel.tsx       # SARIF/table results display
│       │   ├── ThreatDashboard.tsx       # Security findings view
│       │   ├── ConfidenceOverlay.tsx     # Color-coded diagram annotations
│       │   ├── AgentStatusBar.tsx        # Active agent + handoff indicator
│       │   ├── FileManager.tsx           # Project file tree + upload/download
│       │   └── ProjectSelector.tsx       # Project switching
│       └── hooks/
│           ├── useArchitectureState.ts   # CopilotKit readables + actions
│           ├── useDiagramRenderer.ts     # Mermaid rendering hook
│           └── useProjectFiles.ts        # File management hook
│
└── docker-compose.yml         # NEW — backend + frontend orchestration
```

---

## Agent Mapping: .agent.md to LangGraph Nodes

### 10 LLM-Driven Agents

Each becomes a LangGraph node that calls an LLM with the system prompt extracted from the `.agent.md` body:

| VS Code Agent | LangGraph Node | System Prompt Source | Key Tools |
|---|---|---|---|
| `@architect` | `architect` | `architect.agent.md` body (360 lines) | read/write YAML, validate.py |
| `@doc-collector` | `doc_collector` | `doc-collector.agent.md` body | convert-docs.py, detect-tools.py, classify-sections.py |
| `@doc-extractor` | `doc_extractor` | `doc-extractor.agent.md` body | validate.py, validate-provenance.py, entity_resolver.py |
| `@deployer` | `deployer` | `deployer.agent.md` body | compose.py, validate.py |
| `@security-reviewer` | `security_reviewer` | `security-reviewer.agent.md` body | threat-rules.py, validate.py |
| `@validator` | `validator` | `validator.agent.md` body | validate.py, validate-patterns.py, validate-diagram.py |
| `@pattern-manager` | `pattern_manager` | `pattern-manager.agent.md` body | validate-patterns.py, compose.py, migrate-pattern.py |
| `@diagram-generator` | `diagram_generator` | `diagram-generator.agent.md` body | validate-diagram.py |
| `@diagram-diff` | `diagram_diff` | `diagram-diff.agent.md` body | file reads, git diff |
| `@doc-writer` | `doc_writer` | `doc-writer.agent.md` body | file reads |

### 5 Deterministic Renderers (consolidated into 1 node — NO LLM call)

| VS Code Agent | Combined Node | Approach |
|---|---|---|
| `@diagram-mermaid` | `diagram_renderer` | Pure Python rendering (template specs from .agent.md) |
| `@diagram-plantuml` | `diagram_renderer` | Pure Python rendering |
| `@diagram-drawio` | `diagram_renderer` | Pure Python rendering |
| `@diagram-structurizr` | `diagram_renderer` | Pure Python rendering |
| `@diagram-d2` | `diagram_renderer` | Pure Python rendering |

All 5 have `disable-model-invocation: true` in their frontmatter — they are template-based, not LLM-driven. Their template specifications (classDefs, node shapes, edge styles, preambles, legends) get translated into Python string-formatting functions. This is the single largest engineering task.

---

## Handoffs as LangGraph Routing

In VS Code, handoffs are YAML arrays with `label`, `agent`, and `prompt`. In LangGraph:

**Supervisor pattern:** A central `router` node dispatches to the active agent based on state.

```
User message → router → (picks active agent) → agent node → (may call handoff tool) → router → next agent → ...
```

Each LLM agent has a `handoff` tool constrained to only the targets declared in its `.agent.md` frontmatter `agents` field:

```python
@tool
def handoff(target: Literal["validator", "deployer", ...], context: str) -> str:
    """Hand off to another specialized agent."""
    return json.dumps({"handoff_to": target, "context": context})
```

The router reads `active_agent` from state and dispatches accordingly.

---

## Python Tools as LangGraph Tools

Each CLI tool gets a `@tool`-decorated wrapper using `subprocess.run()`:

```python
from langchain_core.tools import tool
import subprocess

TOOLS_DIR = Path(__file__).parents[3] / "tools"

@tool
def validate_architecture(system_yaml_path: str, format: str = "json") -> str:
    """Validate architecture YAML for structural correctness and referential integrity.
    Returns JSON with errors and warnings. 17 SARIF rules (ARCH001-ARCH017)."""
    result = subprocess.run(
        ["python", str(TOOLS_DIR / "validate.py"), system_yaml_path, "--format", format],
        capture_output=True, text=True, cwd=str(TOOLS_DIR.parent)
    )
    return result.stdout or result.stderr

@tool
def run_threat_analysis(system_yaml_path: str, networks_yaml_path: str = "",
                        environment: str = "production") -> str:
    """Run deterministic STRIDE threat analysis. Returns JSON findings with CWE/compliance refs."""
    cmd = ["python", str(TOOLS_DIR / "threat-rules.py"), system_yaml_path, "--format", "json"]
    if networks_yaml_path:
        cmd.extend(["--networks", networks_yaml_path])
    cmd.extend(["--environment", environment])
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(TOOLS_DIR.parent))
    return result.stdout or result.stderr

# ... similar wrappers for all 25+ tools
```

The existing `tools/agent-bridge.py` already wraps several tools (validate, threat, confidence, compose, diagram validate) — it can serve as the foundation, reducing the number of individual subprocess wrappers needed.

---

## Frontend: CopilotKit Integration Details

### Workspace Layout

```
+-------------------------------------------+
| [Project Selector] [Agent: @architect]    |
+----------+----------------+---------------+
|          |                |               |
|  File    |   Main Panel   |    Chat      |
|  Tree    |   (tabs):      |   (CopilotKit|
|          |   - Diagram    |    Sidebar)  |
|          |   - YAML       |               |
|          |   - Validation |               |
|          |   - Threats    |               |
|          |                |               |
+----------+----------------+---------------+
```

### CopilotKit Hooks

**useCopilotReadable** — shares app state with the agent:
```tsx
useCopilotReadable({ description: "Current system.yaml content", value: systemYaml });
useCopilotReadable({ description: "Currently active diagram", value: activeDiagram });
useCopilotReadable({ description: "Latest validation results", value: validationResults });
```

**useCopilotAction** — maps agent tool calls to frontend UI updates:
```tsx
useCopilotAction({
  name: "show_diagram",
  description: "Display a Mermaid diagram in the viewer",
  parameters: [
    { name: "mermaid_source", type: "string" },
    { name: "title", type: "string" },
  ],
  handler: async ({ mermaid_source, title }) => {
    setActiveDiagram({ source: mermaid_source, title });
    setActiveTab("diagram");
  },
});

useCopilotAction({
  name: "show_validation_results",
  description: "Display validation results in the panel",
  parameters: [{ name: "results_json", type: "string" }],
  handler: async ({ results_json }) => {
    setValidationResults(JSON.parse(results_json));
    setActiveTab("validation");
  },
});

useCopilotAction({
  name: "update_yaml",
  description: "Update YAML file content in the editor",
  parameters: [
    { name: "file_name", type: "string" },
    { name: "content", type: "string" },
  ],
  handler: async ({ file_name, content }) => {
    setYamlFiles(prev => ({ ...prev, [file_name]: content }));
    setActiveTab("yaml");
  },
});
```

### Diagram Rendering

The `DiagramViewer` component uses `mermaid.js` to render Mermaid source in real-time. The existing layout-plan.yaml schema includes a `confidence` field on each node; after Mermaid renders the SVG, a post-processing step applies CSS classes for confidence visualization (blue=HIGH, amber=MEDIUM, red=LOW, green=user-provided, grey=unresolved).

### File Management REST API

Separate from the AG-UI chat protocol (binary files don't go through SSE):

```
POST   /api/projects                     # Create project
GET    /api/projects                     # List projects
GET    /api/projects/{id}/files          # List files
GET    /api/projects/{id}/files/{path}   # Read file
PUT    /api/projects/{id}/files/{path}   # Write file
POST   /api/projects/{id}/upload         # Upload document (PDF, DOCX)
GET    /api/projects/{id}/download/{path} # Download file
GET    /api/projects/{id}/download-zip   # Download project as ZIP
```

---

## Phased Implementation Plan

### Phase 1: MVP — Single Agent Chat + YAML Display (3-4 weeks)

- Set up `backend/` with FastAPI + CopilotKit Python SDK
- Create `AgentState` with minimal fields (messages, system_yaml, active_agent)
- Implement `architect` node with full system prompt from `architect.agent.md`
- Wrap 3 essential tools: `validate.py`, `read_project_file`, `write_project_file`
- Implement `ProjectManager` with filesystem storage
- Set up `frontend/` with Next.js + CopilotKit
- Build `CopilotSidebar` chat panel
- Build `YamlEditor` with Monaco editor + schema validation
- Wire `useCopilotReadable` and `useCopilotAction` hooks
- Docker Compose for backend + frontend

**Deliverable:** User can chat with @architect, build YAML interactively, see it update in the editor.

### Phase 2: Validation + Diagrams (2-3 weeks)

- Add `validator` and `diagram_generator` nodes
- Implement Mermaid renderer as pure Python (translate template specs from `diagram-mermaid.agent.md`)
- Build `DiagramViewer` component with mermaid.js
- Build `ValidationPanel` component (parse SARIF JSON)
- Add handoff routing: architect ↔ validator ↔ diagram_generator
- Wire `show_diagram` and `show_validation_results` actions

**Deliverable:** Full architect → validate → generate diagrams → view flow.

### Phase 3: Security + Document Ingestion (2-3 weeks)

- Add `security_reviewer`, `doc_collector`, `doc_extractor` nodes
- Wrap convert-docs.py, classify-sections.py, entity_resolver.py, confidence.py
- Implement file upload endpoint and `FileManager` component
- Build `ThreatDashboard` component
- Add confidence overlay to diagram viewer

**Deliverable:** Full document ingestion pipeline and security analysis working in browser.

### Phase 4: Remaining Agents + Polish (2-3 weeks)

- Add `deployer`, `pattern_manager`, `doc_writer`, `diagram_diff` nodes
- Implement PlantUML, Draw.io, Structurizr, D2 renderers (pure Python)
- Build `AgentStatusBar` showing active agent and handoff history
- Add `ProjectSelector` for multi-project support
- Implement download-as-ZIP for projects

**Deliverable:** All 15 agents operational, full feature parity with VS Code agent system.

### Phase 5: Production Hardening (2-3 weeks)

- Authentication (OAuth2 or API keys)
- Rate limiting and cost controls for LLM calls
- LangGraph checkpointing with persistent storage (PostgreSQL)
- Connection recovery for long sessions
- End-to-end tests
- Performance optimization (lazy loading, diagram caching)
- Production Docker multi-stage build

**Total estimated timeline: 12-16 weeks**

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Frontend Framework | Next.js 14 + React 18 | SSR, routing, API proxy |
| Chat UI | @copilotkit/react-core + @copilotkit/react-ui | Chat interface, state sync |
| Diagram Rendering | mermaid.js 10.x | SVG diagram rendering in browser |
| YAML Editor | Monaco Editor (@monaco-editor/react) | Syntax highlighting, JSON Schema validation |
| Schema Validation | Ajv (frontend) | YAML schema validation in browser |
| Backend Framework | FastAPI + Uvicorn | HTTP/SSE server |
| Agent Orchestration | LangGraph 0.2+ | State machine for multi-agent workflows |
| CopilotKit Runtime | copilotkit Python SDK | AG-UI protocol adapter |
| LLM Provider | langchain-openai or langchain-anthropic | LLM calls |
| Python Tools | Existing 25+ scripts (UNCHANGED) | Deterministic processing |
| File Storage | Server filesystem (Docker volume) | Project data persistence |
| Containerization | Docker + Docker Compose | Development and deployment |

---

## Key Risk Areas

| Risk | Impact | Mitigation |
|---|---|---|
| **Renderer translation** (5 agents → pure Python) | Largest single engineering task. Each renderer agent has 100-200 lines of template specifications. | Start with Mermaid only (Phase 2). Add others incrementally in Phase 4. |
| **CopilotKit Python SDK maturity** | API may change; documentation may have gaps. | Budget investigation time. Pin SDK version. |
| **LLM prompt fidelity across providers** | Agent prompts optimized for GPT-4 in VS Code. | Test with target LLM early. May need prompt tuning for Claude. |
| **Long conversation context windows** | Architect has 6-layer sequence; sessions can exceed context limits. | Implement conversation summarization or message pruning strategy. |
| **State size over SSE** | Full YAML in AgentState → expensive to serialize/transmit. | Consider lazy loading; only send diffs via JSON Patch. |
| **Confidence overlay on Mermaid SVG** | Mermaid's SVG output structure isn't always predictable. | Post-process SVG DOM; match node IDs from layout-plan to SVG elements. |

---

## Critical Source Files

| File | Role in Integration |
|---|---|
| `.github/agents/architect.agent.md` | Primary system prompt for the `architect` LangGraph node (360 lines, 6-layer guided modeling sequence) |
| `.github/agents/diagram-mermaid.agent.md` | Template specifications (classDefs, node shapes, edge styles, preamble tiers, legend generation) to translate into pure Python Mermaid renderer |
| `.github/agents/diagram-generator.agent.md` | Defines the `layout-plan.yaml` schema — the contract between the diagram generator and all renderers |
| `tools/agent_supervisor.py` | Existing pipeline orchestrator with `PipelineStage` enum — pattern for LangGraph tool execution |
| `tools/agent-bridge.py` | Existing unified tool bridge wrapping validate, threat, confidence, compose, diagram-validate — foundation for LangGraph tool wrappers |

---

## Related Research

### CopilotKit Ecosystem

- [CopilotKit GitHub](https://github.com/CopilotKit/CopilotKit) — Main repository
- [AG-UI Protocol](https://docs.ag-ui.com/introduction) — Agent-User Interaction Protocol specification
- [CopilotKit Python SDK](https://pypi.org/project/copilotkit/) — PyPI package for FastAPI/LangGraph integration
- [CopilotKit Docs](https://docs.copilotkit.ai) — Official documentation
- [Generative UI Examples](https://github.com/CopilotKit/generative-ui) — AG-UI, A2UI, MCP Apps patterns

### Complementary Technologies

- [A2UI](https://a2ui.org/) — Google's declarative UI specification for agent-driven interfaces
- [LangGraph](https://github.com/langchain-ai/langgraph) — State machine framework for multi-agent orchestration
- [Swark](https://github.com/swark-io/swark) — Architecture diagram generation from source code (VS Code + Copilot)
- [MCP Protocol](https://modelcontextprotocol.io/) — Model Context Protocol for tool integration
