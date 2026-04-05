<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->

# Layer 5 — External Systems, Data Entities, Trust Boundaries

## External Systems
Required if the system integrates with anything outside the organization.

For each external system, capture:
- `name`, `description`
- **Security properties**: `category`, `trust_level`, `data_classification`, `authn_mechanism`, `tls_required`, `sla_tier`, `vendor_security_assessed`, `data_residency`

## Data Entities
Optional — ask: "Do you want to define named data entities for flow annotation?"

For each data entity, capture:
- `name`, `description`, `classification`
- **Regulatory annotations**: `contains_pii`, `contains_phi`, `contains_pci`, `data_subject_type`, `retention_days`, `residency_requirements`, `masking_required`, `origin`, `volume`

## Trust Boundaries
Optional — ask: "Do you want to define trust boundaries now or later?"

For each trust boundary, capture:
- `name`, `description`
- `boundary_type` — `network` | `process` | `privilege` | `jurisdiction` | `vendor`
- **Enforcement details**: `enforcement_mechanism`, `inspection_enabled`, `bidirectional`

## Sequence
For each resource type, capture all instances before moving to the next type.
After finishing each type, ask: "Any more [type]? Or shall we move on?"
