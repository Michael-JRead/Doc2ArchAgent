<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->

# Progress Reporting

**Applies to: ALL agents.**

## Status Indicators

Use these consistently throughout all responses:

```
✓  Completed / Success
►  In progress / Current step
⚠  Warning / Needs attention
✗  Error / Failed / Skipped
❓ Question / User input needed
```

## Progress Banners

At the start of each major phase, show a progress banner:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE NAME                    [===>      ]
Context: System Name
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Checkpoint Summaries

After completing each phase, show what was accomplished:

```
✓ PHASE COMPLETE
Captured: [summary of what was produced]
Files written: [list of files]
► Next: [what comes next]
```

## Loading Confirmation

When reading files at startup, confirm what was loaded:

```
✓ Loaded: [summary of loaded files]
```

If no files are found when expected, say so immediately:

```
✗ No architecture files found. Please run @architect first.
```

## Micro-Confirmations

After every significant action (writing YAML, generating a diagram, completing a check), confirm with the user before proceeding. Never assume the user wants to continue — always offer the next step explicitly.
