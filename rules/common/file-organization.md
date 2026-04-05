<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->

# File Organization

## Architecture Output
```
architecture/<system-id>/
  system.yaml          # C4 model (contexts, containers, components, relationships)
  provenance.yaml      # Per-field source citations and confidence scores
  deployments/         # Environment-specific zone placements
  diagrams/            # Generated diagrams
  docs/                # Generated documentation
architecture/
  networks.yaml        # Shared network zones and infrastructure
```

## Patterns
```
patterns/
  networks/_catalog.yaml
  networks/<region>/<pattern-id>/
    pattern.meta.yaml, networks.yaml, system.yaml (optional), contexts/, diagrams/
  products/_catalog.yaml
  products/<category>/<pattern-id>/
    pattern.meta.yaml, system.yaml, networks.yaml (optional), contexts/, diagrams/
```

## Deployments
```
deployments/
  _catalog.yaml
  <deployment-id>/
    manifest.yaml                 # Source of truth
    networks.yaml                 # GENERATED
    system.yaml                   # GENERATED
    deployment.yaml               # GENERATED
    *-security.yaml               # GENERATED security overlays
    diagrams/_index.yaml           # Diagram catalog
```

## Protected Directories
Never modify: `schemas/`, `context/*.yaml`, license files.
