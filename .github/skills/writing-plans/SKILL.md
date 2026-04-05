<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->
---
name: writing-plans
description: Use when a design has been approved and you need to create a structured implementation plan — breaks work into bite-sized tasks with exact steps, file paths, and verification commands
allowed-tools:
  - execute
  - edit
---

# Writing Plans — Structured Implementation Planning

## Overview

Create implementation plans detailed enough for an agent with no project context to follow. Every task must be self-contained with exact file paths, code/YAML content, and verification steps.

**Core principle:** If the plan says "similar to Task N" or "add appropriate config," it's not a plan — it's a wish.

## When to Use

- After a design has been approved (via brainstorming skill)
- When breaking down a complex modeling task into ordered steps
- When preparing work for subagent execution

## Plan Header (Required)

Every plan starts with:

```markdown
# Implementation Plan: <system-id>

## Goal
<One sentence describing what this plan produces>

## Architecture Context
<Which C4 layers are covered, which agents are involved>

## Prerequisites
- [ ] Design document approved: docs/architecture-designs/<design-file>.md
- [ ] Source documents available at: <paths>
- [ ] Required patterns exist: <pattern paths>
```

## Task Format

Each task follows this structure:

```markdown
### Task N: <Clear action verb> <specific target>

**Files:** `<file1>`, `<file2>`
**Agent:** @<agent-name> (or manual)
**Depends on:** Task M (if applicable)

#### Steps

1. <Exact action with file path>
   ```yaml
   # Exact YAML content to write or expect
   ```

2. <Next action>

#### Verification

```bash
python tools/validate.py <file> --format table
# Expected: 0 errors, 0 warnings
```

#### Done When
- [ ] File exists and passes validation
- [ ] Specific condition met
```

## Task Design Rules

1. **2-5 minutes per task** — If longer, split it
2. **Exact file paths** — Never "the config file" or "the YAML"
3. **Complete content** — Show the full YAML/code block, not snippets
4. **Verification for every task** — A `python tools/validate.py` or `python -m pytest` command
5. **No placeholders** — "TBD", "TODO", "add as needed" are forbidden
6. **Dependency ordering** — Tasks that produce files other tasks read come first
7. **One concern per task** — Don't mix extraction with diagram generation

## Task Ordering for Architecture Work

Follow the natural data flow:

1. **Document collection** — `@doc-collector` gathers sources
2. **Entity extraction** — `@doc-extractor` produces system.yaml + provenance.yaml
3. **Pattern application** — `@pattern-manager` merges patterns if applicable
4. **Validation** — `@validator` checks schema conformance
5. **Security review** — `@security-reviewer` runs STRIDE analysis
6. **Deployment mapping** — `@deployer` places containers in zones
7. **Diagram generation** — `@diagram-generator` produces visuals
8. **Documentation** — `@doc-writer` generates HLDD

## Self-Review Checklist

Before saving the plan, verify:

- [ ] Every design requirement maps to at least one task
- [ ] No tasks contain "TBD", "TODO", "similar to", or vague language
- [ ] Every task has a verification step
- [ ] File paths are consistent across tasks (no typos)
- [ ] Dependencies form a DAG (no circular dependencies)
- [ ] Total estimated effort is reasonable

## Save Location

```
docs/implementation-plans/YYYY-MM-DD-<system-id>-plan.md
```

## Handoff

After saving, offer two execution modes:

1. **Subagent-driven** (recommended) — Fresh agent per task with two-stage review. Use `subagent-driven-development` skill.
2. **Sequential execution** — Execute tasks inline with checkpoints. Use `executing-plans` skill.

## Red Flags

| Thought | Reality |
|---------|---------|
| "The agent will figure out the details" | No. Specify every detail. |
| "This task is obvious" | Obvious to you ≠ obvious to a fresh agent. |
| "I'll add verification later" | Every task needs verification NOW. |
| "These tasks can be combined" | Smaller tasks = better isolation = fewer failures. |
