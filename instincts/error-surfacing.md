<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->

# Error Surfacing

**Applies to: ALL agents.**

## Core Rule

Never silently swallow errors. Every error, warning, or unexpected condition MUST be surfaced to the developer with clear context.

## Error Display Format

Always prefix errors with severity and provide actionable guidance:

```
✗ [ERROR] <what went wrong>
  Expected: <what was expected>
  Found: <what was actually found>
  Fix: <how to resolve it>
```

```
⚠ [WARNING] <what might be wrong>
  Detail: <additional context>
  Recommendation: <suggested action>
```

## Error Categories

1. **Validation errors** — Schema violations, missing required fields, broken references. Show the exact field and valid options.
2. **File errors** — Missing files, permission issues, malformed YAML. Show the expected path and what to do.
3. **Reference errors** — Dangling `context_id`, `container_id`, `listener_ref`. List valid IDs the user can choose from.
4. **Tool errors** — Python tool failures. Show the command that failed and the error output.

## Recovery Guidance

After surfacing an error, always suggest at least one concrete fix. Never leave the user with just an error message and no path forward.

## Never Silently Skip

- If a validation check fails, report it — do not skip to the next check
- If a file is missing, say so — do not proceed without it
- If a referenced entity doesn't exist, show valid options — do not silently drop the reference

## Red Flags — You Are Rationalizing If You Think:

| Thought | Reality |
|---------|---------|
| "This error is probably a false positive" | Investigate before dismissing. Show it to the user. |
| "I can work around this" | Workarounds hide bugs. Surface the error. |
| "The user doesn't need to see this warning" | The user decides what matters. Show everything. |
| "I'll fix it quietly" | Silent fixes are invisible fixes. Report what you changed. |
