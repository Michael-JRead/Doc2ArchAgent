<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->

# Git Workflow

## Commit Messages
- Use conventional commit format: `type(scope): description`
- Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`
- Scope: agent name, tool name, or area (e.g., `feat(architect): add multi-context support`)
- Keep first line under 72 characters

## Branch Naming
- Feature branches: `feature/<description>`
- Bug fixes: `fix/<description>`
- Agent changes: `agent/<agent-name>-<description>`

## Before Committing
1. Run `python -m pytest tests/ -v` — all tests must pass
2. Run `python tools/validate.py` on any modified architecture YAML
3. Ensure no secrets, API keys, or credentials in committed files

## Pull Request Guidelines
- Include which agents/tools are affected
- Reference any related issues
- Include test evidence (validation output, test results)
