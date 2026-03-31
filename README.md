# Doc2ArchAgent

A multi-agent architecture modeling system for VS Code, powered by GitHub Copilot custom agents. Walk through a structured, conversational workflow to transform your software architecture knowledge into well-formed C4 model YAML, deployment maps, security analyses, and auto-generated diagrams — all without leaving your editor.

---

## Table of Contents

- [What This Does](#what-this-does)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [How It Works — The Agent System](#how-it-works--the-agent-system)
- [Complete Step-by-Step Workflow](#complete-step-by-step-workflow)
  - [Phase 0: Document Ingestion (@doc-ingester)](#phase-0-document-ingestion-doc-ingester)
  - [Phase 1: Architecture Modeling (@architect)](#phase-1-architecture-modeling-architect)
  - [Phase 2: Deployment Mapping (@deployer)](#phase-2-deployment-mapping-deployer)
  - [Phase 3: Security Review (@security-reviewer)](#phase-3-security-review-security-reviewer)
  - [Phase 4: Diagram Generation (@diagram-generator)](#phase-4-diagram-generation-diagram-generator)
  - [Phase 5: Validation (@validator)](#phase-5-validation-validator)
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

---

## What This Does

Doc2ArchAgent turns your architecture knowledge into a structured, validated C4 model through a guided conversation. Instead of manually writing YAML or drawing diagrams, you answer questions and the agents build everything for you.

**The end result:**
- A complete `system.yaml` describing your contexts, containers, components, listeners, and relationships
- A `networks.yaml` defining your network zones and infrastructure resources
- Deployment YAML files mapping containers/components to specific network zones per environment
- A `provenance.yaml` tracing every extracted field back to its source document, section, and quote
- C4 diagrams at every level (Context, Container, Component, Deployment) in Mermaid and PlantUML
- Confidence-colored diagrams showing which elements are well-supported vs. need verification
- Persona-specific diagram views (Executive, Architect, Security, Network, Compliance)
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
git clone https://github.com/Michael-JRead/Arch2DocAgent.git
cd Arch2DocAgent
```

### Step 2: Open in VS Code
```bash
code .
```

### Step 3: Verify Agents are Detected
1. Open Copilot Chat: press `Ctrl+Shift+I` (Windows/Linux) or `Cmd+Shift+I` (Mac)
2. Click the **agents dropdown** (the `@` icon or type `@`)
3. You should see all 5 agents listed:
   - `@architect`
   - `@deployer`
   - `@security-reviewer`
   - `@diagram-generator`
   - `@validator`

If you don't see them, ensure:
- The `.github/agents/` folder is at the root of your workspace
- GitHub Copilot Chat is updated to the latest version
- You have an active Copilot subscription

### Step 4: Start Modeling
Select `@architect` from the dropdown and type your system description. That's it.

---

## How It Works — The Agent System

The system is composed of **5 specialized agents**, each owning a specific concern. They communicate through **handoffs** — when one agent finishes its work, it offers to hand off to the next logical agent.

### Agent Overview

| Agent | What It Does | When to Use It |
|-------|-------------|----------------|
| **@doc-ingester** | Ingests existing architecture documents (PDF, Word, text, images), extracts entities with source citations, validates with you, then writes YAML. Zero hallucinations. | **Start here if you have existing docs.** Import documentation before manual modeling. |
| **@architect** | Walks you through defining contexts, containers, components, listeners, and relationships. Writes `system.yaml` and `networks.yaml` incrementally. | **Start here if starting fresh.** Or continue after `@doc-ingester` to refine. |
| **@deployer** | Places your containers and components into network zones for specific environments (production, staging, regional deployments). Writes deployment YAML files. | After `@architect` completes your system model, or when you need to add a new deployment. |
| **@security-reviewer** | Reads all YAML and produces security findings, STRIDE threat analysis per data flow, and firewall ACL rules. Checks for unauthenticated listeners, unencrypted flows, trust boundary gaps, and more. | After deployments are defined, or anytime you want a security audit. |
| **@diagram-generator** | Generates C4 architecture diagrams in 3 formats: Mermaid C4, PlantUML C4, and Mermaid graph/subgraph. Covers all 4 C4 levels. Supports confidence color-coding, security overlays, and persona-specific views. | After your architecture is modeled. Use anytime to visualize the current state. |
| **@validator** | Dual-pass validation: deterministic Python script for structural/referential checks, then LLM semantic review for business logic. Reports errors, warnings, and info. | Anytime. Run it after making changes to catch issues early. |

### How Handoffs Work

Each agent has **handoff buttons** that appear in the chat when appropriate. For example, after `@architect` finishes Layer 3 (Components), you'll see buttons like:

```
Architecture modeling is complete. You can now:
1. Deploy to network zones        → hands off to @deployer
2. Review security posture        → hands off to @security-reviewer
3. Generate diagrams              → hands off to @diagram-generator
4. Validate architecture          → hands off to @validator
```

Click a button or type the agent name directly (e.g., `@deployer place my containers`) to switch.

**Handoffs carry context.** When you switch from `@architect` to `@deployer`, the deployer reads your `system.yaml` and `networks.yaml` automatically — you don't need to re-explain anything.

---

## Complete Step-by-Step Workflow

Below is the full end-to-end workflow, showing exactly what happens at each step, what questions you'll be asked, and what files get created.

---

### Phase 0: Document Ingestion (@doc-ingester)

**Skip this phase if you don't have existing documentation.** Go straight to Phase 1.

The `@doc-ingester` agent reads your existing architecture documents and extracts structured entities with source citations. Every fact it extracts must be traceable to a specific document and section. You approve everything before it writes any YAML.

#### Starting the Session

**You type:**
```
@doc-ingester Ingest my architecture docs
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
   1. **Ingest from documents** — import existing architecture docs (hands off to `@doc-ingester`)
   2. **Start fresh** — guided questions layer by layer
   3. **Load existing folder** — extend what's already been modeled

> **If option 1:** Hands off to `@doc-ingester` with your system name.
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

The `@diagram-generator` generates C4 architecture diagrams from your YAML files. It produces **3 file formats** for each diagram level.

#### Starting the Session

**You type:**
```
@diagram-generator Generate all diagrams for payment-platform
```

**The agent responds:**
1. Reads `system.yaml` and `networks.yaml`
2. Shows: *"Found: 3 contexts, 5 containers, 8 components, 2 deployments."*
3. Presents a menu:
   ```
   Which diagrams would you like to generate?
   1. Context (Level 1)
   2. Container (Level 2)
   3. Component (Level 3)
   4. Deployment — specify which deployment
   5. All diagrams
   ```

#### Diagram Levels Explained

| Level | What It Shows | Audience |
|-------|--------------|----------|
| **C4 Context (Level 1)** | High-level system boundaries and external actors. Internal systems as single boxes, external systems outside the boundary. | Executives, stakeholders, architects |
| **C4 Container (Level 2)** | Internal context boundaries with container nodes (API Tier, Data Tier, etc.). Shows container-to-container relationships. | Architects, tech leads |
| **C4 Component (Level 3)** | Individual components within container boundaries. Shows listeners, protocols, data flows. | Developers, security engineers |
| **C4 Deployment (Level 4)** | Network zones with containers/components placed inside. Color-coded by trust level. Shows derived network links with warnings. | Network engineers, security, operations |

#### Three Output Formats Per Diagram

| Format | File Extension | Use Case |
|--------|---------------|----------|
| **Mermaid C4** | `.md` | Preview in VS Code Markdown preview, GitHub rendering |
| **PlantUML C4** | `.puml` | Enterprise tooling, Confluence, detailed styling |
| **Mermaid Graph/Subgraph** | `-graph.md` | Better layout control, subgraph boundaries, custom styling |

#### Color Scheme

| Element | Fill Color | Use |
|---------|-----------|-----|
| Internal components/containers | Blue (`#1565c0`) | Systems you own |
| External systems/actors | Gray (`#999999`) | Third-party systems |
| Infrastructure | Orange (`#ff8f00`) | WAFs, load balancers, etc. |
| Trusted zones | Green border (`#2e7d32`) | Private/internal networks |
| Semi-trusted zones | Yellow border (`#f9a825`) | DMZ, semi-exposed |
| Untrusted zones | Red border (`#c62828`) | Internet-facing |

#### Output

The agent writes files and confirms:
```
Written 3 files:
  architecture/payment-platform/diagrams/payment-platform-context.md
  architecture/payment-platform/diagrams/payment-platform-context.puml
  architecture/payment-platform/diagrams/payment-platform-context-graph.md

Generating diagram 2 of 4 — Container Level
Writing 3 files: .md, .puml, -graph.md
...

DIAGRAM GENERATION COMPLETE
Files written: 12
Location: architecture/payment-platform/diagrams/
```

#### Confidence-Colored Diagrams

When `provenance.yaml` exists (generated by `@doc-ingester`), diagrams are automatically color-coded by extraction confidence:

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
    └── diagrams/
        ├── payment-platform-context.md              ← Mermaid C4 Context
        ├── payment-platform-context.puml            ← PlantUML C4 Context
        ├── payment-platform-context-graph.md        ← Mermaid graph Context
        ├── payment-platform-container.md            ← Mermaid C4 Container
        ├── payment-platform-container.puml          ← PlantUML C4 Container
        ├── payment-platform-container-graph.md      ← Mermaid graph Container
        ├── payment-platform-component.md            ← Mermaid C4 Component
        ├── payment-platform-component.puml          ← PlantUML C4 Component
        ├── payment-platform-component-graph.md      ← Mermaid graph Component
        ├── prod-us-east-deployment-container.md     ← Deployment (container level)
        ├── prod-us-east-deployment-container.puml
        ├── prod-us-east-deployment-component.md     ← Deployment (component level)
        ├── prod-us-east-deployment-component.puml
        ├── prod-us-east-deployment-graph.md         ← Mermaid graph Deployment
        ├── prod-us-east-network-crossings.md        ← Network crossing report
        ├── security-findings.md                     ← Security analysis report
        ├── stride-analysis.md                       ← STRIDE threat analysis per relationship
        ├── firewall-acls.md                         ← Auto-generated firewall ACL rules
        ├── blast-radius-*.md                        ← Blast radius analysis per container
        ├── payment-platform-security-overlay.md     ← Security overlay diagram (Mermaid C4)
        ├── payment-platform-security-overlay.puml   ← Security overlay diagram (PlantUML)
        ├── payment-platform-security-overlay-graph.md ← Security overlay (Mermaid graph)
        ├── payment-platform-executive.md            ← Executive persona view
        ├── payment-platform-architect.md            ← Architect persona view
        ├── payment-platform-security.md             ← Security engineer persona view
        ├── payment-platform-network.md              ← Network engineer persona view
        └── payment-platform-compliance.md           ← Compliance officer persona view

tools/
├── validate.py                                      ← Deterministic validation script
└── requirements.txt                                 ← Python dependencies (pyyaml)
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
| `Show security findings` | Runs full security analysis | @security-reviewer |
| `Show blast radius for <container-id>` | Impact analysis for a container | @security-reviewer |
| `Show network crossings for <deployment-id>` | Zone crossing report | @security-reviewer |
| `Summarize risks` | Executive summary of top findings | @security-reviewer |
| `Show derived links` | Network links for current deployment | @deployer |
| `Add another deployment` | Start a new deployment for same system | @deployer |

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
@doc-ingester → @validator → @architect → @deployer → @diagram-generator → @security-reviewer
```

**New system from scratch (no docs):**
```
@architect → @deployer → @security-reviewer → @diagram-generator → @validator
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

**Quick validation check:**
```
@validator Validate all
```

### Working with Multiple Systems

Each system gets its own subfolder under `architecture/`. The `networks.yaml` file is shared across all systems. You can model multiple systems by running `@architect` multiple times with different system names.

---

## Zero-Hallucination Pipeline

When using `@doc-ingester` to extract architecture from existing documents, the system enforces a **zero-hallucination invariant**:

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

After extraction, `@doc-ingester` writes `architecture/<system-id>/provenance.yaml` containing:
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

Each view generates 3 files (Mermaid C4, PlantUML C4, Mermaid graph).

---

## How This Compares

| Tool | Approach | Key Difference |
|------|----------|---------------|
| **STRIDE GPT** | Chat-based threat modeling | Single-pass, no schema validation, no provenance tracking |
| **Threagile** | YAML-in, risk-out | Requires manual YAML authoring; Doc2ArchAgent extracts it from documents |
| **Visual Paradigm AI** | AI-generated diagrams | No zero-hallucination controls, no source traceability |
| **pytm** | Python code defines threats | Code-first (not document-first), no multi-pass extraction |
| **Doc2ArchAgent** | Document → validated C4 model → diagrams + STRIDE + ACLs | Full pipeline: extraction with provenance, deterministic validation, multi-persona rendering |

Doc2ArchAgent's key differentiator is the **zero-hallucination pipeline**: every element is traceable to a source document, validated by deterministic code, and rendered with confidence indicators. The output is a verifiable subset, never a plausible guess.

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
| `@doc-ingester` can't convert PDF/DOCX | Install pandoc (`choco install pandoc`) or switch to Option 1 (manual text conversion). |
| `@doc-ingester` says "pdftotext not found" | Install poppler-utils, or copy-paste the PDF content into chat (Option 3). |
| Image in docs folder not readable | Paste the image directly into Copilot Chat. The agent uses GPT-4o Vision to analyze it. |
| Extraction shows LOW confidence for many fields | Your documents may be ambiguous. Review the cited sources and provide corrections at each layer. |
| `@doc-ingester` extracted something wrong | Say the field number to correct it, or "reject" to remove the extraction entirely. |
| Validation shows "non-existent context" errors | A container references a `context_id` that doesn't exist. Check your contexts list. |
| Diagrams have empty Deployment_Nodes | Known Mermaid limitation. The agent adds comments explaining the omission. |
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

MIT
