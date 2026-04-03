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

The `manifest.yaml` declares which patterns to compose.

### Single-Network Manifest (backward compatible)

```yaml
manifest:
  id: mq-prod-us-east
  name: MQ Production US East
  environment: production
  region: us-east-1

  network:                          # Singular form (backward compat)
    pattern_ref: standard-3tier
    version: "1.0.0"
    id_prefix: prod

  products:
    - pattern_ref: ibm-mq
      version: "1.0.0"
      id_prefix: mq
      context_name: MQ Production Messaging

  placements:
    - container_ref: mq-mq-infrastructure
      zone_ref: prod-private-app-tier
      replicas: 2
```

### Multi-Network Manifest

Use `networks:` (plural) to compose multiple network patterns. Each entry has a `purpose` indicating who it serves.

```yaml
manifest:
  id: payment-prod-multi
  name: Payment Platform Production
  environment: production

  networks:                         # Plural form for multi-network
    - pattern_ref: standard-3tier
      id_prefix: app
      purpose: application          # application/human/hybrid/management/other
      version: "1.0.0"
    - pattern_ref: user-access-vpn
      id_prefix: user
      purpose: human
      version: "1.0.0"

  products:
    - pattern_ref: payment-gateway
      id_prefix: pay
    - pattern_ref: ibm-mq
      id_prefix: mq

  placements:
    - container_ref: pay-api-gateway
      zone_ref: app-dmz
    - container_ref: pay-admin-console
      zone_ref: user-admin-zone
    - container_ref: mq-mq-infrastructure
      zone_ref: mq-mq-isolation     # Zone from product pattern (unified)

  cross_network_links:               # Explicit cross-network zone connections
    - source_zone: user-admin-zone
      target_zone: app-private-app-tier
      direction: bidirectional
      description: "Admin access to application tier"
```

**Rules:**
- Use `network:` (singular) OR `networks:` (plural), never both
- Each `id_prefix` must be globally unique across all patterns
- `cross_network_links` connect zones from different network patterns
- Product patterns with `networks.yaml` contribute zones to the composed output

## ID Prefixing

Every pattern gets a unique prefix to avoid ID collisions when composing:

- Network pattern IDs: `<network.id_prefix>-<original-id>` (e.g., `prod-private-app-tier`)
- Product pattern IDs: `<product.id_prefix>-<original-id>` (e.g., `mq-queue-manager`)
- Placement references must use prefixed IDs

## Generated Output

Compose writes these files alongside the manifest (all marked `DO NOT EDIT`):

| File | Content |
|------|---------|
| `networks.yaml` | Composed network topology from all network patterns + product-contributed zones |
| `system.yaml` | Composed system architecture from all product patterns + network-contributed containers |
| `deployment.yaml` | Zone placements from manifest |
| `app-dataflows.yaml` | Composed application-to-application flows (if any patterns have them) |
| `human-dataflows.yaml` | Composed human user-facing flows (if any patterns have them) |
| `networks-security.yaml` | Security overlay for networks |
| `system-security.yaml` | Security overlay for system |
| `deployment-security.yaml` | Security overlay for deployment |

## Pattern Directory Structure (Unified)

Any pattern can now include both `networks.yaml` and `system.yaml` plus dataflow files. Only the primary file is required; all others are optional.

### Network patterns

```
patterns/networks/<region>/<pattern-id>/
  pattern.meta.yaml      # Metadata, audience, files list
  networks.yaml          # PRIMARY — zone definitions
  system.yaml            # OPTIONAL — infra components as C4 containers (e.g., WAF, LB)
  app-dataflows.yaml     # OPTIONAL — application-to-application flows
  human-dataflows.yaml   # OPTIONAL — human user-facing flows
  contexts/
    _context.yaml
    provenance.yaml
    sources/
      doc-inventory.yaml
    diagrams/
      _index.yaml
```

### Product patterns

```
patterns/products/<category>/<pattern-id>/
  pattern.meta.yaml      # Metadata, audience, files list
  system.yaml            # PRIMARY — containers, components, relationships
  networks.yaml          # OPTIONAL — product-specific zones (e.g., MQ isolation)
  app-dataflows.yaml     # OPTIONAL — application-to-application flows
  human-dataflows.yaml   # OPTIONAL — human user-facing flows
  contexts/
    _context.yaml
    provenance.yaml
    sources/
      doc-inventory.yaml
    diagrams/
      _index.yaml
```

### Dataflow files

Both `app-dataflows.yaml` and `human-dataflows.yaml` follow `schemas/dataflows.schema.json`:
- **Zone-level flows:** `source_zone` / `target_zone` (references zones in `networks.yaml`)
- **Component-level flows:** `source_component` / `target_component` (references components in `system.yaml`)
- Both can coexist in the same file
- Each file declares `audience: application|human|hybrid` in `dataflow_metadata`

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
