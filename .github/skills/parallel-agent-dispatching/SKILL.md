<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->
---
name: parallel-agent-dispatching
description: Use when facing 2 or more independent tasks that can be worked on without shared state or sequential dependencies — dispatches one agent per independent problem domain
allowed-tools:
  - execute
---

# Parallel Agent Dispatching

## Overview

Dispatch one agent per independent problem domain. Let them work concurrently.

**Core principle:** Independent problems deserve independent agents. Sequential investigation of parallel issues wastes time.

## When to Use

**Use when:**
- 2+ tasks with no shared state (e.g., modeling different systems)
- Multiple validation failures in different files
- Independent diagram generation for different scopes
- Parallel extraction from different document sources

**Don't use when:**
- Tasks are related (fixing one might fix others)
- Tasks share files (agents would conflict)
- You need to understand full system state first
- One task depends on another's output

## Decision Flow

```
Multiple tasks?
  ├─ No → Single agent handles it
  └─ Yes → Are they independent?
       ├─ No (related) → Single agent investigates all
       └─ Yes → Can they run in parallel?
            ├─ No (shared files) → Sequential agents
            └─ Yes → PARALLEL DISPATCH
```

## The Pattern

### 1. Identify Independent Domains

Group work by what's independent:
- System A extraction → Agent 1
- System B extraction → Agent 2
- Network zone modeling → Agent 3

Each domain is independent — Agent 1's work doesn't affect Agent 3.

### 2. Create Focused Agent Prompts

Each agent gets:

```markdown
## Task
<Specific, self-contained task description>

## Context
<All files the agent needs to know about>

## Constraints
- Only modify files in: <specific paths>
- Do NOT modify: <protected paths>
- Run validation after changes: python tools/validate.py <file> --format table

## Expected Output
- Files created: <list>
- Validation: 0 errors
- Summary of what you did and any concerns
```

**Key rules:**
- **Self-contained** — Include all context the agent needs
- **Scoped** — Explicit file boundaries prevent conflicts
- **Specific output** — What should the agent return?

### 3. Dispatch in Parallel

Launch all agents concurrently. Each works in isolation.

### 4. Review and Integrate

When all agents return:
1. Read each summary
2. Check for conflicts (same file modified by multiple agents)
3. Run full validation across all changes
4. Run full test suite
5. Resolve any integration issues

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Too broad: "Fix all the issues" | Specific: "Fix validation errors in system-a.yaml" |
| No context: "Figure it out" | Paste error messages, file paths, expected behavior |
| No constraints: agent touches unrelated files | Explicit scope: "Only modify files in architecture/acme/" |
| Vague output: "Let me know when done" | Specific: "Report files changed, validation results, concerns" |

## Verification After Integration

```bash
# Validate all changed files
python tools/validate.py architecture/*/system.yaml --format table

# Run full test suite
python -m pytest tests/ -v

# Check for inconsistencies across systems
python tools/validate.py --cross-reference
```

## Integration

- **Used within:** `subagent-driven-development` (for independent subtasks)
- **Pairs with:** `verification-before-completion` (verify integrated result)
