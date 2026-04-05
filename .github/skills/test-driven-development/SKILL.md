<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->
---
name: test-driven-development
description: Use when implementing any new tool, feature, or bugfix — enforces Red-Green-Refactor cycle where no production code is written without a failing test first
allowed-tools:
  - execute
  - edit
---

# Test-Driven Development (TDD)

## Overview

Write the test first. Watch it fail. Write minimal code to pass.

**Core principle:** If you didn't watch the test fail, you don't know if it tests the right thing.

**Violating the letter of the rules IS violating the spirit of the rules.**

## The Iron Law

```
NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST
```

Wrote code before the test? Delete it. Start over.

**No exceptions:**
- Don't keep it as "reference"
- Don't "adapt" it while writing tests
- Don't look at it
- Delete means delete

Implement fresh from tests. Period.

## When to Use

**Always:**
- New Python tools in `tools/`
- Bug fixes in existing tools
- New validation rules
- New schema constraints
- Behavior changes in any tool

**Exceptions (ask the user):**
- Agent `.md` files (not testable with pytest)
- YAML schema definitions (validated differently)
- Configuration files

## Red-Green-Refactor

### RED — Write Failing Test

Write one minimal test showing what should happen.

```python
# Good: Clear name, tests real behavior, one thing
def test_validate_rejects_missing_container_type(tmp_path):
    yaml_content = "containers:\n  - id: api-gw\n    name: API Gateway\n"
    system_file = tmp_path / "system.yaml"
    system_file.write_text(yaml_content)
    result = validate(str(system_file))
    assert result.error_count > 0
    assert "container_type" in result.errors[0].message
```

```python
# Bad: Vague name, tests mock not behavior
def test_validation_works():
    mock = MagicMock()
    mock.return_value = True
    assert validate(mock)
```

**Requirements:**
- One behavior per test
- Clear, descriptive name
- Real code paths (minimize mocks)

### Verify RED — Watch It Fail

**MANDATORY. Never skip.**

```bash
python -m pytest tests/test_<module>.py::<test_name> -v
```

Confirm:
- Test fails (not errors)
- Failure message matches what you expect
- Fails because the feature is missing (not because of typos)

**Test passes immediately?** You're testing existing behavior, not new behavior.

### GREEN — Write Minimal Code

Write the **minimum code** to make the failing test pass.

- No extra features
- No "while I'm here" improvements
- No premature optimization
- Just make the red test green

```bash
python -m pytest tests/test_<module>.py::<test_name> -v
# Expected: PASSED
```

### Verify GREEN — All Tests Pass

Run the full test suite:

```bash
python -m pytest tests/ -v
```

All tests must pass. If a previously passing test now fails, your change broke something. Fix it before proceeding.

### REFACTOR — Clean Up

Now — and only now — improve the code:
- Remove duplication
- Improve naming
- Simplify logic

After every refactor change, run tests again. Stay green.

## Testing Anti-Patterns

### 1. Testing Mock Behavior Instead of Real Code
If your test only verifies that a mock was called, it tests nothing about your actual code.

### 2. Test-Only Methods in Production Code
If you add a method solely for testing, your design needs rethinking.

### 3. Mocking Without Understanding
Don't mock what you haven't read. Understand the real behavior first.

### 4. Integration Tests as Afterthought
If unit tests pass but integration fails, your units aren't integrated. Write integration tests too.

### 5. Skipping the RED Step
"I know this test would fail" — You don't. Run it.

## Doc2ArchAgent-Specific Patterns

### Testing Validation Tools
```python
def test_validate_catches_invalid_relationship_target(fixture_dir):
    result = subprocess.run(
        ["python", "tools/validate.py", str(fixture_dir / "bad-ref.yaml"), "--format", "json"],
        capture_output=True, text=True
    )
    output = json.loads(result.stdout)
    assert output["error_count"] > 0
```

### Testing Threat Rules
```python
def test_stride_detects_unauthenticated_listener(fixture_dir):
    result = subprocess.run(
        ["python", "tools/threat-rules.py", str(fixture_dir / "no-auth.yaml"), "--format", "json"],
        capture_output=True, text=True
    )
    findings = json.loads(result.stdout)
    assert any(f["stride_category"] == "Spoofing" for f in findings)
```

## Red Flags

| Thought | Reality |
|---------|---------|
| "Skip TDD just this once" | Stop. That's rationalization. |
| "I'll add tests later" | Later never comes. Test first. |
| "This is too simple to test" | Simple code breaks too. Test it. |
| "The existing tests cover this" | If they do, your new test should fail identically. Verify. |
| "I'm just refactoring, no new tests needed" | Correct — but run existing tests after EVERY change. |
| "TDD is slower" | Debugging untested code is slower. |

## Integration

- **Used by:** `executing-plans`, `subagent-driven-development`
- **Pairs with:** `verification-before-completion` (ensures evidence-based completion)
- **Test location:** `tests/` directory (pytest)
