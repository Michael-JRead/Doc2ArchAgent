<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->

# Handoff Protocol

**Applies to: ALL agents when transferring work to another agent.**

## When Handing Off

Every handoff MUST include:

1. **Summary of current state** — which files exist, what was just completed
2. **Exact task** for the target agent — what it should do
3. **Relevant file paths** the target agent should read
4. **Security overlay paths** when applicable (`system-security.yaml`, `networks-security.yaml`, `deployment-security.yaml`)

## Self-Validation Before Handoff

After any agent writes or modifies YAML, it MUST invoke validation before handing off:

```bash
python tools/validate.py <file> --format table
```

If validation fails, fix the errors before handing off. Never pass invalid YAML downstream.

## Handoff Format

Use the agent's declared `handoffs:` frontmatter to present options to the user. Always offer at least the most relevant next step.

## Context Passing

When handing off, include enough context that the receiving agent does not need to re-read the entire conversation. Summarize:
- What entities were created or modified
- Any unresolved questions or `NOT_STATED` fields
- User preferences expressed during the session (e.g., naming style, detail level)

## Never Hand Off Silently

Always tell the user what you're handing off and why. Let the user choose when to proceed.

## Red Flags — You Are Rationalizing If You Think:

| Thought | Reality |
|---------|---------|
| "The next agent will figure it out" | No. Provide complete context. |
| "Validation probably passes" | Run it. Handing off invalid YAML wastes everyone's time. |
| "I'll skip the security overlay paths" | Security context is not optional. Include it. |
| "The handoff is obvious" | Obvious to you with full context ≠ obvious to a fresh agent. |
