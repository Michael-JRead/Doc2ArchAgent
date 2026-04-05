<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->
---
name: executing-plans
description: Use when you have a written implementation plan to execute — loads the plan, reviews critically, executes tasks sequentially with verification at each step
allowed-tools:
  - execute
  - edit
---

# Executing Plans — Sequential Plan Execution

## Overview

Load a plan, review it critically, execute all tasks in order, verify each step, report when complete.

**Core principle:** Follow the plan exactly. Stop when blocked. Never guess.

## The Process

### Step 1: Load and Review Plan

1. Read the plan file from `docs/implementation-plans/`
2. Review critically — identify any concerns:
   - Missing file paths?
   - Unclear verification steps?
   - Missing prerequisites?
3. If concerns exist: raise them with the user before starting
4. If no concerns: proceed

### Step 2: Execute Tasks

For each task in order:

1. Check dependencies — are prerequisite tasks completed?
2. Execute each step exactly as written
3. Run the verification command specified in the task
4. If verification passes: mark task complete, move to next
5. If verification fails: STOP and report

```
Task 3 of 8: Extract container entities
✓ Step 1: Read source document
✓ Step 2: Write system.yaml containers section
✗ Step 3: Validate — 2 errors found

BLOCKED: Validation failed. Errors:
  - Line 42: container 'api-gateway' missing required field 'container_type'
  - Line 58: relationship target 'unknown-db' not found

Awaiting guidance.
```

### Step 3: Complete

After all tasks verified:

1. Run full validation: `python tools/validate.py <system.yaml> --format table`
2. Run tests: `python -m pytest tests/ -v`
3. Report summary of what was produced
4. Use `finishing-a-development-branch` skill if on a feature branch

## When to STOP

**Stop executing immediately when:**
- A verification step fails
- A task instruction is unclear or ambiguous
- A required file doesn't exist
- The plan has gaps preventing progress
- You discover the plan contradicts the design document

**Ask for help rather than guessing.** Wrong guesses in architecture modeling compound into wrong threat models, wrong deployments, and wrong diagrams.

## Red Flags

| Thought | Reality |
|---------|---------|
| "I can infer what they meant" | In architecture, inference = hallucination |
| "Close enough" | Validation is pass/fail, not close-enough |
| "I'll fix the plan as I go" | Changing the plan mid-execution without approval = drift |
| "Skip this verification, it probably passes" | Run it. "Probably" is not evidence. |

## Integration

- **Prerequisites:** `writing-plans` (creates the plan), `brainstorming` (creates the design)
- **Completion:** `finishing-a-development-branch` (merge/PR/cleanup)
- **Alternative:** `subagent-driven-development` (parallel execution with review)
