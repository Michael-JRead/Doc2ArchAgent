---
name: pattern-composition
description: Create deployment compositions from network and product patterns using manifest.yaml and the compose tool
allowed-tools: ['execute', 'read']
---

# Pattern Composition Skill

Create deployment compositions by merging reusable network and product patterns via `manifest.yaml`.

## Commands

### Compose a deployment

```bash
python tools/compose.py deployments/<deployment-id>/manifest.yaml
```

### Compose with validation

```bash
python tools/compose.py deployments/<deployment-id>/manifest.yaml --validate
```

### Dry run (preview without writing)

```bash
python tools/compose.py deployments/<deployment-id>/manifest.yaml --dry-run
```

## Manifest Structure

The `manifest.yaml` declares which patterns to compose:

```yaml
manifest:
  id: mq-prod-us-east
  name: MQ Production US East
  environment: production
  region: us-east-1

  network:
    pattern_ref: standard-3tier     # Pattern directory name
    version: "1.0.0"                # Required version match
    id_prefix: prod                 # Prefix applied to all network IDs

  products:
    - pattern_ref: ibm-mq           # Pattern directory name
      version: "1.0.0"
      id_prefix: mq                 # Prefix applied to all system IDs
      context_name: MQ Production Messaging

  placements:
    - container_ref: mq-mq-infrastructure   # prefixed: <product-prefix>-<original-id>
      zone_ref: prod-private-app-tier       # prefixed: <network-prefix>-<original-id>
      replicas: 2

  overrides:                        # Optional per-entity overrides
    - entity_ref: mq-queue-manager
      field: technology
      value: "IBM MQ 9.4"
```

## ID Prefixing

Every pattern gets a unique prefix to avoid ID collisions when composing:

- Network pattern IDs: `<network.id_prefix>-<original-id>` (e.g., `prod-private-app-tier`)
- Product pattern IDs: `<product.id_prefix>-<original-id>` (e.g., `mq-queue-manager`)
- Placement references must use prefixed IDs

## Generated Output

Compose writes these files alongside the manifest (all marked `DO NOT EDIT`):

| File | Content |
|------|---------|
| `networks.yaml` | Composed network topology from network pattern |
| `system.yaml` | Composed system architecture from product patterns |
| `deployment.yaml` | Zone placements from manifest |
| `networks-security.yaml` | Security overlay (if source pattern has one) |
| `system-security.yaml` | Security overlay (if source pattern has one) |
| `deployment-security.yaml` | Security overlay (if source pattern has one) |

## Pattern Directory Structure

### Network patterns

```
patterns/networks/<region>/<pattern-id>/
  pattern.meta.yaml      # Metadata and composition contract
  networks.yaml          # Standalone network topology
  contexts/
    _context.yaml        # Context metadata
    provenance.yaml      # Source citations
    sources/
      doc-inventory.yaml
    diagrams/
      _index.yaml
```

### Product patterns

```
patterns/products/<category>/<pattern-id>/
  pattern.meta.yaml      # Metadata and composition contract
  system.yaml            # Standalone system architecture
  contexts/
    _context.yaml
    provenance.yaml
    sources/
      doc-inventory.yaml
    diagrams/
      _index.yaml
```

## Pattern Catalogs

Browse available patterns:

```bash
# Read network pattern catalog
cat patterns/networks/_catalog.yaml

# Read product pattern catalog
cat patterns/products/_catalog.yaml

# Read deployment catalog
cat deployments/_catalog.yaml
```

## Validate Patterns

```bash
python tools/validate-patterns.py patterns/networks/<region>/<pattern-id>/
python tools/validate-patterns.py patterns/products/<category>/<pattern-id>/
```

## Saving New Patterns

Use `@pattern-manager` agent to save current architecture as a reusable pattern. The agent:
1. Copies `system.yaml` or `networks.yaml` to the pattern directory
2. Creates `pattern.meta.yaml` with version, description, binding points
3. Initializes `contexts/` directory structure
4. Updates the parent `_catalog.yaml`

## Migration

Migrate legacy `.pattern.yaml` files to directory format:

```bash
python tools/migrate-pattern.py <legacy-pattern.yaml> <target-dir>
```
