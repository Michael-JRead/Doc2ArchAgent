<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->
---
name: systematic-debugging
description: Use when tests fail, validation produces unexpected errors, tools crash, or any unexpected behavior occurs — enforces root-cause-first investigation before attempting fixes
allowed-tools:
  - execute
  - edit
---

# Systematic Debugging

## Overview

Find the root cause first. Never guess-and-fix.

**Core principle:** If 3 fixes have failed, question the architecture — don't attempt fix #4.

## The 4-Phase Process

### Phase 1: Root Cause Investigation

**Read before you act:**

1. **Read the actual error** — Copy the full error message, stack trace, and exit code
2. **Reproduce** — Run the exact command that failed
3. **Check recent changes** — What was modified since it last worked?
4. **Trace the data flow** — Follow the input from source to error point

```bash
# Example: Validation failure
python tools/validate.py architecture/acme/system.yaml --format table 2>&1
# Read EVERY line of output — don't skim
```

**Never skip reading the error.** Most "mysterious" bugs have clear error messages that were never read.

### Phase 2: Pattern Analysis

Find a working example and compare:

1. Locate a file/test/config that WORKS correctly
2. Diff it against the failing case
3. Identify the exact difference

```bash
# Compare working vs failing
diff examples/payment-platform/system.yaml architecture/acme/system.yaml
```

### Phase 3: Hypothesis and Test

Use the scientific method:

1. Form ONE hypothesis about the root cause
2. Predict what would happen if your hypothesis is correct
3. Test the prediction with the smallest possible change
4. If prediction wrong → new hypothesis (don't force the old one)

**One variable at a time.** Don't change 3 things and hope one works.

### Phase 4: Fix and Verify

1. Create a failing test that reproduces the bug (TDD!)
2. Apply the single fix
3. Verify the test passes
4. Run the full test suite — ensure no regressions

```bash
python -m pytest tests/ -v
# ALL tests must pass, not just the one you fixed
```

## The 3-Fix Rule

```
Fix attempt 1 failed → Normal, try another hypothesis
Fix attempt 2 failed → Slow down, re-read the error carefully
Fix attempt 3 failed → STOP. Question your assumptions entirely.
```

After 3 failed fixes:
- Is the problem actually where you think it is?
- Are you reading the right file?
- Is there a deeper architectural issue?
- Should you ask the user for context?

**Do not attempt fix #4 without fundamentally changing your approach.**

## Common Debug Patterns for Doc2ArchAgent

### Validation Errors
```bash
# Get detailed error output
python tools/validate.py <file> --format json 2>&1 | python -m json.tool
# Check the schema
cat schemas/<type>.schema.json | python -m json.tool
# Verify the YAML parses
python -c "import yaml; yaml.safe_load(open('<file>'))"
```

### Threat Rule False Positives
```bash
# Run with verbose output
python tools/threat-rules.py <file> --format json 2>&1
# Check threat-rules.yaml for the triggering rule
grep -n "<rule-id>" context/threat-rules.yaml
```

### Composition Failures
```bash
# Validate the manifest first
python tools/validate.py <manifest> --format table
# Then validate source patterns
python tools/validate-patterns.py <pattern-dir>
```

## Red Flags

| Thought | Reality |
|---------|---------|
| "Let me just try this quick fix" | Root cause first. Quick fixes hide real issues. |
| "I've seen this before" | Maybe. Verify — don't assume. |
| "It must be a race condition" | It's almost never a race condition. Read the error. |
| "The tool must be buggy" | Your input is more likely wrong. Validate your input first. |
| "Let me rewrite this whole thing" | Rewrites don't fix bugs you don't understand. |
| "I'll add more logging" | Read the existing error message first. |

## Integration

- **Pairs with:** `test-driven-development` (create failing test for the bug)
- **Pairs with:** `verification-before-completion` (verify the fix works)
- **Used when:** Any unexpected behavior during plan execution
