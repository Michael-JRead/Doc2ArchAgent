<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->
---
name: verification-before-completion
description: Use before claiming any task is complete — requires running verification commands and showing actual output as evidence, not assumptions or predictions
allowed-tools:
  - execute
---

# Verification Before Completion

## Overview

Never claim work is complete without fresh verification evidence.

**Core principle:** Claiming completion without verification is dishonest. "Should work" is not evidence.

## The Iron Law

```
NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE
```

## The Gate

Before saying "done", "complete", "finished", or "ready":

```
1. IDENTIFY — What command verifies this work?
2. RUN — Execute it NOW (not "I ran it earlier")
3. READ — Examine FULL output (not just exit code)
4. VERIFY — Does output MATCH your claim?
5. ONLY THEN — State completion with evidence
```

## What Counts as Evidence

**Valid evidence:**
- Actual command output pasted in your response
- Test results showing pass counts
- Validation output showing 0 errors
- Screenshot or log excerpt

**NOT evidence:**
- "Tests should pass"
- "I validated it earlier"
- "Based on my changes, this works"
- "The code looks correct"
- Previous test runs (must be FRESH)

## Verification Commands for Doc2ArchAgent

```bash
# YAML validation
python tools/validate.py <file> --format table
# Expected: "0 errors, 0 warnings"

# Full test suite
python -m pytest tests/ -v
# Expected: "X passed in Y seconds"

# Threat analysis
python tools/threat-rules.py <file> --format table
# Expected: findings listed (review each)

# Pattern validation
python tools/validate-patterns.py <pattern-dir>
# Expected: "All patterns valid"

# DFA constraints
python tools/dfa_constraints.py <system.yaml> --networks <networks.yaml>
# Expected: review all violations
```

## Partial Completion

If some parts pass and others fail, report honestly:

```
✓ system.yaml validates (0 errors)
✓ provenance.yaml validates (0 errors)
✗ security review found 3 HIGH findings
✗ 2 tests failing in test_regression.py

Status: PARTIALLY COMPLETE — 2 issues need resolution.
```

Never round up. 90% complete is not complete.

## Red Flags

| Thought | Reality |
|---------|---------|
| "I'm confident this works" | Confidence is not evidence. Run it. |
| "The tests passed 5 minutes ago" | Run them again. Something may have changed. |
| "It's just a documentation change, no need to verify" | Verify anyway. Typos in YAML docs break rendering. |
| "I'll verify after I tell the user it's done" | No. Verify BEFORE claiming completion. |
| "This is taking too long, let me just say it's done" | Exhaustion does not equal excuse. |
| "Should", "probably", "seems to" | These words mean you haven't verified. |

## Integration

- **Used by:** All execution skills (`executing-plans`, `subagent-driven-development`)
- **Pairs with:** `test-driven-development` (TDD ensures tests exist to verify against)
- **Required instinct:** `progress-reporting` (report honest status)
