<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->
---
name: finishing-a-development-branch
description: Use when implementation is complete and all tests pass — guides branch completion by verifying tests, presenting structured options (merge, PR, keep, discard), and cleaning up
allowed-tools:
  - execute
---

# Finishing a Development Branch

## Overview

Guide completion of development work by presenting clear options and handling the chosen workflow.

**Core principle:** Verify tests → Present options → Execute choice → Clean up.

## The Process

### Step 1: Verify Tests

**Before presenting options, verify ALL tests pass:**

```bash
python -m pytest tests/ -v
python tools/validate.py <files> --format table
```

**If tests fail:**
```
Tests failing (N failures). Must fix before completing:

[Show failures]

Cannot proceed with merge/PR until tests pass.
```

**STOP.** Do not proceed to Step 2.

### Step 2: Determine Base Branch

```bash
git merge-base HEAD main 2>/dev/null || git merge-base HEAD master 2>/dev/null
```

Or ask: "This branch diverged from `main` — is that correct?"

### Step 3: Present Options

Present exactly these 4 options:

```
Implementation complete. All tests passing. What would you like to do?

1. Merge back to <base-branch> locally
2. Push and create a Pull Request
3. Keep the branch as-is (I'll handle it later)
4. Discard this work
```

**Don't add explanation** — keep options concise. Wait for the user's choice.

### Step 4: Execute Choice

#### Option 1: Merge Locally
```bash
git checkout <base-branch>
git pull origin <base-branch>
git merge <feature-branch>
python -m pytest tests/ -v              # Verify after merge
git branch -d <feature-branch>
```

#### Option 2: Push and Create PR
```bash
git push -u origin <feature-branch>
# Then create PR with summary of changes
```

#### Option 3: Keep As-Is
Report: "Keeping branch `<name>`. Worktree preserved at `<path>`."

**Don't cleanup worktree.**

#### Option 4: Discard

**Confirm first:**
```
This will permanently delete:
- Branch: <name>
- All commits since <base>
- Worktree at <path> (if applicable)

Type 'discard' to confirm.
```

Wait for exact confirmation. Then:
```bash
git checkout <base-branch>
git branch -D <feature-branch>
```

### Step 5: Cleanup Worktree (if applicable)

For Options 1, 2, 4:
```bash
git worktree remove <worktree-path> 2>/dev/null
```

For Option 3: keep worktree intact.

## Quick Reference

| Option | Merge | Push | Keep Worktree | Cleanup Branch |
|--------|-------|------|---------------|----------------|
| 1. Merge locally | ✓ | — | — | ✓ |
| 2. Create PR | — | ✓ | ✓ | — |
| 3. Keep as-is | — | — | ✓ | — |
| 4. Discard | — | — | — | ✓ (force) |

## Red Flags

**Never:**
- Proceed with failing tests
- Merge without verifying tests on the merged result
- Delete work without typed confirmation
- Force-push without explicit user request

**Always:**
- Verify tests before presenting options
- Present exactly 4 options
- Get typed confirmation for Option 4
- Clean up worktree for Options 1 and 4 only

## Integration

- **Called by:** `subagent-driven-development`, `executing-plans`
- **Pairs with:** `git-worktrees` (cleanup)
- **Prerequisite:** `verification-before-completion` (tests must pass first)
