# Doc2ArchAgent

<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->

> Architecture extraction from documentation — powered by 16 specialized agents.

## Quick Start

Read `.github/copilot-instructions.md` for the full project context, agent hierarchy, and conventions.

## Core Invariant

**Zero-Hallucination**: Every architecture entity MUST have a verifiable source citation in `provenance.yaml`. If the source document does not state it, it does not exist in the model.

## Build & Test

```bash
python -m pytest tests/ -v                                    # Run all tests
python tools/validate.py architecture/*/system.yaml --format table  # Validate YAML
python tools/threat-rules.py architecture/*/system.yaml       # Run STRIDE analysis
python tools/compose.py deployments/<id>/manifest.yaml --validate   # Compose deployment
```

## Agent Workflow

```
@doc-collector → @doc-extractor → @architect → @security-reviewer → @deployer → @diagram-generator → @doc-writer
                                       ↑
                                  @orchestrator (pipeline coordination)
```

## Skills (Auto-Triggered)

Before acting on any task, check if a skill applies. Skills live in `.github/skills/` and are loaded on demand.

**Process skills** (check FIRST — these determine HOW to approach work):
- **brainstorming** — Design-first workflow; no implementation before design approval
- **writing-plans** — Break work into bite-sized tasks with exact steps
- **systematic-debugging** — Root-cause-first debugging methodology

**Execution skills** (use AFTER process skills):
- **executing-plans** — Load and execute a written plan with review checkpoints
- **subagent-driven-development** — Fresh agent per task with two-stage review
- **test-driven-development** — Red-Green-Refactor cycle; no code without failing test

**Quality skills** (use during and after implementation):
- **verification-before-completion** — Evidence-based completion; never claim done without proof
- **requesting-code-review** — Structured review dispatch
- **receiving-code-review** — Technical evaluation, not performative agreement
- **finishing-a-development-branch** — Verify → Present options → Execute → Clean up

**Utility skills**:
- **git-worktrees** — Isolated workspace creation with safety verification
- **parallel-agent-dispatching** — One agent per independent problem domain

**Domain skills** (architecture-specific):
- c4-modeling, security-analysis, deployment-mapping, documentation-generation, handoff-protocol, validate-yaml, threat-analysis, confidence-scoring, diagram-workflow, yaml-schema-guide, document-ingestion, pattern-composition

## Anti-Rationalization Check

If you catch yourself thinking any of these, STOP — you are rationalizing:

| Thought | Reality |
|---------|---------|
| "This is just a simple change" | Simple changes break things. Check skills. |
| "I know the architecture" | Read the YAML. Trust the source, not memory. |
| "I'll skip validation this once" | Self-validation is mandatory. Always. |
| "The tests probably pass" | Run them. "Probably" is not evidence. |
| "I'll add tests later" | No production code without a failing test first. |
| "Let me just quickly fix this" | Systematic debugging first. Quick fixes hide root causes. |

## Instincts (Always Active)

Behavioral rules in `instincts/` apply to ALL agents at ALL times:
zero-hallucination, yaml-hygiene, progress-reporting, handoff-protocol, user-confirmation, error-surfacing, scope-enforcement, provenance-awareness, session-memory

## Rules

Standards in `rules/` define structural constraints:
- `rules/common/` — YAML formatting, naming, file organization, git workflow, security, testing
- `rules/yaml/` — Schema-specific rules for system/networks/deployment YAML
- `rules/diagrams/` — Mermaid, PlantUML, Draw.io conventions

## Do NOT Touch

- `schemas/` — JSON Schema source of truth
- `context/*.yaml` — Curated threat intelligence and compliance mappings
- Generated files marked `GENERATED`
- `diagrams/custom/` — Hand-crafted diagrams
- License files
