<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->

# Testing Rules

## Before Any Handoff
- Run `python tools/validate.py <file> --format table` on all modified YAML
- Fix validation errors before handing off — never pass invalid YAML downstream

## Validation Layers
1. **Schema validation** — JSON Schema conformance via `tools/validate.py`
2. **Referential integrity** — All cross-entity references resolve
3. **Naming conventions** — All IDs are kebab-case
4. **Security posture** — `tools/threat-rules.py` for threat assessment
5. **Provenance** — `tools/validate-provenance.py` for citation verification
6. **Diagrams** — `tools/validate-diagram.py` for syntax correctness

## Test Fixtures
- Valid examples: `tests/fixtures/valid/`
- Invalid examples: `tests/fixtures/invalid/`
- Regression cases: `tests/fixtures/regression/`

## Running Tests
```bash
python -m pytest tests/ -v --tb=short
```

## When Adding New Features
- Add corresponding test fixtures for new schema fields or validation rules
- Ensure regression tests still pass after changes
