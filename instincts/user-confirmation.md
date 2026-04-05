<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->

# User Confirmation

**Applies to: ALL agents that write or modify files.**

## Core Rule

Always confirm with the developer before writing files. Show the proposed YAML or content, get explicit approval, then write.

## Confirmation Points

1. **Before first file write** — Confirm system name, output directory, and file structure
2. **After each entity** — Show the YAML for the entity just captured, confirm before continuing
3. **Before overwriting** — If a file already exists, show what will change and get approval
4. **Before handoff** — Confirm the user wants to proceed to the next agent
5. **Before destructive actions** — Deleting files, removing entities, resetting state

## What NOT to Confirm

- Reading files (always allowed, no confirmation needed)
- Running validation tools (read-only, always allowed)
- Showing progress or status (informational, always allowed)

## When the User Says "Do It All"

If the user explicitly requests batch processing ("model everything", "validate all"), you may proceed through multiple steps but still show a summary checkpoint after each major phase.
