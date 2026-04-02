<p align="center">
  <img src="assets/logo.png" alt="Doc2Arch — Documentation to Architecture" width="600">
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-BSL%201.1-blue.svg" alt="License: BSL 1.1"></a>
</p>

# Doc2ArchAgent

A multi-agent architecture modeling system for VS Code, powered by GitHub Copilot custom agents. Walk through a structured, conversational workflow to transform your software architecture knowledge into well-formed C4 model YAML, deployment maps, security analyses, and auto-generated diagrams — all without leaving your editor.

---

## Table of Contents

- [What This Does](#what-this-does)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [How It Works — The Agent System](#how-it-works--the-agent-system)
- [Complete Step-by-Step Workflow](#complete-step-by-step-workflow)
  - [Phase 0: Document Collection & Extraction (@doc-collector / @doc-extractor)](#phase-0-document-collection--extraction-doc-collector--doc-extractor)
  - [Phase 1: Architecture Modeling (@architect)](#phase-1-architecture-modeling-architect)
  - [Phase 2: Deployment Mapping (@deployer)](#phase-2-deployment-mapping-deployer)
  - [Phase 3: Security Review (@security-reviewer)](#phase-3-security-review-security-reviewer)
  - [Phase 4: Diagram Generation (@diagram-generator)](#phase-4-diagram-generation-diagram-generator)
  - [Phase 5: Validation (@validator)](#phase-5-validation-validator)
  - [Phase 6: Documentation Generation (@doc-writer)](#phase-6-documentation-generation-doc-writer)
- [File Structure Explained](#file-structure-explained)
- [YAML Schema Reference](#yaml-schema-reference)
- [Commands You Can Use Anytime](#commands-you-can-use-anytime)
- [Tips and Best Practices](#tips-and-best-practices)
- [Zero-Hallucination Pipeline](#zero-hallucination-pipeline)
- [Deterministic Validation](#deterministic-validation)
- [STRIDE Threat Analysis](#stride-threat-analysis)
- [Persona-Specific Diagram Views](#persona-specific-diagram-views)
- [How This Compares](#how-this-compares)
- [Known Limitations](#known-limitations)
- [Troubleshooting](#troubleshooting)
- [Templates](#templates)
- [License](#license)
- [Contributing](#contributing)

---

## What This Does

Doc2ArchAgent turns your architecture knowledge into a structured, validated C4 model through a guided conversation. Instead of manually writing YAML or drawing diagrams, you answer questions and the agents build everything for you.

**The end result:**
- A complete `system.yaml` describing your contexts, containers, components, listeners, and relationships
- A `networks.yaml` defining your network zones and infrastructure resources
- Deployment YAML files mapping containers/components to specific network zones per environment
- A `provenance.yaml` tracing every extracted field back to its source document, section, and quote
- C4 diagrams at every level (Context, Container, Component, Deployment) in **3 formats**: Mermaid, PlantUML, and Draw.io/Lucidchart
- Confidence-colored diagrams showing which elements are well-supported vs. need verification
- Persona-specific diagram views (Executive, Architect, Security, Network, Compliance)
- **HLDD (High-Level Design Document)** formatted for Confluence page upload or Markdown
- **Executive summaries** and **stakeholder briefs** tailored to specific audiences
- A STRIDE threat analysis per data flow crossing trust boundaries
- Firewall ACL rules auto-generated from listener data (protocol, port, zone)
- A security findings report identifying vulnerabilities, trust boundary issues, and blast radius
- A deterministic validation report (Python) + semantic validation confirming correctness

**You get all of this by answering guided questions in VS Code chat.**

---

## Prerequisites

| Requirement | Minimum Version | How to Check |
|-------------|----------------|--------------|
| **VS Code** | 1.100+ | `code --version` |
| **GitHub Copilot extension** | Latest | Extensions panel → search "GitHub Copilot" |
| **GitHub Copilot Chat extension** | Latest | Extensions panel → search "GitHub Copilot Chat" |
| **Active GitHub Copilot subscription** | Individual, Business, or Enterprise | [github.com/settings/copilot](https://github.com/settings/copilot) |

> **Note:** Custom agents (`.agent.md`) require GitHub Copilot Chat. The agents use built-in tools (`read`, `edit`, `search`, `execute`) — no MCP servers or external dependencies needed.

| **Python 3** *(optional)* | 3.8+ | `python --version` |
| **PyYAML** *(optional)* | 6.0+ | `pip install pyyaml` |

> **Optional:** Python + PyYAML enables deterministic validation via `tools/validate.py`. Without it, the `@validator` agent uses LLM-only validation.

---

## Installation

### Step 1: Clone the Repository
```bash
git clone https://github.com/Michael-JRead/Doc2ArchAgent.git
cd Doc2ArchAgent
```

### Step 2: Open in VS Code
```bash
code .
```

### Step 3: Verify Agents are Detected
1. Open Copilot Chat: press `Ctrl+Shift+I` (Windows/Linux) or `Cmd+Shift+I` (Mac)
2. Click the **agents dropdown** (the `@` icon or type `@`)
3. You should see all **15 agents** listed:
   - `@architect` — architecture modeling
   - `@doc-collector` — document collection and conversion
   - `@doc-extractor` — document entity extraction
   - `@deployer` — deployment mapping
   - `@security-reviewer` — security analysis
   - `@diagram-generator` — diagram orchestrator
   - `@diagram-mermaid` — Mermaid renderer
   - `@diagram-plantuml` — PlantUML renderer
   - `@diagram-drawio` — Draw.io/Lucidchart renderer
   - `@diagram-structurizr` — Structurizr DSL renderer
   - `@diagram-d2` — D2 language renderer
   - `@diagram-diff` — architecture version comparison
   - `@doc-writer` — documentation generation
   - `@validator` — validation
   - `@pattern-manager` — reusable network and product patterns

If you don't see them, ensure:
- The `.github/agents/` folder is at the root of your workspace
- GitHub Copilot Chat is updated to the latest version
- You have an active Copilot subscription

### Step 4: Start Modeling
Select `@architect` from the dropdown and type your system description. That's it.

---

## How It Works — The Agent System

The system is composed of **10 specialized agents**, each owning a specific concern. They communicate through **handoffs** — when one agent finishes its work, it offers to hand off to the next logical agent. Each handoff includes a descriptive prompt visible in the Copilot UI.

### Agent Overview

#### Core Workflow Agents

| Agent | What It Does | When to Use It |
|-------|-------------|----------------|
| **@doc-collector** | Collects and converts architecture documents (PDF, Word, text, images) into readable text using `tools/convert-docs.py`. Builds a document inventory. | **Start here if you have existing docs.** Collects and prepares documents for extraction. |
| **@doc-extractor** | Extracts architecture entities from collected documents with source citations. Validates with you, then writes YAML. Zero hallucinations. | After `@doc-collector` prepares your documents, or if text files are already in `context/`. |
| **@architect** | Walks you through defining contexts, containers, components, listeners, and relationships. Writes `system.yaml` and `networks.yaml` incrementally. | **Start here if starting fresh.** Or continue after `@doc-extractor` to refine. |
| **@deployer** | Places your containers and components into network zones for specific environments (production, staging, regional deployments). Writes deployment YAML files. | After `@architect` completes your system model, or when you need to add a new deployment. |
| **@security-reviewer** | Reads all YAML and produces security findings, STRIDE threat analysis per data flow, and firewall ACL rules. Checks for unauthenticated listeners, unencrypted flows, trust boundary gaps, and more. | After deployments are defined, or anytime you want a security audit. |
| **@validator** | Dual-pass validation: deterministic Python script for structural/referential checks, then LLM semantic review for business logic. Reports errors, warnings, and info. | Anytime. Run it after making changes to catch issues early. |
| **@pattern-manager** | Manages reusable network topology and product/service patterns. Save, load, swap, version, and browse patterns organized in hierarchy trees (by geography for networks, by capability for products). | When you want to reuse a standard network layout or product stack across systems. Pop-and-swap between configurations. |

#### Diagram Agents (Phased Pipeline)

The diagram system uses a **phased pipeline**: the orchestrator analyzes your architecture and builds a layout plan, then hands off to specialized renderers.

| Agent | What It Does | When to Use It |
|-------|-------------|----------------|
| **@diagram-generator** | Orchestrator: reads architecture YAML, assesses complexity, builds a structured `layout-plan.yaml` with grid positions and node/edge data. Dispatches to renderer agents. | After your architecture is modeled. Use anytime to visualize the current state. |
| **@diagram-mermaid** | Renderer: reads `layout-plan.yaml` and generates Mermaid `flowchart LR` diagrams with subgraph boundaries and C4 styling. | Called by `@diagram-generator`, or directly if you want Mermaid-only output. |
| **@diagram-plantuml** | Renderer: reads `layout-plan.yaml` and generates PlantUML C4 diagrams using the C4-PlantUML stdlib. Verified syntax for plantuml.com and VS Code extension. | Called by `@diagram-generator`, or directly for PlantUML-only output. |
| **@diagram-drawio** | Renderer: reads `layout-plan.yaml` and generates `.drawio` XML files with explicit x,y coordinates. Import into Lucidchart via File > Import > Draw.io. | Called by `@diagram-generator`, or directly for Lucidchart export. |

#### Documentation Agent

| Agent | What It Does | When to Use It |
|-------|-------------|----------------|
| **@doc-writer** | Generates architecture documentation from YAML: HLDD (High-Level Design Document), executive summaries, and stakeholder briefs. Output in Confluence storage format (`.confluence.html`) or Markdown. | After architecture is modeled. For stakeholder presentations, Confluence pages, or design reviews. |

### How Handoffs Work

Each agent has **handoff buttons** that appear in the Copilot Chat when appropriate. Every handoff includes a descriptive `prompt` explaining what the target agent will do. For example, after `@architect` finishes Layer 3 (Components), you'll see buttons like:

```
Architecture modeling is complete. You can now:
1. Deploy to network zones        → "Place containers and components into network zones"
2. Review security posture        → "Analyze the architecture for security vulnerabilities"
3. Generate diagrams              → "Generate architecture diagrams from the YAML model"
4. Generate documentation         → "Generate HLDD and stakeholder docs from the architecture"
5. Validate architecture          → "Validate architecture YAML for structural correctness"
```

Click a button or type the agent name directly (e.g., `@deployer place my containers`) to switch.

**Handoffs carry context.** When you switch from `@architect` to `@deployer`, the deployer reads your `system.yaml` and `networks.yaml` automatically — you don't need to re-explain anything.

**Diagram pipeline handoffs:** The `@diagram-generator` orchestrator hands off to renderers one at a time. Each renderer offers to hand off to the next renderer or back to the orchestrator:
```
@diagram-generator → builds layout-plan.yaml → @diagram-mermaid → @diagram-plantuml → @diagram-drawio
```

---

## Complete Step-by-Step Workflow

Below is the full end-to-end workflow, showing exactly what happens at each step, what questions you'll be asked, and what files get created.

---

### Phase 0: Document Collection & Extraction (@doc-collector / @doc-extractor)

**Skip this phase if you don't have existing documentation.** Go straight to Phase 1.

The document ingestion pipeline uses two agents: `@doc-collector` collects and converts your documents (PDF, DOCX, images → text), then hands off to `@doc-extractor` which extracts structured architecture entities with source citations. Every fact it extracts must be traceable to a specific document and section. You approve everything before it writes any YAML.

#### Starting the Session

**You type:**
```
@doc-collector Collect my architecture docs
```

**The agent responds with:**
1. A welcome message explaining the 5-step process
2. Asks how your documents are formatted (3 options)

#### Input Mode Selection

The agent offers three ways to provide documents:

| Option | What You Do | What the Agent Does | Requirements |
|--------|------------|-------------------|--------------|
| **1. Text files (Recommended)** | Convert docs to `.txt` or `.md` yourself, place in `context/` folder | Reads files directly with `read` tool | None — works everywhere |
| **2. Auto-convert** | Point to a folder with PDFs, Word docs, HTML | Detects tools on your machine, converts via `execute` | pandoc, pdftotext, or Python |
| **3. Paste directly** | Paste text or images into Copilot Chat | Saves pasted content, analyzes images via Vision | None |

> **For architecture diagram images:** In any mode, you can paste images directly into Copilot Chat. The agent uses GPT-4o Vision to identify system boundaries, components, relationships, and technology labels visible in the diagram — then presents its understanding for you to validate.

#### Step-by-Step Flow

**Step 1 — Document Collection**

The agent loads your documents (method depends on your chosen input mode) and presents a summary:
```
DOCUMENTS LOADED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Files read: 4
  ✓ architecture-overview.txt    → Read directly
  ✓ network-design.md            → Read directly
  ✓ api-specs.md                 → Read directly
  ✓ system-design.txt            → Read directly

Shall I proceed with analysis, or add more files?
```

**Step 2 — Document Inventory**

The agent reads each document and summarizes what architecture topics it detected:
```
DOCUMENT INVENTORY
1. architecture-overview.txt — System description, contexts, high-level components
2. network-design.md — Network zones, trust levels, firewall rules
3. api-specs.md — REST endpoints, protocols, authentication mechanisms
4. system-design.txt — Containers, component types, technology stack

Does this match your expectations? Any documents to focus on or ignore?
```

**Step 3 — Layer-by-Layer Extraction (the core)**

The agent extracts entities one layer at a time, presenting each with **confidence scores** and **source citations**:

```
EXTRACTED: System Metadata
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

| Field                 | Value                           | Confidence | Source                                 |
|-----------------------|---------------------------------|------------|----------------------------------------|
| name                  | Payment Processing Platform     | HIGH       | architecture-overview.txt, paragraph 1 |
| description           | Handles card payment processing | HIGH       | architecture-overview.txt, paragraph 1 |
| owner                 | NOT_STATED                      | —          | Not found in any document              |
| compliance_frameworks | PCI-DSS, SOC2                   | MEDIUM     | network-design.md, "Compliance" section|
| status                | NOT_STATED                      | —          | Not found in any document              |
```

**Confidence levels:**
| Level | Meaning | What Happens |
|-------|---------|-------------|
| **HIGH** | Exact match found in document | Presented as-is |
| **MEDIUM** | Stated but requires minor interpretation | Marked `[verify]` — please confirm |
| **LOW** | Weak implication, ambiguous wording | Warning shown — please confirm or correct |
| **UNCERTAIN** | Conflicting info across documents | Question shown — please clarify |
| **NOT_STATED** | Not found in any document | You must provide the value |

The agent extracts in this order:
1. **System Metadata** — name, description, owner, compliance, status
2. **Contexts** — internal/external systems
3. **Containers** — per internal context
4. **Components + Listeners** — per container
5. **Relationships** — context, container, component level
6. **Networks, External Systems, Data Entities, Trust Boundaries**

**You must approve each layer** before the agent proceeds to the next.

**Step 4 — Consolidated Review**

After all layers, the agent shows a complete summary with confidence breakdown:
```
EXTRACTION COMPLETE — SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Contexts: 3 | Containers: 5 | Components: 8 | Relationships: 12
Confidence: 28 HIGH | 9 MEDIUM | 3 LOW | 5 user-provided

Ready to write YAML? (1) Yes  (2) Review a layer  (3) Make changes
```

**Step 5 — Write YAML**

Only after your explicit approval. The agent writes `system.yaml` and `networks.yaml`, then offers to hand off to `@architect` for refinement or `@validator` for checking.

#### Optional Tools for Auto-Convert Mode

These tools improve the auto-convert experience but are **NOT required**:

| Tool | What It Converts | Install Command |
|------|-----------------|-----------------|
| **pandoc** | DOCX, HTML, many formats | `choco install pandoc` (Win) / `brew install pandoc` (Mac) / `apt install pandoc` (Linux) |
| **pdftotext** | PDF files | Part of `poppler-utils` package |
| **tesseract** | Images (OCR) | `choco install tesseract` (Win) / `brew install tesseract` (Mac) / `apt install tesseract-ocr` (Linux) |
| **Python 3** | PDF (via pdfplumber) | `pip install pdfplumber` |

If none are installed, the agent falls back to Option 1 (manual text) or Option 3 (paste).

---

### Phase 1: Architecture Modeling (@architect)

This is the main phase. The `@architect` agent walks you through **6 layers** in order. It will not skip ahead or let you jump layers (though you can say "skip" or "later" to defer optional items).

#### Starting the Session

**You type:**
```
@architect Model a payment processing platform
```

**The agent responds with:**
1. A brief greeting
2. Asks for your **system name** and **one-sentence description**
3. Explains the file structure it will create
4. Asks: "How would you like to start?"
   1. **Ingest from documents** — import existing architecture docs (hands off to `@doc-collector`/`@doc-extractor`)
   2. **Start fresh** — guided questions layer by layer
   3. **Load existing folder** — extend what's already been modeled

> **If option 1:** Hands off to `@doc-collector`/`@doc-extractor` with your system name.
>
> **If option 2 (start fresh):** The agent begins with Layer 1 below.
>
> **If option 3 (load existing):** The agent reads all existing YAML files, shows you what it found, and picks up where it left off.

---

#### Layer 1 — Contexts (The Big Picture)

**What contexts are:** The highest-level systems in your architecture. Each is either **internal** (you own it) or **external** (a third-party system you integrate with).

**Progress banner you'll see:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LAYER 1 of 6 — CONTEXTS              [=>        ]
Context: Payment Processing Platform
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Step 1.1 — System Metadata**

The agent asks for:
| Field | Required | Example | Notes |
|-------|----------|---------|-------|
| `name` | Yes | "Payment Processing Platform" | Human-readable name |
| `description` | Yes | "Handles card-present and card-not-present payment transactions" | One sentence |
| `owner` | Yes | "Platform Security Team" | Team or person responsible |
| `compliance_frameworks` | Optional | PCI-DSS, SOC2, GDPR | Array of framework names |
| `status` | Yes | active | One of: `proposed`, `active`, `deprecated`, `decommissioned` |

**Step 1.2 — Define Each Context**

The agent asks you to list all the systems involved. For each context:
| Field | Required | Example |
|-------|----------|---------|
| `name` | Yes | "Payment Platform" |
| `description` | Yes | "Core payment processing system" |
| `internal` | Yes | `true` for systems you own, `false` for external |

> **Naming:** If you say "API Gateway", the agent will suggest: *"I'll use `api-gateway` as the ID. OK?"* All IDs are kebab-case.

The agent captures **all contexts** before moving on. After each one, it shows the YAML it wrote:
```yaml
contexts:
  - id: payment-platform
    name: Payment Platform
    description: Core payment processing system
    internal: true
```

It asks: *"Any more contexts? Or shall we define relationships?"*

**Step 1.3 — Context Relationships**

For each relationship between contexts:
| Field | Required | Example |
|-------|----------|---------|
| Source context | Yes | (select from numbered list) |
| Target context | Yes | (select from numbered list) |
| `label` | Yes | "submits transactions to" |
| `bidirectional` | Yes | `false` (default) |

> **Context relationships are high-level only.** No protocol details, no ports, no listeners. Those come in Layer 3.

**Layer 1 Checkpoint:**
```
LAYER 1 COMPLETE
Captured: 3 contexts, 2 context relationships
Files written: architecture/payment-platform/system.yaml
Next: Layer 2 — Containers
```

The agent shows the full Layer 1 YAML and asks: *"Does this look correct? Any changes before we move on?"*

---

#### Layer 2 — Containers (Functional Tiers)

**What containers are:** Logical groupings of related components within an internal context. Think of them as functional tiers — NOT individual services. Examples: "API Tier", "Application Core", "Data Tier", "Message Bus".

**Progress banner you'll see:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LAYER 2 of 6 — CONTAINERS            [===>      ]
Context: Payment Platform
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Step 2.1 — Define Containers (per internal context)**

For each container:
| Field | Required | Example | Notes |
|-------|----------|---------|-------|
| `name` | Yes | "API Tier" | Human-readable |
| `description` | Yes | "Public-facing API gateway with rate limiting" | |
| `container_type` | Yes | `api_gateway` | Freeform but descriptive |
| `technology` | Yes | "Kong Gateway" | Primary technology/framework |
| `status` | Optional | `active` | Default: `active` |
| `external` | Optional | `false` | Default: `false` |

> **Important:** Containers do NOT have listeners directly. Listeners are defined at the component level (Layer 3) and automatically aggregated up to containers in diagrams.

**Step 2.2 — Container Relationships**

For each relationship:
| Field | Required | Example |
|-------|----------|---------|
| Source container | Yes | (numbered list) |
| Target container | Yes | (numbered list) |
| `label` | Yes | "routes requests to" |
| `synchronous` | Yes | `true` or `false` |
| `data_classification` | Optional | `confidential` |
| `trust_boundary_crossing` | Optional | `true` / `false` |

> **Note:** Listener targeting is deferred to Layer 3. The agent will revisit these relationships after components and listeners exist.

**Layer 2 Checkpoint:**
```
LAYER 2 COMPLETE
Captured: 3 containers, 2 container relationships
Files updated: architecture/payment-platform/system.yaml
Next: Layer 3 — Components
```

---

#### Layer 3 — Components (Individual Services)

**What components are:** The individual deployable services, applications, databases, or processes within a container. This is where you define listeners (ports, protocols, TLS, authentication).

**Progress banner you'll see:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LAYER 3 of 6 — COMPONENTS            [=====>    ]
Container: Application Core
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Step 3.1 — Define Components (per container)**

For each component:
| Field | Required | Example | Notes |
|-------|----------|---------|-------|
| `name` | Yes | "Payment API" | |
| `description` | Optional | "REST API for payment processing" | |
| `component_type` | Yes | `api` | Examples: `api`, `database`, `message_queue`, `web_app`, `background_service`, `cache` |
| `technology` | Yes | "Spring Boot 3.2" | |
| `platform` | Optional | "JVM 21" | Runtime platform |
| `resiliency` | Optional | "active-active" | HA pattern |

**Step 3.2 — Define Listeners (per component)**

Listeners define how other components connect to this one. For each listener:
| Field | Required | Example | Notes |
|-------|----------|---------|-------|
| `id` | Yes | "payment-api-https" | Unique within the component |
| `protocol` | Yes | "HTTPS" | |
| `port` | Yes | `8443` | Integer |
| `tls_enabled` | Yes | `true` | Boolean |
| `tls_version_min` | Conditional | "1.3" | Required if `tls_enabled: true` |
| `authn_mechanism` | Yes | "oauth2" | Examples: `oauth2`, `mtls`, `api_key`, `certificate`, `none` |
| `authz_required` | Yes | `true` | Default: `true` |

> **Why listeners matter:** Listeners are the foundation for security analysis, deployment link computation, and trust boundary validation. The security reviewer flags listeners with `tls_enabled: false` or `authn_mechanism: none`.

**Step 3.3 — Component Relationships**

This is where the detailed data flows are captured. For each relationship:

1. **Select source component** — the agent shows a numbered list of all components
2. **Select target component** — another numbered list
3. **Select target listener** — if the target has listeners, the agent displays them:
   ```
   Target component "Payment Database" has these listeners:
   1. payment-db-pg — PostgreSQL :5432 / TLS 1.2 / certificate auth
   Which listener does this connection use?
   ```
4. **Confirm listener spec** — the agent displays the full listener details as read-only:
   ```
   Derived from listener:
     protocol: PostgreSQL
     port: 5432
     tls_enabled: true
     tls_version_min: "1.2"
     authn_mechanism: certificate
     authz_required: true
   ```
5. **Capture remaining fields:**
   | Field | Required | Example |
   |-------|----------|---------|
   | `label` | Yes | "persists transactions" |
   | `synchronous` | Yes | `true` |
   | `data_entities` | Optional | `[transaction-record]` |
   | `data_classification` | Optional | `confidential` |

**Step 3.4 — Update Container Relationships**

Now that listeners exist, the agent revisits each container relationship from Layer 2 and resolves `target_listener_ref` automatically. It shows what it resolved and asks for confirmation.

**Layer 3 Checkpoint:**
```
LAYER 3 COMPLETE
Captured: 4 components, 6 listeners, 5 component relationships
Container relationships updated with listener refs
Files updated: architecture/payment-platform/system.yaml
Next: Layer 4 — Networks
```

---

#### Layer 4 — Networks (networks.yaml)

**What this defines:** Shared network zones and infrastructure resources that deployments will reference.

**Step 4.1 — Network Zones**

For each zone:
| Field | Required | Example | Notes |
|-------|----------|---------|-------|
| `name` | Yes | "DMZ" | |
| `zone_type` | Yes | `dmz` | Examples: `external`, `dmz`, `private`, `management` |
| `internet_routable` | Yes | `true` | Is it accessible from the internet? |
| `trust` | Yes | `semi_trusted` | One of: `trusted`, `semi_trusted`, `untrusted` |
| `description` | Optional | "Demilitarized zone for public-facing services" | |

**Step 4.2 — Infrastructure Resources**

For each resource (load balancers, WAFs, secret managers, etc.):
| Field | Required | Example |
|-------|----------|---------|
| `name` | Yes | "F5 Web Application Firewall" |
| `resource_type` | Yes | `waf` |
| `technology` | Yes | "F5 BIG-IP ASM" |
| `zone_id` | Yes | `dmz` (must reference a valid zone) |

**File written:** `architecture/networks.yaml`

---

#### Layer 5 — External Systems (system.yaml)

**Step 5.1 — External Systems**

For each third-party or external system:
| Field | Required | Example |
|-------|----------|---------|
| `name` | Yes | "Visa / Mastercard Network" |
| `description` | Yes | "Card network for payment authorization" |
| `category` | Yes | `partner` (examples: `partner`, `saas`, `internal_other_team`) |

**Step 5.2 — Data Entities (Optional)**

The agent asks: *"Do you want to define named data entities for flow annotation?"*

If yes, for each:
| Field | Required | Example |
|-------|----------|---------|
| `name` | Yes | "Transaction Record" |
| `description` | Yes | "Payment transaction with card details" |
| `classification` | Yes | `confidential` |

**Step 5.3 — Trust Boundaries (Optional)**

The agent asks: *"Do you want to define trust boundaries now or later?"*

If yes, for each:
| Field | Required | Example |
|-------|----------|---------|
| `name` | Yes | "Internet to DMZ" |
| `source_zone` | Yes | `internet` |
| `target_zone` | Yes | `dmz` |

---

#### Layer 6 — Review

The agent shows a complete summary of everything captured and offers handoff:

```
ARCHITECTURE MODELING COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
System: Payment Processing Platform
Contexts: 3 (2 internal, 1 external)
Containers: 5
Components: 8
Listeners: 12
Context Relationships: 4
Container Relationships: 6
Component Relationships: 10
Network Zones: 5
Infrastructure Resources: 3
External Systems: 2
Data Entities: 3
Trust Boundaries: 2

Files written:
  architecture/payment-platform/system.yaml
  architecture/networks.yaml

You can now:
1. Deploy to network zones        → @deployer
2. Review security posture        → @security-reviewer
3. Generate diagrams              → @diagram-generator
4. Validate architecture          → @validator
```

---

### Phase 2: Deployment Mapping (@deployer)

The `@deployer` agent places your containers and components into specific network zones for a given environment or location. A system can have many deployments (e.g., "Production US-East", "Staging EU", "DR Site Asia").

#### Starting the Session

**You type:**
```
@deployer Deploy payment-platform to production US-East
```

**The agent responds:**
1. Reads `system.yaml` and `networks.yaml` automatically
2. Shows a summary: *"Found 5 containers, 8 components, 5 network zones."*
3. Begins the guided sequence

#### Step-by-Step Deployment Flow

**Step 1 — Deployment Metadata**

The agent asks for:
| Field | Required | Example |
|-------|----------|---------|
| `name` | Yes | "Production US-East" |
| `description` | Yes | "Primary production deployment in US-East data center" |
| `status` | Yes | One of: `proposed`, `approved`, `active`, `deprecated` |

The agent auto-generates the deployment ID: `prod-us-east`

**Step 2 — Zone Placements**

For each network zone you want to use, the agent asks:
```
Which containers go in the DMZ zone?
1. api-tier — API Tier (Kong Gateway)
2. app-core — Application Core (Java / Spring Boot)
3. data-tier — Data Tier (PostgreSQL 15)
4. (none — skip this zone)
```

For each container placed in a zone, the agent asks:
```
Which components of "API Tier" are deployed here? (default: all)
1. api-gateway — API Gateway (Kong)
2. rate-limiter — Rate Limiter (Kong Plugin)
3. All components (default)
```

It shows a running summary after each placement:
```
Placed 2 of 5 containers into zones.
```

**Step 3 — Write Deployment YAML**

The agent writes the file and displays it:
```yaml
# architecture/payment-platform/deployments/prod-us-east.yaml
deployment:
  id: prod-us-east
  name: Production US-East
  description: Primary production deployment in US-East data center
  status: active
  zone_placements:
    - zone_id: dmz
      containers:
        - container_id: api-tier
          components:
            - component_id: api-gateway
              internal: true
            - component_id: rate-limiter
              internal: true
    - zone_id: private-app-tier
      containers:
        - container_id: app-core
          components:
            - component_id: payment-api
              internal: true
    - zone_id: private-data-tier
      containers:
        - container_id: data-tier
          components:
            - component_id: payment-db
              internal: true
```

Asks: *"Does this look correct?"*

**Step 4 — Derived Link Computation**

The agent automatically computes all network links based on your component relationships and deployment placements. For each link, it builds a technology string:

```
DERIVED LINKS for prod-us-east:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. api-gateway → payment-api
   HTTPS :8443 / TLS 1.3 / oauth2
   ⚠ warning: zone crossing (dmz → private-app-tier)
   ⚠ warning: trust boundary crossing (semi_trusted → trusted)

2. payment-api → payment-db
   PostgreSQL :5432 / TLS 1.2 / certificate
   ⚠ warning: zone crossing (private-app-tier → private-data-tier)
```

Warnings are automatically flagged for:
- **Zone crossing** — source and target are in different network zones
- **Internet boundary** — one zone is internet-routable, the other is not
- **Trust boundary crossing** — zones have different trust levels
- **No TLS** — `tls_enabled: false` on the target listener
- **No authentication** — `authn_mechanism: none` on the target listener

**Deployment Complete — Handoff Options:**
```
Deployment complete. You can now:
1. Back to architecture        → @architect
2. Generate diagrams           → @diagram-generator
3. Review security             → @security-reviewer
4. Validate                    → @validator
```

---

### Phase 3: Security Review (@security-reviewer)

The `@security-reviewer` reads all YAML files and produces a comprehensive security analysis. It does NOT make changes — it reports findings and offers to hand off to the appropriate agent for fixes.

#### Starting the Session

**You type:**
```
@security-reviewer Review payment-platform
```

**The agent responds:**
1. Reads all architecture files
2. Shows: *"Found: 1 system (payment-platform), 2 deployments, 5 network zones."*
3. Runs all security checks with progress:
   ```
   Running check 1 of 6 — Unauthenticated Listeners
   Running check 2 of 6 — Unencrypted Listeners
   Running check 3 of 6 — Internet-Exposed Listeners
   Running check 4 of 6 — Unconfirmed Trust Boundary Controls
   Running check 5 of 6 — External Sensitive Data Flows
   Running check 6 of 6 — Missing Authorization
   ```

#### Security Checks Performed

| Check | What It Finds | Severity |
|-------|--------------|----------|
| **Unauthenticated Listeners** | Components with `authn_mechanism: none` | HIGH if internet-facing, MEDIUM otherwise |
| **Unencrypted Listeners** | Components with `tls_enabled: false` | HIGH if crossing trust boundaries, MEDIUM otherwise |
| **Internet-Exposed Listeners** | Components in zones where `internet_routable: true` | INFO (flagged for awareness) |
| **Unconfirmed Trust Boundary Controls** | Trust boundaries with no associated controls | MEDIUM |
| **External Sensitive Data Flows** | Relationships to external systems carrying `confidential`+ data | HIGH |
| **Missing Authorization** | Listeners with `authz_required: false` | MEDIUM |

#### Output — Security Findings Report

The agent writes a markdown report to `architecture/<system>/diagrams/security-findings.md` and displays it:

```
SECURITY REVIEW COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Findings: 2 HIGH | 3 MEDIUM | 1 INFO
Report written to: architecture/payment-platform/diagrams/security-findings.md
```

Each finding includes:
- **What** — the issue
- **Where** — component, listener, container, context
- **Why it matters** — the risk
- **Recommended fix** — specific action to take

#### STRIDE Threat Analysis

After the basic security checks, the agent performs a per-relationship STRIDE analysis for every data flow crossing a trust boundary. Each relationship is evaluated for:

| STRIDE Category | What It Checks |
|---|---|
| **Spoofing** | Authentication mechanism strength (none, api_key, oauth2, mtls) |
| **Tampering** | Transport integrity (TLS enabled/disabled on sensitive data) |
| **Repudiation** | Audit trail presence (logging infrastructure in target zone) |
| **Information Disclosure** | Data exposure risk (TLS status, data classification) |
| **Denial of Service** | DoS protection (WAF presence for internet-facing listeners) |
| **Elevation of Privilege** | Authorization checks (authz_required on listeners) |

Output: `architecture/<system>/diagrams/stride-analysis.md` — a table with S/T/R/I/D/E columns per relationship.

#### Firewall ACL Generation

The agent auto-generates firewall rules from listener data:
- For flows with explicit protocol and port: `PERMIT TCP FROM zone/component TO zone/component PORT <port>`
- For flows missing protocol/port: `NEEDS_SPECIFICATION` (never guesses)

Output: `architecture/<system>/diagrams/firewall-acls.md`

#### Additional Security Commands

| Command | What It Does |
|---------|-------------|
| `Show blast radius for <container-id>` | Shows all affected systems, zones, and data flows if a container is compromised |
| `Show network crossings for <deployment-id>` | Generates a table of all zone crossings with protocol, TLS, and auth details |
| `Summarize risks` | Executive summary of highest-severity findings |
| `Generate firewall rules` / `Show ACLs` | Generates firewall ACL rules from listener data |

---

### Phase 4: Diagram Generation (@diagram-generator)

The diagram system uses a **phased pipeline** — the orchestrator analyzes your architecture, builds a structured layout plan, and then hands off to specialized renderer agents. This approach ensures any LLM model can execute the workflow without timeouts.

#### How the Pipeline Works

```
@diagram-generator (orchestrator)
    ↓ reads system.yaml + networks.yaml
    ↓ assesses complexity (simple/medium/complex)
    ↓ writes layout-plan.yaml (grid positions, nodes, edges, legend)
    ↓
    ├── @diagram-mermaid    → generates .md files (Mermaid flowchart LR)
    ├── @diagram-plantuml   → generates .puml files (PlantUML C4)
    └── @diagram-drawio     → generates .drawio files (import into Lucidchart)
```

The `layout-plan.yaml` is the intermediate artifact — it decouples analysis from rendering. All three renderers read the same plan, ensuring **consistent diagrams** across formats.

#### Starting the Session

**You type:**
```
@diagram-generator Generate all diagrams for payment-platform
```

**The agent responds:**
1. Reads `system.yaml` and `networks.yaml`
2. Shows: *"Found: 3 contexts, 5 containers, 8 components, 2 deployments."*
3. Assesses complexity: *"Complexity: medium (14 nodes, 18 relationships)"*
4. Presents menus:
   ```
   Which diagrams would you like to generate?
   1. Context (Level 1)
   2. Container (Level 2)
   3. Component (Level 3)
   4. Deployment — specify which deployment
   5. All diagrams

   Which formats?
   1. All formats (Mermaid + PlantUML + Lucidchart)
   2. Mermaid only (.md)
   3. PlantUML only (.puml)
   4. Lucidchart only (.drawio)
   ```
5. Builds `layout-plan.yaml` and hands off to the first renderer

#### Diagram Levels Explained

| Level | What It Shows | Audience |
|-------|--------------|----------|
| **C4 Context (Level 1)** | High-level system boundaries and external actors. Internal systems as single boxes, external systems outside the boundary. | Executives, stakeholders, architects |
| **C4 Container (Level 2)** | Internal context boundaries with container nodes (API Tier, Data Tier, etc.). Shows container-to-container relationships. | Architects, tech leads |
| **C4 Component (Level 3)** | Individual components within container boundaries. Shows listeners, protocols, data flows. | Developers, security engineers |
| **C4 Deployment (Level 4)** | Network zones with containers/components placed inside. Color-coded by trust level. Shows derived network links with warnings. | Network engineers, security, operations |

#### Three Output Formats Per Diagram

| Format | File Extension | Use Case | Renderer Agent |
|--------|---------------|----------|----------------|
| **Mermaid** | `.md` | Preview in VS Code Markdown preview, GitHub rendering, Obsidian | `@diagram-mermaid` |
| **PlantUML C4** | `.puml` | VS Code PlantUML extension preview, plantuml.com, Confluence | `@diagram-plantuml` |
| **Draw.io / Lucidchart** | `.drawio` | Import into Lucidchart (File > Import > Draw.io), draw.io desktop app, Confluence draw.io plugin | `@diagram-drawio` |

All three formats use the **same C4 color scheme** and produce **visually consistent** diagrams — when viewed side by side, they look nearly identical but rendered in different tools.

#### Color Scheme

| Element | Fill Color | Use |
|---------|-----------|-----|
| Internal components/containers | Blue (`#1565c0`) | Systems you own |
| External systems/actors | Gray (`#999999`) | Third-party systems |
| Infrastructure | Orange (`#ff8f00`) | WAFs, load balancers, etc. |
| Trusted zones | Green border (`#2e7d32`) | Private/internal networks |
| Semi-trusted zones | Yellow border (`#f9a825`) | DMZ, semi-exposed |
| Untrusted zones | Red border (`#c62828`) | Internet-facing |

#### The Layout Plan (Intermediate Artifact)

The orchestrator writes `layout-plan.yaml` before any rendering begins. This file contains:
- **Grid positions** for every node (column = left-to-right flow, row = vertical grouping)
- **Node metadata** — type, label, technology, description, boundary membership
- **Edge data** — source, target, label, protocol, sync/async
- **Legend entries** — element types and flow types present in the diagram
- **Complexity assessment** — determines renderer preamble (spacing, layout engine)

You can inspect `layout-plan.yaml` to understand exactly what will be rendered.

#### Output

Each renderer writes files and shows progress:
```
✓ Phase 1 — Layout plan              [layout-plan.yaml written]
✓ Phase 2 — Mermaid rendering        [4 files written]
► Phase 3 — PlantUML rendering       [handing off to @diagram-plantuml]
  Phase 4 — Lucidchart rendering

Files per level:
  architecture/payment-platform/diagrams/payment-platform-context.md
  architecture/payment-platform/diagrams/payment-platform-context.puml
  architecture/payment-platform/diagrams/payment-platform-context.drawio

DIAGRAM GENERATION COMPLETE
Files written: 12 (+ layout-plan.yaml)
Location: architecture/payment-platform/diagrams/
```

#### Confidence-Colored Diagrams

When `provenance.yaml` exists (generated by `@doc-collector`/`@doc-extractor`), diagrams are automatically color-coded by extraction confidence:

| Color | Meaning |
|-------|---------|
| Blue (`#1565c0`) | HIGH confidence — well-supported by source documents |
| Amber (`#ff8f00`) | MEDIUM confidence — needs verification |
| Red (`#c62828`) | LOW confidence — weak support in sources |
| Green (`#2e7d32`) | User-provided — human-confirmed value |
| Grey (`#9e9e9e`) | UNRESOLVED — requires review before finalizing |

A legend is included in every confidence-colored diagram.

#### Security Overlay Diagrams

Request security-focused diagrams with: `@diagram-generator Generate security overlay`

These overlay encryption status (green/red edges), trust boundary crossings, unauthenticated listener markers, data classification labels, and STRIDE risk badges on components.

#### Persona-Specific Views

| View | Command | What It Shows |
|------|---------|--------------|
| Executive | `Generate executive view` | Context diagram only, compliance frameworks, no protocol detail |
| Architect | `Generate architect view` | Container diagram with technology labels and data classifications |
| Security Engineer | `Generate security view` | Full DFD with STRIDE annotations, auth/authz on every flow |
| Network Engineer | `Generate network view` | Deployment zones, protocol/port on every edge, firewall ACL annotations |
| Compliance Officer | `Generate compliance view` | Data classification map, trust boundary controls, compliance coverage |

> **Tip:** Open any `.md` file in VS Code and use the built-in Markdown Preview (`Ctrl+Shift+V`) to see Mermaid diagrams rendered live.

---

### Phase 5: Validation (@validator)

The `@validator` uses a **dual-pass approach** for maximum accuracy. It reports errors but does NOT fix them — it hands off to the appropriate agent.

#### Starting the Session

**You type:**
```
@validator Validate payment-platform
```

**The agent responds:**
1. Reads all architecture files
2. **Pass 1 — Deterministic validation** (Python script `tools/validate.py`):
   - Runs reproducible structural and referential integrity checks
   - Same input always produces the same result — no LLM variability
   - If Python is unavailable, this pass is skipped with a warning
3. **Pass 2 — Semantic validation** (LLM review):
   - Checks business logic that code cannot catch
   - Are security controls proportionate to data classifications?
   - Are there obvious missing components for compliance frameworks?
   - Are trust boundaries placed logically?
4. Results from both passes are presented separately

#### What Gets Validated

**Structural — Required Fields:**
- Every entity type has required fields (name, id, description, etc.)
- Missing required fields are flagged as `[ERROR]`
- Status fields must be valid enum values

**Referential Integrity:**
| What | Must Reference | Severity |
|------|---------------|----------|
| Container's `context_id` | A valid context | ERROR |
| Component's `container_id` | A valid container | ERROR |
| Relationship `source_context` / `target_context` | Valid contexts | ERROR |
| Relationship `source_container` / `target_container` | Valid containers | ERROR |
| Relationship `source_component` / `target_component` | Valid components | ERROR |
| Relationship `target_listener_ref` | A listener on the target component | ERROR |
| Deployment `zone_id` | A zone in `networks.yaml` | ERROR |
| Deployment `container_id` | A container in `system.yaml` | ERROR |
| Deployment `component_id` | A component in that container | ERROR |

**Naming Conventions:**
- All `id` fields must be kebab-case: `^[a-z][a-z0-9]*(-[a-z0-9]+)*$`
- IDs must be unique within their collection
- Non-kebab-case IDs flagged as `[WARNING]`
- Duplicate IDs flagged as `[ERROR]`

**Relationship Consistency:**
- Component relationships targeting a component with listeners MUST specify `target_listener_ref` → `[ERROR]`
- Container relationships SHOULD have `target_listener_ref` if listeners exist → `[WARNING]`
- Duplicate bidirectional context relationships → `[WARNING]`

**Deployment Consistency:**
- Every container in a deployment must exist in `system.yaml` → `[ERROR]`
- Every component must belong to its specified container → `[ERROR]`
- Every zone must exist in `networks.yaml` → `[ERROR]`

#### Output — Validation Report

```
=== VALIDATION REPORT ===
System: Payment Processing Platform
Timestamp: 2026-03-30T14:22:00Z
Files checked: 4

ERRORS (1):
  [ERROR] system.yaml:component_relationships[3] — target_listener_ref
          "cache-redis" references non-existent listener on component "redis-cache"

WARNINGS (2):
  [WARNING] system.yaml:containers[2].id — "DataTier" is not kebab-case
            (should be "data-tier")
  [WARNING] system.yaml:container_relationships[1] — missing target_listener_ref
            (target container "app-core" has components with listeners)

INFO (1):
  [INFO] 2 deployment files validated successfully

SUMMARY: 1 error, 2 warnings, 1 info
Status: FAIL
```

The agent then offers:
```
Would you like to fix these? I can hand off to:
  • @architect for system.yaml issues
  • @deployer for deployment issues
```

---

### Phase 6: Documentation Generation (@doc-writer)

The `@doc-writer` agent generates architecture documentation from your YAML model files. It reads the same `system.yaml`, `networks.yaml`, and deployment files used by all other agents.

#### Starting the Session

**You type:**
```
@doc-writer Generate HLDD for payment-platform
```

**The agent responds:**
1. Reads all architecture files
2. Shows: *"Loaded: Payment Processing Platform — 3 contexts, 5 containers, 8 components, 2 deployments"*
3. Asks which document type and format:
   ```
   What documentation would you like to generate?
   1. HLDD — Full High-Level Design Document
   2. Executive Summary — Non-technical overview
   3. Stakeholder Brief — Targeted summary for a specific audience

   Output format?
   1. Confluence (storage format — paste into Confluence editor or upload via API)
   2. Markdown (for GitHub, wikis, or general use)
   3. Both
   ```

#### Document Types

**HLDD (High-Level Design Document)** — Comprehensive 12-section technical architecture document:

| Section | Content Source |
|---------|--------------|
| Title & Metadata | system.yaml metadata, status badges |
| Table of Contents | Auto-generated (Confluence TOC macro or Markdown links) |
| Executive Summary | metadata.description + contexts overview |
| System Context | contexts + context_relationships |
| Container Architecture | containers + container_relationships with expand/collapse |
| Component Design | components + component_relationships per container |
| Data Flow | relationships with data_classification, warnings for sensitive flows |
| Deployment Architecture | deployments + networks.yaml, zone placements, TLS status |
| Security Considerations | compliance frameworks, trust boundaries, auth mechanisms |
| Technology Stack | Deduplicated from all technology fields |
| Assumptions & Constraints | From provenance gaps or manual modeling notes |
| Appendix: Glossary | Auto-generated from entity names and descriptions |

**Executive Summary** — Max 2 pages, non-technical language, business value and risk focus.

**Stakeholder Brief** — Tailored to a specific audience:
- **Engineering leads**: Container architecture, tech stack, integration points
- **Security team**: Trust boundaries, auth mechanisms, data classification
- **Operations**: Deployment topology, infrastructure, monitoring
- **Product/Business**: Context diagram narrative, capabilities, integrations

#### Output Formats

**Confluence Storage Format** (`.confluence.html`):
- Uses Confluence XHTML with `ac:structured-macro` elements
- Includes: TOC macro, info/warning/note panels, status badges, expand/collapse sections, styled tables, code blocks
- Paste directly into the Confluence editor or upload via REST API
- Works on both Confluence Cloud and Data Center

**Markdown** (`.md`):
- GitHub-flavored Markdown with callouts (`> [!NOTE]`, `> [!WARNING]`)
- Suitable for GitHub wikis, Obsidian, or any Markdown renderer

#### Format Preferences

You can customize the output by telling the agent:
- *"Use expand macros for components"* — wrap details in collapsible sections
- *"Flat structure"* — no expand/collapse, all content visible
- *"Compact"* — shorter descriptions, more bullet points
- *"Detailed"* — full descriptions, all tables, YAML excerpts
- *"Include diagrams inline"* — add diagram embed references

#### Confidence Annotations

When `provenance.yaml` exists (from `@doc-collector`/`@doc-extractor`), the documentation includes confidence annotations:
- HIGH confidence — no annotation
- MEDIUM confidence — *(needs verification)* in italic
- LOW confidence — warning panel: "verify with source documents"
- UNRESOLVED — warning panel: "could not be confirmed from source documents"

#### Output Files

```
architecture/<system-id>/docs/
├── <system-id>-hldd.confluence.html          ← Confluence HLDD
├── <system-id>-hldd.md                       ← Markdown HLDD
├── <system-id>-executive-summary.confluence.html
├── <system-id>-executive-summary.md
├── <system-id>-stakeholder-brief.confluence.html
└── <system-id>-stakeholder-brief.md
```

#### On-Demand Commands

| Command | What It Does |
|---------|-------------|
| `Generate HLDD` | Full High-Level Design Document |
| `Generate executive summary` | Non-technical overview |
| `Generate stakeholder brief for [audience]` | Tailored brief (engineering, security, ops, product) |
| `Generate all docs` | HLDD + executive summary |
| `Regenerate` | Re-read YAML and regenerate |
| `Switch to Confluence format` | Change output to Confluence storage format |
| `Switch to Markdown` | Change output to Markdown |

---

## File Structure Explained

After a full workflow, your project will look like this:

```
architecture/
├── networks.yaml                                    ← Shared: all network zones + infra resources
│
└── payment-platform/                                ← One folder per system
    ├── system.yaml                                  ← The complete system model
    │   ├── metadata                                 ← Name, owner, compliance
    │   ├── contexts[]                               ← High-level systems (Layer 1)
    │   ├── context_relationships[]                  ← Context-to-context flows
    │   ├── containers[]                             ← Functional tiers (Layer 2)
    │   ├── container_relationships[]                ← Container-to-container flows
    │   ├── components[]                             ← Individual services (Layer 3)
    │   │   └── listeners[]                          ← Ports, protocols, TLS, auth
    │   ├── component_relationships[]                ← Service-to-service flows + listener refs
    │   ├── external_systems[]                       ← Third-party integrations
    │   ├── data_entities[]                          ← Named data types for flow annotation
    │   └── trust_boundaries[]                       ← Zone boundary definitions
    │
    ├── provenance.yaml                              ← Per-field source citations + confidence scores
    │
    ├── deployments/
    │   ├── prod-us-east.yaml                        ← Production US-East placement
    │   ├── staging-eu.yaml                          ← Staging EU placement
    │   └── dr-asia.yaml                             ← Disaster recovery Asia
    │
    ├── docs/                                        ← Generated documentation
    │   ├── payment-platform-hldd.confluence.html    ← HLDD (Confluence format)
    │   ├── payment-platform-hldd.md                 ← HLDD (Markdown)
    │   ├── payment-platform-executive-summary.confluence.html
    │   ├── payment-platform-executive-summary.md
    │   ├── payment-platform-stakeholder-brief.confluence.html
    │   └── payment-platform-stakeholder-brief.md
    │
    └── diagrams/
        ├── layout-plan.yaml                         ← Intermediate layout plan (orchestrator output)
        ├── payment-platform-context.md              ← Mermaid Context
        ├── payment-platform-context.puml            ← PlantUML Context
        ├── payment-platform-context.drawio          ← Draw.io/Lucidchart Context
        ├── payment-platform-container.md            ← Mermaid Container
        ├── payment-platform-container.puml          ← PlantUML Container
        ├── payment-platform-container.drawio        ← Draw.io/Lucidchart Container
        ├── payment-platform-component.md            ← Mermaid Component
        ├── payment-platform-component.puml          ← PlantUML Component
        ├── payment-platform-component.drawio        ← Draw.io/Lucidchart Component
        ├── prod-us-east-deployment.md               ← Deployment (Mermaid)
        ├── prod-us-east-deployment.puml             ← Deployment (PlantUML)
        ├── prod-us-east-deployment.drawio           ← Deployment (Draw.io)
        ├── prod-us-east-network-crossings.md        ← Network crossing report
        ├── security-findings.md                     ← Security analysis report
        ├── stride-analysis.md                       ← STRIDE threat analysis per relationship
        ├── firewall-acls.md                         ← Auto-generated firewall ACL rules
        ├── blast-radius-*.md                        ← Blast radius analysis per container
        ├── payment-platform-security-overlay.md     ← Security overlay (Mermaid)
        ├── payment-platform-security-overlay.puml   ← Security overlay (PlantUML)
        └── payment-platform-security-overlay.drawio ← Security overlay (Draw.io)

patterns/                                                ← Reusable architecture templates
├── networks/
│   ├── _catalog.yaml                                ← Network pattern catalog (by geography)
│   └── usa/
│       ├── standard-3tier.pattern.yaml              ← Legacy single-file format (deprecated)
│       └── standard-3tier/                          ← New directory format
│           ├── pattern.meta.yaml                    ← Metadata + composition contract
│           ├── networks.yaml                        ← Standalone (conforms to networks.schema.json)
│           ├── contexts/                            ← Per-pattern context hierarchy
│           │   ├── _context.yaml                    ← C4 Level 1 context definitions
│           │   ├── sources/                         ← Source documents for this pattern
│           │   │   └── doc-inventory.yaml           ← Inventory of collected documents
│           │   └── provenance.yaml                  ← Entity → source evidence mapping
│           └── diagrams/                            ← Pattern reference diagrams
│               └── _index.yaml                      ← Diagram catalog for this pattern
└── products/
    ├── _catalog.yaml                                ← Product pattern catalog (by capability)
    └── messaging/
        ├── ibm-mq.pattern.yaml                      ← Legacy single-file format (deprecated)
        └── ibm-mq/                                  ← New directory format
            ├── pattern.meta.yaml                    ← Metadata + composition contract
            ├── system.yaml                          ← Standalone (conforms to system.schema.json)
            ├── contexts/                            ← Per-pattern context hierarchy
            │   ├── _context.yaml                    ← C4 Level 1 context definitions
            │   ├── sources/                         ← Source documents for this product
            │   │   └── doc-inventory.yaml           ← Inventory of collected documents
            │   └── provenance.yaml                  ← Entity → source evidence mapping
            └── diagrams/                            ← Pattern reference diagrams
                └── _index.yaml                      ← Diagram catalog for this pattern

deployments/                                             ← Manifest-based deployment compositions
├── _catalog.yaml                                    ← Catalog of deployment compositions
└── <deployment-id>/
    ├── manifest.yaml                                ← Declares: 1 network + N products + placements
    ├── networks.yaml                                ← GENERATED by compose.py (read-only)
    ├── system.yaml                                  ← GENERATED by compose.py (read-only)
    ├── deployment.yaml                              ← GENERATED by compose.py (read-only)
    └── diagrams/                                    ← Deployment-scoped diagrams
        ├── _index.yaml                              ← Diagram catalog for this deployment
        ├── layout-plan.yaml                         ← Intermediate orchestration plan
        ├── <deployment-id>-context.md               ← Mermaid context diagram
        ├── <deployment-id>-containers.md            ← Mermaid container diagram
        ├── <deployment-id>-deployment.md            ← Mermaid deployment diagram
        ├── <deployment-id>-context.puml             ← PlantUML context diagram
        ├── <deployment-id>.dsl                      ← Structurizr DSL (all levels)
        └── custom/                                  ← Hand-crafted diagrams (never overwritten)

tools/
├── validate.py                                      ← Deterministic validation script
├── validate-patterns.py                             ← Pattern validation (legacy + directory format)
├── compose.py                                       ← Compose deployment from manifest + patterns
├── migrate-pattern.py                               ← Migrate legacy .pattern.yaml to directory format
├── classify-sections.py                             ← Classify document sections (network vs product)
├── detect-tools.py                                  ← Cross-platform tool detection
└── requirements.txt                                 ← Python dependencies (pyyaml)

schemas/
├── system.schema.json                               ← system.yaml validation
├── networks.schema.json                             ← networks.yaml validation
├── deployment.schema.json                           ← deployment YAML validation
├── provenance.schema.json                           ← provenance.yaml validation
├── pattern-meta.schema.json                         ← pattern.meta.yaml validation
├── manifest.schema.json                             ← manifest.yaml validation
├── context.schema.json                              ← pattern _context.yaml validation
└── doc-inventory.schema.json                        ← pattern doc-inventory.yaml validation

schemas/
├── system.schema.json                               ← System YAML schema
├── networks.schema.json                             ← Networks YAML schema
├── deployment.schema.json                           ← Deployment YAML schema
├── provenance.schema.json                           ← Provenance YAML schema
├── pattern-meta.schema.json                         ← Pattern metadata schema
├── manifest.schema.json                             ← Deployment manifest schema
├── context.schema.json                              ← Pattern _context.yaml schema
├── doc-inventory.schema.json                        ← Pattern doc-inventory.yaml schema
└── diagram-index.schema.json                        ← Diagram _index.yaml catalog schema
```

---

## YAML Schema Reference

### system.yaml — Complete Structure

```yaml
metadata:
  name: string (required)
  description: string (required)
  owner: string (required)
  status: proposed | active | deprecated | decommissioned (required)
  compliance_frameworks: [string] (optional)

contexts:
  - id: kebab-case (required, unique)
    name: string (required)
    description: string (required)
    internal: boolean (required)
    external_system_id: string (conditional — if internal: false)

context_relationships:
  - id: kebab-case (required)
    source_context: context id (required)
    target_context: context id (required)
    label: string (required)
    bidirectional: boolean (default: false)

containers:
  - id: kebab-case (required, unique)
    name: string (required)
    context_id: context id (required)
    container_type: string (required)
    technology: string (required)
    description: string (optional)
    status: proposed | active | deprecated | decommissioned (default: active)
    external: boolean (default: false)

container_relationships:
  - id: kebab-case (required)
    source_container: container id (required)
    target_container: container id (required)
    label: string (required)
    synchronous: boolean (required)
    target_listener_ref: listener id (resolved in Layer 3)
    data_entities: [string] (optional)
    data_classification: string (optional)

components:
  - id: kebab-case (required, unique)
    name: string (required)
    container_id: container id (required)
    component_type: string (required)
    technology: string (required)
    platform: string (optional)
    resiliency: string (optional)
    listeners:
      - id: string (required, unique within component)
        protocol: string (required)
        port: integer (required)
        tls_enabled: boolean (required)
        tls_version_min: string (conditional — if tls_enabled: true)
        authn_mechanism: string (required)
        authz_required: boolean (required, default: true)

component_relationships:
  - id: kebab-case (required)
    source_component: component id (required)
    target_component: component id (required)
    target_listener_ref: listener id (required if target has listeners)
    label: string (required)
    synchronous: boolean (required)
    data_entities: [string] (optional)
    data_classification: string (optional)

external_systems:
  - id: kebab-case (required)
    name: string (required)
    description: string (required)
    category: string (required)

data_entities:
  - id: kebab-case (required)
    name: string (required)
    description: string (required)
    classification: string (required)

trust_boundaries:
  - id: kebab-case (required)
    name: string (required)
    description: string (optional)
    source_zone: zone id (required)
    target_zone: zone id (required)
```

### networks.yaml — Complete Structure

```yaml
network_zones:
  - id: kebab-case (required, unique)
    name: string (required)
    zone_type: string (required)
    internet_routable: boolean (required)
    trust: trusted | semi_trusted | untrusted (required)
    description: string (optional)

infrastructure_resources:
  - id: kebab-case (required)
    name: string (required)
    resource_type: string (required)
    technology: string (required)
    zone_id: zone id (required)
```

### Deployment YAML — Complete Structure

```yaml
deployment:
  id: kebab-case (required)
  name: string (required)
  description: string (optional)
  status: proposed | approved | active | deprecated (required)
  zone_placements:
    - zone_id: zone id from networks.yaml (required)
      containers:
        - container_id: container id from system.yaml (required)
          components:
            - component_id: component id (required)
              internal: boolean (default: true)
```

### pattern.meta.yaml — Pattern Metadata

```yaml
pattern:
  id: kebab-case (required)
  type: product | network (required)
  name: string (required)
  category: string (required)
  version: X.Y.Z (required, semver)
  description: string (required)
  tags: [string] (optional)

  provides:                                # What this pattern offers
    - capability: string (required)
      containers: [string] (product only)
      zones: [string] (network only)

  requires:                                # What this pattern needs
    - capability: string (required)

  binding_points:                          # IDs consumers map during composition
    - id: string (required)
      type: container | component | zone | infrastructure_resource (required)
      bind_to: string (optional, parent entity)
      description: string (optional)

  version_tracking_enabled: boolean (optional)
  version_history:
    - version: string (required)
      date: date (required)
      author: string (optional)
      description: string (optional)
```

### manifest.yaml — Deployment Manifest

```yaml
manifest:
  id: kebab-case (required)
  name: string (required)
  description: string (optional)
  environment: development | staging | production | dr (required)
  region: string (optional)
  status: proposed | approved | active | deprecated (optional)

  network:                                 # Exactly one network pattern
    pattern_ref: string (required)         # Pattern ID
    version: string (optional)             # Pinned version
    id_prefix: kebab-case (required)       # Prefix for all network IDs
    overrides: {entity_id: {fields}} (optional)

  products:                                # One or more product patterns
    - pattern_ref: string (required)
      version: string (optional)
      id_prefix: kebab-case (required)     # Must be unique per product
      context_name: string (optional)      # Override context display name
      overrides: {entity_id: {fields}} (optional)

  placements:                              # Zone placements (prefixed IDs)
    - container_ref: string (required)
      zone_ref: string (required)
      replicas: integer (optional)
      runtime_user: root | non_root | unknown (optional)

  cross_product_relationships:             # Connections between products
    - id: string (required)
      source_component: string (required)  # Prefixed ID
      target_component: string (required)  # Prefixed ID
      target_listener_ref: string (optional)
      label: string (optional)
      synchronous: boolean (optional)
```

---

## Pattern-Based Deployments

The pattern system enables **platform teams** to maintain reusable architecture templates that **application teams** consume through deployment manifests. This is an alternative to the bespoke modeling workflow described in earlier phases.

### How It Works

1. **Platform teams** create and maintain pattern directories:
   - Network patterns (`patterns/networks/`) — standalone `networks.yaml` files defining topologies
   - Product patterns (`patterns/products/`) — standalone `system.yaml` files defining services
   - Each pattern has a `contexts/` subdirectory with C4 context definitions, source documents, and provenance

2. **Document collection** feeds patterns:
   - `@doc-collector` prompts for pattern type (network, product, or mixed)
   - Mixed documents are classified by section using `tools/classify-sections.py`
   - Sections are routed to the correct pattern's `contexts/sources/`
   - `@doc-extractor` extracts entities and writes provenance per pattern

3. **Application teams** compose deployments by selecting patterns:
   - Create a `manifest.yaml` referencing 1 network + N products
   - Each pattern gets a unique `id_prefix` to prevent ID conflicts
   - The manifest also defines zone placements and cross-product relationships

4. **Composition** generates the combined output:
   ```bash
   python tools/compose.py deployments/prod-us-east/manifest.yaml --validate
   ```
   This merges contexts from all patterns and produces `networks.yaml`, `system.yaml`, and `deployment.yaml` — all validated and ready for security review and diagram generation.

### Per-Pattern Context Hierarchy

Each pattern directory contains a `contexts/` subdirectory:

```
patterns/products/messaging/ibm-mq/
├── pattern.meta.yaml         # Metadata + composition contract
├── system.yaml               # Containers, components, listeners
└── contexts/                 # Self-contained context hierarchy
    ├── _context.yaml         # C4 Level 1 context definitions
    ├── sources/              # Source documents for this product
    │   ├── doc-inventory.yaml
    │   ├── mq-deployment-guide.md
    │   └── mq-network-flows.md    # Product's network needs (OK!)
    └── provenance.yaml       # Entity → source evidence mapping
```

**Context separation rule:**
- **Network patterns** → contexts about topology, segmentation, infrastructure
- **Product patterns** → contexts about product functionality and deployment
- A product's own network requirements (ports, TLS) belong in the **product pattern**

### Document Classification for Mixed Content

When a vendor document covers both network and product content:

```bash
# Preview how sections will be classified
python tools/classify-sections.py vendor-guide.md --dry-run

# Split and write classified sections to a pattern's sources
python tools/classify-sections.py vendor-guide.md --output-dir patterns/products/messaging/ibm-mq/contexts/sources/
```

Classification uses keyword signals (firewall/VLAN → network, queue/component → product) with title-weighted scoring and confidence thresholds.

### Example Workflow

```
@pattern-manager List network patterns
  → User selects "standard-3tier" (DMZ + App Tier + Data Tier)

@pattern-manager List product patterns
  → User selects "ibm-mq" and "hashicorp-vault"

@pattern-manager Create deployment
  → User provides: name, environment, id_prefix per pattern
  → User maps containers to zones
  → manifest.yaml written
  → compose.py generates composed output

@validator Validate deployment
@security-reviewer Review deployment
@diagram-generator Generate diagrams
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Each pattern is a **directory** (not a single file) | Enables standalone validation with existing tools |
| Product patterns conform to **full system.schema.json** | No subset schemas to maintain; existing tools work unchanged |
| ID conflicts prevented by **mandatory unique prefix** per pattern | Simpler than complex merge/resolution logic |
| Manifest is **declarative** (what to compose, not how) | Same manifest always produces same output |
| Generated files have **"DO NOT EDIT" header** | Forces changes through manifest or source patterns |
| Legacy `.pattern.yaml` format **still works** | Gradual migration; deprecation warnings guide users |
| **Per-pattern `contexts/`** with source docs + provenance | Each pattern is a self-contained, portable, shareable unit |
| **Product network info stays in product pattern** | Product's port/TLS needs ≠ network topology — no confusion |
| **Section-level document classification** | Mixed vendor docs auto-split to correct pattern hierarchy |

### Validating Patterns

```bash
# Validate a new-format pattern directory
python tools/validate-patterns.py patterns/products/messaging/ibm-mq/

# Validate a legacy single-file pattern
python tools/validate-patterns.py patterns/networks/usa/standard-3tier.pattern.yaml

# Validate all patterns in a category
python tools/validate-patterns.py patterns/networks/

# Dry-run composition to check for errors without writing files
python tools/compose.py deployments/prod-us-east/manifest.yaml --validate --dry-run
```

### Migrating Legacy Patterns

Convert existing `.pattern.yaml` files to the new directory format:

```bash
python tools/migrate-pattern.py patterns/products/messaging/ibm-mq.pattern.yaml
```

This creates `patterns/products/messaging/ibm-mq/` with:
- `pattern.meta.yaml` — metadata, composition contract, binding points
- `system.yaml` — full system.schema.json-conformant architecture
- `contexts/_context.yaml` — auto-generated C4 context definitions
- `contexts/sources/doc-inventory.yaml` — empty document inventory (ready for collection)
- `contexts/provenance.yaml` — empty provenance (ready for extraction)

---

## Commands You Can Use Anytime

These commands can be typed in any agent's chat session. The agent will either handle it directly or hand off to the appropriate specialist.

| Command | What Happens | Handled By |
|---------|-------------|------------|
| `Show YAML` | Displays all current YAML files | Current agent |
| `Validate` | Runs full structural validation | @validator |
| `Validate <system-id>` | Validates only that system | @validator |
| `Check references` | Runs only referential integrity checks | @validator |
| `Check naming` | Runs only naming convention checks | @validator |
| `Generate diagrams` | Generates all C4 diagrams | @diagram-generator |
| `Generate context diagram` | Generates only Level 1 | @diagram-generator |
| `Generate deployment diagrams for <id>` | Generates deployment diagrams | @diagram-generator |
| `Generate security overlay` | Security-focused diagrams with encryption colors and STRIDE badges | @diagram-generator |
| `Generate executive view` | Context-only diagram for executives | @diagram-generator |
| `Generate security view` | Full DFD with STRIDE annotations | @diagram-generator |
| `Generate network view` | Zone-focused diagram with protocol/port detail | @diagram-generator |
| `Regenerate` | Re-reads YAML and regenerates all diagrams | @diagram-generator |
| `Generate HLDD` | Full High-Level Design Document | @doc-writer |
| `Generate executive summary` | Non-technical overview | @doc-writer |
| `Generate stakeholder brief for <audience>` | Tailored brief (engineering, security, ops, product) | @doc-writer |
| `Generate all docs` | HLDD + executive summary | @doc-writer |
| `Show security findings` | Runs full security analysis | @security-reviewer |
| `Show blast radius for <container-id>` | Impact analysis for a container | @security-reviewer |
| `Show network crossings for <deployment-id>` | Zone crossing report | @security-reviewer |
| `Summarize risks` | Executive summary of top findings | @security-reviewer |
| `Show derived links` | Network links for current deployment | @deployer |
| `Add another deployment` | Start a new deployment for same system | @deployer |
| `List network patterns` | Browse network pattern catalog by geography | @pattern-manager |
| `List product patterns` | Browse product pattern catalog by capability | @pattern-manager |
| `Load pattern <id>` | Apply a saved pattern to architecture files | @pattern-manager |
| `Save as pattern` | Extract current config into a reusable pattern | @pattern-manager |
| `Swap network` / `Swap product` | Pop-and-swap a loaded pattern for another | @pattern-manager |
| `Create deployment` | Compose network + products into a deployment manifest | @pattern-manager |
| `Compose deployment <id>` | Run compose.py on an existing manifest | @pattern-manager |
| `Classify document <file>` | Classify document sections as network/product/security | @doc-collector |
| `Collect for pattern <path>` | Collect documents into a pattern's contexts/sources/ | @doc-collector |

---

## Tips and Best Practices

### Getting the Best Results

1. **Start with `@architect`** — Always begin here. The other agents depend on `system.yaml` and `networks.yaml` existing.

2. **Be specific with names** — Instead of "database", say "PostgreSQL 15 primary-replica cluster for transaction data". The agent records exactly what you say.

3. **Don't worry about IDs** — The agent auto-generates kebab-case IDs from your names. If you say "API Gateway", it suggests `api-gateway`.

4. **Take your time with listeners** — Listeners are the most important detail. They drive security analysis, deployment link computation, and diagram annotations. Get the protocol, port, TLS, and auth right.

5. **Use "skip" or "later"** — If you don't know something yet, say "skip" or "later". The agent marks it as incomplete and you can return to it.

6. **Review YAML after each layer** — The agent shows you the YAML after each layer. Read it carefully — it's much easier to fix now than after 3 more layers.

7. **Run `@validator` often** — Validation is fast and catches issues early. Run it after every major change.

### Common Workflows

**New system from existing docs (recommended):**
```
@doc-collector → @validator → @architect → @deployer → @security-reviewer → @diagram-generator → @doc-writer
```

**New system from scratch (no docs):**
```
@architect → @deployer → @security-reviewer → @diagram-generator → @doc-writer → @validator
```

**Add a deployment to an existing system:**
```
@deployer Deploy payment-platform to staging EU
```

**Security audit after changes:**
```
@security-reviewer Review payment-platform
```

**Regenerate diagrams after YAML edits:**
```
@diagram-generator Regenerate
```

**Export diagrams for Lucidchart:**
```
@diagram-drawio Generate all Draw.io diagrams
```
Then import the `.drawio` files into Lucidchart via File > Import > Draw.io.

**Generate Confluence documentation:**
```
@doc-writer Generate HLDD in Confluence format
```

**Quick validation check:**
```
@validator Validate all
```

**Compose a deployment from patterns:**
```
@pattern-manager Create deployment
```
The agent walks you through selecting a network pattern, product patterns, assigning zone placements, and running `compose.py`.

**Validate a pattern:**
```
@validator Validate patterns/products/messaging/ibm-mq/
```

**Migrate a legacy pattern to directory format:**
```
python tools/migrate-pattern.py patterns/products/messaging/ibm-mq.pattern.yaml
```

### Working with Multiple Systems

Each system gets its own subfolder under `architecture/`. The `networks.yaml` file is shared across all systems. You can model multiple systems by running `@architect` multiple times with different system names.

---

## Zero-Hallucination Pipeline

When using `@doc-collector`/`@doc-extractor` to extract architecture from existing documents, the system enforces a **zero-hallucination invariant**:

> For every element E in the output YAML, there exists a source reference S in the input documents where E is a direct extraction (not inference) from S, and S is verifiable by human review.

The output is a faithful, verifiable **subset** of what the source documents state. It may be incomplete (because the docs are incomplete), but it is never wrong about what it does include.

### How It Works

The pipeline uses a 5-stage approach:

1. **Multi-Pass Extraction** — Each document is processed in separate focused passes: prose (narrative text), tables (structured data), diagrams (Vision analysis), then cross-reference (consistency check across passes and documents).

2. **Chunked Extraction** — Each document section is processed independently to prevent context cross-contamination. Entities from one section never leak into another section's extraction.

3. **Self-Verification** — After extraction, the agent re-reads each cited source passage and asks: "Does this source explicitly state what I extracted?" If it can't produce a direct quote, confidence is downgraded from HIGH to MEDIUM.

4. **Cross-Document Consistency** — When the same entity appears in multiple documents with different values, both values are presented side-by-side for the user to resolve. The agent never silently picks one value over another.

5. **Provenance Tracking** — Every extracted field is traced to its source document, section, extraction pass, and supporting quote in `provenance.yaml`. This enables full traceability and human verification.

### Confidence Scoring

Each field's confidence is the minimum of four factors:

| Factor | HIGH | MEDIUM | LOW | UNCERTAIN |
|--------|------|--------|-----|-----------|
| Source clarity | Exact match | Requires interpretation | Ambiguous | Conflicting |
| Extraction method | Direct text/table | — | OCR/Vision | — |
| Cross-document | Confirmed in 2+ docs | Single source | — | Contradicted |
| Self-verification | Re-confirmed with quote | Could not re-confirm | — | — |

Confidence determines routing: HIGH elements auto-present, MEDIUM elements get `[verify]` tags, LOW elements get warnings, UNCERTAIN elements block until the user resolves them, and NOT_STATED elements require the user to provide the value.

### Provenance File

After extraction, `@doc-collector`/`@doc-extractor` writes `architecture/<system-id>/provenance.yaml` containing:
- Per-field source citations with document, section, and extraction pass
- Supporting quotes from source documents
- Conflict resolution history
- Unresolved items with impact analysis and suggested questions
- Extraction statistics (total fields, confidence breakdown)

---

## Deterministic Validation

The `@validator` agent uses a **separation principle**: extraction is done by the LLM, but validation is done by deterministic code. This ensures the same input always produces the same validation result.

### Python Validation Script

```bash
python tools/validate.py architecture/<system-id>/system.yaml
```

The script auto-detects `networks.yaml` in the parent directory. Output is JSON:

```json
{
  "valid": true,
  "errors": [],
  "warnings": ["component 'redis-cache' has no relationships (orphaned)"]
}
```

**What it checks:**
- Required fields for all entity types (metadata, contexts, containers, components, listeners, zones)
- Unique ID enforcement per entity type
- Referential integrity (context_id, container_id, target_listener_ref, zone_id)
- Kebab-case naming convention
- Security posture warnings (unauthenticated listeners, missing TLS)
- Orphaned components (no relationships)

**Dependencies:** Python 3 + PyYAML (`pip install pyyaml`). Install from `tools/requirements.txt`.

If Python is unavailable, the validator falls back to LLM-only validation with a warning.

---

## STRIDE Threat Analysis

The `@security-reviewer` performs automated STRIDE threat analysis on every data flow crossing a trust boundary. This is deterministic — based on schema fields, not AI inference.

### DFD Element Mapping

Architecture entities are mapped to Data Flow Diagram (DFD) elements for STRIDE applicability:

| DFD Element | Schema Mapping | STRIDE Applicability |
|---|---|---|
| External Entity | `external_systems[]` | Spoofing |
| Process | `components` (type: api, service, web_app) | All six categories |
| Data Store | `components` (type: database, cache, queue) | Tampering, Repudiation, Info Disclosure, DoS |
| Data Flow | `component_relationships[]` | Tampering, Info Disclosure, DoS |
| Trust Boundary | `trust_boundaries[]` + network zone crossings | All categories at crossings |

### Output

The STRIDE report is a per-relationship table:

```
| Relationship        | S | T | R | I | D | E | Risk Level |
|---------------------|---|---|---|---|---|---|------------|
| user → api-gateway  | ✓ | ✓ | ⚠ | ✓ | ⚠ | ✓ | MEDIUM     |
| api-gw → auth-svc   | ✓ | ✗ | ⚠ | ✗ | ✗ | ⚠ | HIGH       |
```

Written to: `architecture/<system>/diagrams/stride-analysis.md`

---

## Persona-Specific Diagram Views

The `@diagram-generator` can render filtered views of the same architecture YAML tailored to different audiences. No re-extraction or re-modeling needed — just different rendering rules.

| Persona | Focus | Detail Level |
|---------|-------|-------------|
| **Executive** | Business relationships, compliance frameworks | Context (Level 1) only, no protocol detail |
| **Architect** | Technology stack, data classifications, trust boundaries | Container (Level 2) with tech labels |
| **Security Engineer** | STRIDE annotations, auth/authz, data classification | Full component DFD with threat badges |
| **Network Engineer** | Zones, protocols, ports, firewall rules | Deployment with raw specs, ACL annotations |
| **Compliance Officer** | Data classification map, boundary controls, framework coverage | Container with compliance overlay |

Each view generates up to 3 files (Mermaid, PlantUML, Draw.io) depending on which formats you request.

---

## How This Compares

| Tool | Approach | Key Difference |
|------|----------|---------------|
| **STRIDE GPT** | Chat-based threat modeling | Single-pass, no schema validation, no provenance tracking |
| **Threagile** | YAML-in, risk-out | Requires manual YAML authoring; Doc2ArchAgent extracts it from documents |
| **Visual Paradigm AI** | AI-generated diagrams | No zero-hallucination controls, no source traceability |
| **pytm** | Python code defines threats | Code-first (not document-first), no multi-pass extraction |
| **Doc2ArchAgent** | Document → validated C4 model → diagrams + docs + STRIDE + ACLs | Full pipeline: extraction with provenance, deterministic validation, multi-format rendering (Mermaid, PlantUML, Lucidchart), Confluence-ready documentation |

Doc2ArchAgent's key differentiator is the **zero-hallucination pipeline**: every element is traceable to a source document, validated by deterministic code, and rendered with confidence indicators. The output is a verifiable subset, never a plausible guess. The multi-format output (Mermaid, PlantUML, Lucidchart, Confluence, Markdown) ensures integration with any toolchain.

---

## Known Limitations

| Limitation | Mitigation |
|-----------|------------|
| OCR errors on poor-quality scanned PDFs | Confidence capped at MEDIUM for all OCR-derived text; user prompted to paste pages as images |
| Ambiguous terms ("server" = physical or virtual?) | Marked as ambiguous with resolution options presented to user |
| Implicit architecture (components everyone knows exist but nobody documented) | Flagged: "commonly expected component not found in docs" — never silently added |
| Cross-document contradictions | Conflict handler presents both values side-by-side; blocks until user resolves |
| Overlapping elements in diagram images | Multi-stage Vision analysis + human verification step |
| Handwritten whiteboard photos | All confidence set to LOW; aggressive human routing for every extraction |
| Non-English documents | Vision analysis may have reduced accuracy; noted in provenance |
| Large document sets (100+ pages) | Chunked processing per section with cross-chunk resolution pass |
| Tracked changes in DOCX files | Agent asks whether to include tracked changes (may contain migration context) |
| Embedded Visio diagrams in DOCX | Extracted via pandoc; user prompted to paste as images if extraction fails |

---

## Troubleshooting

| Issue | Solution |
|-------|---------|
| Agents don't appear in Copilot Chat dropdown | Ensure `.github/agents/` is at the workspace root. Reload VS Code (`Ctrl+Shift+P` → "Reload Window"). |
| Agent says "No architecture files found" | Run `@architect` first to create `system.yaml` and `networks.yaml`. |
| `@doc-collector`/`@doc-extractor` can't convert PDF/DOCX | Install pandoc (`choco install pandoc`) or switch to Option 1 (manual text conversion). |
| `@doc-collector`/`@doc-extractor` says "pdftotext not found" | Install poppler-utils, or copy-paste the PDF content into chat (Option 3). |
| Image in docs folder not readable | Paste the image directly into Copilot Chat. The agent uses GPT-4o Vision to analyze it. |
| Extraction shows LOW confidence for many fields | Your documents may be ambiguous. Review the cited sources and provide corrections at each layer. |
| `@doc-collector`/`@doc-extractor` extracted something wrong | Say the field number to correct it, or "reject" to remove the extraction entirely. |
| Validation shows "non-existent context" errors | A container references a `context_id` that doesn't exist. Check your contexts list. |
| Diagrams have empty Deployment_Nodes | Known Mermaid limitation. The agent adds comments explaining the omission. |
| PlantUML shows `Syntax Error?` | Most common cause: hyphens in aliases. The PlantUML agent converts kebab-case to snake_case automatically. If editing manually, use only alphanumeric + underscore in aliases. |
| PlantUML `!include` fails | Ensure you use `!include <C4/C4_Container>` with the `C4/` prefix. Without it, the stdlib can't find the files. |
| PlantUML renders `//` as italic | Escape forward slashes in URLs/protocols: use `~/~/` instead of `//`. |
| Lucidchart import looks wrong | Ensure you import `.drawio` files via File > Import > Draw.io (not drag-and-drop). Elements use simple shapes, not C4 stencils. |
| Confluence HTML doesn't render | The `.confluence.html` files use Confluence storage format (XHTML + `ac:` macros). Paste into the Confluence editor's source view, or upload via REST API. |
| Agent skips a question | Required fields are never skipped. If something was skipped, it was optional. Say "go back" to revisit. |
| YAML looks wrong after editing manually | Run `@validator` to check for structural issues. Hand off to `@architect` to fix. |
| Want to change something from Layer 1 while in Layer 3 | Tell the agent: "Go back and change context X". It will re-display, accept changes, and re-write. |

---

## Templates

The `templates/` folder contains fully annotated example files you can reference:

- **`templates/system.yaml.example`** — Complete system model with metadata, contexts, containers, components, listeners, relationships, external systems, data entities, and trust boundaries.

- **`templates/networks.yaml.example`** — Network zones (internet, DMZ, private-app-tier, private-data-tier, management) and infrastructure resources (WAF, Vault, ELK Stack).

These are reference files only. The agents generate your actual YAML in the `architecture/` folder.

---

## License

Copyright (c) 2026 Michael J. Read. All rights reserved.

This project is licensed under the [Business Source License 1.1](LICENSE) (BSL 1.1).

| Use Case | Permitted? |
|----------|------------|
| Personal / non-commercial use | Yes |
| Academic / research / educational use | Yes |
| Evaluation and testing (non-production) | Yes |
| Internal use within your organization | Yes |
| Offering as a product or service to third parties | Requires [commercial license](LICENSE-COMMERCIAL.md) |
| Building a competing product or service | Requires [commercial license](LICENSE-COMMERCIAL.md) |

On **April 1, 2030**, the current version converts to the [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0).

For commercial licensing inquiries, see [LICENSE-COMMERCIAL.md](LICENSE-COMMERCIAL.md).

## Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) before submitting a pull request. All contributions require agreement to the Contributor License Agreement (CLA).
