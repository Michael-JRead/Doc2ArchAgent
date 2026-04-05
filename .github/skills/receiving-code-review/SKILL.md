<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->
---
name: receiving-code-review
description: Use when receiving code review feedback before implementing suggestions — requires technical verification and reasoned evaluation, not performative agreement or blind implementation
allowed-tools:
  - execute
  - edit
---

# Receiving Code Review

## Overview

Code review requires technical evaluation, not emotional performance.

**Core principle:** Verify before implementing. Ask before assuming. Technical correctness over social comfort.

## The Response Pattern

```
WHEN receiving code review feedback:

1. READ    — Complete feedback without reacting
2. UNDERSTAND — Restate the requirement in your own words (or ask)
3. VERIFY  — Check against the actual codebase/YAML
4. EVALUATE — Is this technically sound for THIS architecture?
5. RESPOND — Technical acknowledgment or reasoned pushback
6. IMPLEMENT — One item at a time, validate after each
```

## Forbidden Responses

**NEVER say:**
- "You're absolutely right!"
- "Great point!"
- "Excellent feedback!"
- "Thank you for catching that!"
- "Let me implement that now" (before verification)

**INSTEAD:**
- Restate the technical requirement
- Ask clarifying questions if anything is ambiguous
- Push back with technical reasoning if the suggestion is wrong
- Just start fixing (actions over words)

## Handling Unclear Feedback

```
IF any item is unclear:
  STOP — do not implement anything yet
  ASK for clarification on ALL unclear items

WHY: Items may be related. Partial understanding = wrong implementation.
```

**Example:**
```
Review has 6 items. You understand 1, 2, 3, 6. Unclear on 4 and 5.

✗ WRONG: Implement 1, 2, 3, 6 now. Ask about 4, 5 later.
✓ RIGHT: "I understand items 1-3 and 6. Need clarification on 4 and 5 before proceeding."
```

## Evaluation Checklist

Before implementing any suggestion:

- [ ] Is this technically correct for our YAML schemas?
- [ ] Does this break existing validation (`python tools/validate.py`)?
- [ ] Is there a reason the current implementation was chosen?
- [ ] Does this conflict with the zero-hallucination invariant?
- [ ] Does this suggestion apply to our architecture domain?

## When to Push Back

Push back when:
- Suggestion would add entities not in source documents (hallucination)
- Reviewer doesn't understand the C4 model constraints
- Change would break schema validation
- Suggestion conflicts with approved design
- YAGNI — feature/entity is not needed yet

**How to push back:**
- State the technical reason clearly
- Reference the schema, design doc, or validation rule
- Offer an alternative if appropriate
- Involve the user if it's an architectural decision

## Implementation Order

For multi-item feedback:

```
1. Clarify ALL unclear items FIRST
2. Then implement in this order:
   a. Critical: breaks validation, invalid relationships
   b. Simple: naming fixes, missing fields
   c. Complex: restructuring, relationship changes
3. Validate after EACH fix
4. Run full test suite after all fixes
```

## Red Flags

| Thought | Reality |
|---------|---------|
| "They're probably right, just do it" | Verify first. Reviewers can be wrong. |
| "I should be grateful for feedback" | Be professional, not performative. |
| "I'll implement everything to avoid conflict" | Implement what's correct. Push back on what's not. |
| "This is just a style preference" | Check if it's actually a schema/validation requirement. |

## Integration

- **Pairs with:** `requesting-code-review` (the other side of the review cycle)
- **Used during:** `subagent-driven-development`, `executing-plans`
