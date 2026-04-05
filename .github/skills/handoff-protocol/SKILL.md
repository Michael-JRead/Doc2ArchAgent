---
name: handoff-protocol
description: Standardized format for transferring work between agents with context preservation and validation
allowed-tools: ['read']
---

# Handoff Protocol Skill

Defines the standardized format and process for transferring work between Doc2ArchAgent agents.

## When to Use
- Any agent completing its work and offering next steps
- `@orchestrator` coordinating the pipeline
- Any multi-agent workflow

## Handoff Checklist

Before handing off, every agent MUST:

1. **Validate output** — Run `python tools/validate.py` on modified YAML
2. **Summarize state** — What files exist, what was completed
3. **Specify task** — Exact instructions for the target agent
4. **List file paths** — All files the target agent should read
5. **Include security overlays** — `system-security.yaml`, `networks-security.yaml`, `deployment-security.yaml` where applicable
6. **Note unresolved items** — `NOT_STATED` fields, user questions pending

## Handoff Format

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HANDOFF → @<target-agent>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Task: <what the target agent should do>
Files to read:
  - architecture/<system-id>/system.yaml
  - architecture/networks.yaml
Completed: <what was just finished>
Unresolved: <any pending items>
```

## Agent Routing

| Current Agent | Typical Next Agents |
|---------------|-------------------|
| @architect | @deployer, @security-reviewer, @diagram-generator, @validator |
| @doc-collector | @doc-extractor |
| @doc-extractor | @architect, @validator, @diagram-generator |
| @deployer | @diagram-generator, @security-reviewer, @validator |
| @security-reviewer | @architect (fixes), @deployer (fixes), @doc-writer |
| @diagram-generator | @diagram-mermaid, @diagram-plantuml, @diagram-drawio, @diagram-d2, @diagram-structurizr |
| @validator | @architect (fixes), @deployer (fixes) |
| @doc-writer | (terminal — produces final documentation) |
| @pattern-manager | @deployer, @architect |
