<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->

# YAML Hygiene

**Applies to: ALL agents that write or modify YAML files.**

## Naming Conventions

- All entity IDs MUST use **kebab-case**: `^[a-z][a-z0-9]*(-[a-z0-9]+)*$`
- Examples: `payment-gateway`, `prod-us-east`, `private-app-tier`
- File names: lowercase with hyphens (e.g., `payment-platform.yaml`, `prod-us-east.yaml`)
- Auto-generate IDs from entity names: "Payment Gateway" → `payment-gateway`

## Required Fields

- Never skip required fields. If a value is unknown, mark it `NOT_STATED` and ask the developer.
- Required fields are defined in `schemas/*.schema.json` — these are the source of truth.

## Formatting Rules

- Use 2-space indentation consistently
- Quote strings that could be misinterpreted as YAML types (e.g., `"true"`, `"null"`, `"yes"`, `"3.0"`)
- Use block scalars (`|`) for multi-line strings
- Always include trailing newline at end of file
- Keep YAML keys in the order defined by the schema

## Incremental Writing

- Use `edit` (append), never overwrite entire files
- Show YAML to the user after each entity is captured
- Get user confirmation before proceeding to the next entity
- Never silently modify previously confirmed YAML

## Enum Values

- Always use exact enum values from the schema. Do not use synonyms or abbreviations.
- If unsure which enum value applies, present the valid options to the user.
