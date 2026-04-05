<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->
---
name: git-worktrees
description: Use when starting feature work that needs isolation from the current workspace or before executing implementation plans — creates isolated git worktrees with safety verification
allowed-tools:
  - execute
---

# Git Worktrees — Isolated Workspace Management

## Overview

Git worktrees create isolated workspaces sharing the same repository, allowing work on multiple branches without switching.

**Core principle:** Systematic directory selection + safety verification = reliable isolation.

## When to Use

- Starting a new feature branch for architecture modeling
- Executing an implementation plan (isolate from main)
- Parallel work on different systems/deployments
- Any work you want to be able to discard cleanly

## Directory Selection (Priority Order)

### 1. Check for Existing Worktree Directory

```bash
ls -d .worktrees 2>/dev/null     # Preferred (hidden)
ls -d worktrees 2>/dev/null      # Alternative
```

If found, use that directory. If both exist, `.worktrees/` wins.

### 2. Check CLAUDE.md / Project Config

```bash
grep -i "worktree" CLAUDE.md 2>/dev/null
```

If a preference is specified, use it.

### 3. Ask the User

```
No worktree directory found. Where should I create worktrees?

1. .worktrees/ (project-local, hidden)
2. A custom path

Which would you prefer?
```

## Safety Verification

**Before creating a project-local worktree, verify the directory is git-ignored:**

```bash
git check-ignore -q .worktrees 2>/dev/null
```

**If NOT ignored:**
1. Add `.worktrees/` to `.gitignore`
2. Commit the change
3. Then create the worktree

**Why:** Prevents accidentally committing worktree contents to the repository.

## Creation Steps

```bash
# 1. Create worktree with new branch
git worktree add .worktrees/<branch-name> -b <branch-name>

# 2. Enter worktree
cd .worktrees/<branch-name>

# 3. Install dependencies
pip install -r requirements.txt 2>/dev/null || pip install -e ".[dev]" 2>/dev/null

# 4. Verify clean baseline
python -m pytest tests/ -v
```

**If tests fail during baseline:** Report failures and ask whether to proceed or investigate.

**If tests pass:** Report ready.

```
Worktree ready at .worktrees/<branch-name>
Tests passing (510 tests, 0 failures)
Ready to implement <feature-name>
```

## Cleanup

When work is complete (via `finishing-a-development-branch`):

```bash
# Remove the worktree
git worktree remove .worktrees/<branch-name>

# Verify removal
git worktree list
```

## Quick Reference

| Situation | Action |
|-----------|--------|
| `.worktrees/` exists | Use it (verify ignored) |
| `worktrees/` exists | Use it (verify ignored) |
| Neither exists | Check CLAUDE.md → ask user |
| Directory not ignored | Add to `.gitignore` + commit |
| Tests fail during baseline | Report failures + ask |
| No requirements.txt | Skip dependency install |

## Integration

- **Called by:** `brainstorming`, `executing-plans`, `subagent-driven-development`
- **Pairs with:** `finishing-a-development-branch` (cleanup)
