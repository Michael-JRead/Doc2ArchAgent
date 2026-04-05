<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->
---
name: requesting-code-review
description: Use when a major task or feature is complete and needs review — dispatches a structured review request with clear scope, requirements, and commit references
allowed-tools:
  - execute
---

# Requesting Code Review

## Overview

Review early, review often. Don't accumulate changes without review checkpoints.

**Core principle:** A structured review request produces structured feedback.

## When to Review

**Mandatory review points:**
- After each task in subagent-driven development
- After completing a major feature or system model
- Before merging to main
- After security review findings are addressed

## The Review Request Template

When dispatching a review (to a subagent or requesting from the user):

```markdown
## Review Request

### What Was Done
<1-3 sentences: what was implemented/extracted/modeled>

### Requirements Reference
<Link to design doc or plan task being implemented>
- Design: docs/architecture-designs/<file>.md
- Plan task: Task N from docs/implementation-plans/<file>.md

### Files Changed
<List every file created or modified>
- `architecture/<system-id>/system.yaml` — Added container definitions
- `architecture/<system-id>/provenance.yaml` — Source citations

### Commits
- Base: <SHA before changes>
- Head: <SHA after changes>

### Validation Status
```bash
python tools/validate.py <file> --format table
# Result: 0 errors, 0 warnings
```

### Specific Concerns
<Anything you're unsure about — relationships, naming, security properties>
```

## Review Issue Categories

Reviewers should categorize findings:

| Category | Action | Example |
|----------|--------|---------|
| **Critical** | Fix immediately, blocks merge | Missing required field, invalid relationship |
| **Important** | Fix before proceeding | Naming inconsistency, missing provenance |
| **Minor** | Document for later | Style preference, optional enhancement |

## Handling Review Feedback

1. Read ALL feedback before acting
2. If anything is unclear, ask for clarification FIRST
3. Fix Critical items → Important items → Minor items
4. Re-validate after each fix
5. Request re-review if Critical or Important items were found

## Pushing Back

You may push back on review feedback when:
- The suggestion would violate the zero-hallucination invariant
- The reviewer lacks context about a design decision
- The suggestion conflicts with schema requirements
- The change would break existing valid architecture

Push back with technical reasoning, not defensiveness.

## Integration

- **Used by:** `subagent-driven-development` (per-task review), `executing-plans` (batch review)
- **Pairs with:** `receiving-code-review` (how to handle feedback you receive)
