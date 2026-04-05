<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->

# Scope Enforcement

**Applies to: ALL agents.**

## Core Rule

Every agent has a declared scope — the set of files and directories it is allowed to create or modify. Agents MUST stay within their scope at all times.

## Protected Files and Directories

These are NEVER modified by any agent:

- `schemas/` — Source of truth for validation (JSON Schema files)
- `context/*.yaml` — Curated threat rules, compliance mappings, risk scoring
- `.github/agents/` — Agent definition files
- `.github/skills/` — Skill definition files
- `instincts/` — Shared behavioral patterns
- `rules/` — Standards and conventions
- `tools/` — Deterministic Python tools
- Generated files marked with `GENERATED` header — modify the manifest or source patterns instead
- License files: `LICENSE`, `LICENSE-COMMERCIAL.md`, `CLA.md`, `NOTICE`

## Agent Scope Matrix

| Agent | Can Create/Modify | Cannot Modify |
|-------|-------------------|---------------|
| @architect | `architecture/<system-id>/system.yaml`, `networks.yaml` | Other agents' outputs |
| @doc-collector | `context/<system-id>/`, `<pattern-dir>/contexts/sources/` | Architecture YAML |
| @doc-extractor | `architecture/<system-id>/system.yaml`, `provenance.yaml` | Schema files |
| @deployer | `deployments/`, `architecture/<system-id>/deployments/` | system.yaml |
| @security-reviewer | Security findings/reports (read-only analysis) | Architecture YAML |
| @diagram-generator | `layout-plan.yaml`, `diagrams/_index.yaml` | Source YAML |
| @diagram-* | `diagrams/*.md`, `*.puml`, `*.drawio`, `*.d2`, `*.dsl` | Source YAML |
| @validator | Validation reports (read-only analysis) | Architecture YAML |
| @doc-writer | `docs/*.md`, `docs/*.confluence.html` | Architecture YAML |
| @pattern-manager | `patterns/` | Deployed architecture files |

## Drift Detection

If an agent attempts to modify files outside its scope, it should:
1. Stop immediately
2. Report the attempted modification to the user
3. Suggest which agent should make the change instead
