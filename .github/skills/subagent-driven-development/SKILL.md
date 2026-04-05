<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->
---
name: subagent-driven-development
description: Use when executing an implementation plan with multiple independent tasks — dispatches fresh agents per task with two-stage review (spec compliance then quality)
allowed-tools:
  - execute
  - edit
---

# Subagent-Driven Development

## Overview

Execute implementation plans by dispatching a fresh agent per task, with two-stage review (spec compliance, then quality) ensuring high-quality output.

**Core principle:** Fresh agent per task + two-stage review = high quality, fast iteration.

## When to Use

- You have a written implementation plan (from `writing-plans`)
- Tasks are mostly independent
- You want quality gates between tasks

## The Cycle

For each task in the plan:

```
1. DISPATCH implementer agent with full task context
2. RECEIVE work product
3. DISPATCH spec reviewer — "Did they build what was asked?"
4. If spec fails → implementer fixes → re-review
5. DISPATCH quality reviewer — "Is it well-built?"
6. If quality fails → implementer fixes → re-review
7. MARK task complete → next task
```

### 1. Dispatch Implementer

Send a focused prompt to the implementer agent:

```markdown
## Task
<Full task text from the plan — paste it, don't reference the file>

## Context
- System being modeled: <system-id>
- Relevant files: <list exact paths>
- Schema reference: schemas/<relevant>.schema.json

## Constraints
- Follow the zero-hallucination invariant
- Run validation after writing YAML: python tools/validate.py <file> --format table
- Do NOT modify files outside the task scope

## Expected Output
- Files created/modified: <list>
- Validation: 0 errors
- Summary of what you did
```

**Key rules:**
- Paste the full task text — never say "read the plan file"
- Include all file paths the agent needs
- Specify constraints explicitly

### 2. Review: Spec Compliance

After the implementer returns, dispatch a spec reviewer:

```markdown
## Review Task
Verify this work matches the specification.

## Original Spec
<Paste the task requirements>

## Work Product
<List files created/modified>

## Checklist
- [ ] All required entities present?
- [ ] Field values match specification?
- [ ] No extra entities that weren't specified?
- [ ] Validation passes?

Report: APPROVED or NEEDS_CHANGES with specific items.
```

### 3. Review: Quality

Only after spec review passes, dispatch a quality reviewer:

```markdown
## Quality Review
Review this architecture YAML for quality standards.

## Files
<List files to review>

## Check
- [ ] Kebab-case IDs throughout
- [ ] All relationships have valid source/target
- [ ] Security properties specified where applicable
- [ ] No duplicated entities
- [ ] Provenance entries exist for extracted entities
- [ ] YAML formatting follows rules/common/yaml-formatting.md

Report: APPROVED or NEEDS_CHANGES with specific items.
```

### 4. Handle Status

| Status | Action |
|--------|--------|
| DONE | Proceed to spec review |
| DONE_WITH_CONCERNS | Read concerns. Fix correctness issues before review. |
| NEEDS_CONTEXT | Provide missing info, re-dispatch |
| BLOCKED | Assess: wrong task scope? Missing prerequisite? Plan issue? |

### 5. Final Review

After all tasks complete:
1. Run full validation across all produced files
2. Run `python -m pytest tests/ -v`
3. Review overall consistency
4. Use `finishing-a-development-branch` skill

## Critical Rules

- **Never skip reviews** — even if the implementer "seems confident"
- **Never proceed with unfixed issues** — spec must pass before quality review
- **Always re-review after fixes** — fixes can introduce new issues
- **Never let implementers read plan files directly** — paste full task text

## Red Flags

| Thought | Reality |
|---------|---------|
| "This task is simple, skip review" | Simple tasks have subtle errors. Review. |
| "The implementer already validated" | Trust but verify. Run validation yourself. |
| "We're running behind, skip quality review" | Skipping quality now = debugging later |
| "I'll review multiple tasks at once" | Review each task independently |

## Integration

- **Prerequisites:** `writing-plans`, `brainstorming`
- **Completion:** `finishing-a-development-branch`
- **Related:** `parallel-agent-dispatching` (for independent subtasks within a task)
