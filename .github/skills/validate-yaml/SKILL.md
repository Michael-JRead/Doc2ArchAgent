---
name: validate-yaml
description: Run deterministic YAML validation against architecture schemas, reporting errors in table, JSON, or SARIF format
allowed-tools: ['execute']
---

# YAML Validation Skill

Run deterministic validation against Doc2ArchAgent architecture YAML files. This skill uses Python-based schema validation with zero LLM involvement — same input always produces same output.

## Commands

### Validate a system file

```bash
python tools/validate.py architecture/<system-id>/system.yaml --format table
```

### Validate system + networks together (referential integrity)

```bash
python tools/validate.py architecture/<system-id>/system.yaml architecture/networks.yaml --format table
```

### Validate with security overlays

```bash
python tools/validate.py architecture/<system-id>/system.yaml architecture/networks.yaml \
    --security architecture/<system-id>/system-security.yaml \
    --security architecture/networks-security.yaml \
    --format table
```

### Validate a deployment composition

```bash
python tools/validate.py deployments/<deployment-id>/system.yaml \
    deployments/<deployment-id>/networks.yaml --format table
```

### Validate patterns

```bash
python tools/validate-patterns.py patterns/networks/<region>/<pattern-id>/
python tools/validate-patterns.py patterns/products/<category>/<pattern-id>/
```

### Strict mode (treats warnings as errors)

```bash
python tools/validate.py <file> --strict --format table
```

### SARIF output for GitHub Security tab

```bash
python tools/validate.py <file> --format sarif > results.sarif
```

## Output Formats

| Format | Flag | Use Case |
|--------|------|----------|
| `table` | `--format table` | Human-readable, best for interactive use |
| `json` | `--format json` | Machine-readable: `{"valid": bool, "errors": [...], "warnings": [...]}` |
| `sarif` | `--format sarif` | SARIF 2.1.0 for GitHub Security tab integration |

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | No errors (warnings allowed unless `--strict`) |
| `1` | Errors found |
| `2` | Only warnings found (with `--strict`) |

## What Gets Validated

1. **Schema validation** — Required fields, types, enum constraints against JSON schemas in `schemas/`
2. **Referential integrity** — All `container_ref`, `zone_ref`, `context_ref` point to existing IDs
3. **Naming conventions** — All IDs match kebab-case: `^[a-z][a-z0-9]*(-[a-z0-9]+)*$`
4. **Duplicate detection** — No two entities share the same ID within a type
5. **Orphan detection** — Components without containers, containers without contexts

## Common Error Codes

| Code | Description | Fix |
|------|-------------|-----|
| `ARCH001` | Missing required field | Add the field with a non-empty value |
| `ARCH002` | Referential integrity violation | Ensure referenced ID exists |
| `ARCH003` | Duplicate ID | Use unique IDs within each entity type |
| `ARCH004` | Invalid naming convention | Use kebab-case for all IDs |
| `ARCH005` | Orphaned entity | Add to a parent or remove |

## Self-Validation Rule

**Before any agent hands off to another agent, it MUST run validation** on any YAML it wrote or modified:

```bash
python tools/validate.py <modified-file> --format table
```

If validation fails, fix the errors before handing off. Never pass invalid YAML downstream.
