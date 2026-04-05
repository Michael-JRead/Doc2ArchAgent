<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->

# Layer 1 — Contexts

Contexts represent the highest-level systems and their relationships. Each context is either an internal system you control or an external system you interact with.

## Examples
- "Order Management" (internal)
- "Payment Gateway" (external partner)
- "Customer Portal" (internal)
- "Identity Provider" (external SaaS)

## Capture Sequence

### 1. System Metadata
Ask for and capture:
- `name` — Human-readable system name
- `description` — One-sentence purpose
- `owner` — Team or individual responsible
- `compliance_frameworks` — Array (e.g., PCI-DSS, SOC2, GDPR)
- `status` — `proposed` | `active` | `deprecated` | `decommissioned`

### 2. Define Each Context
For each context, capture:
- `name`, `description`
- `internal` flag (true = you control it, false = external)
- If external: link to an external system entry (defined in Layer 5)
- If internal: containers will be defined in Layer 2

Capture ALL contexts before moving on.

### 3. Context Relationships
Dependency relationships between contexts. For each:
- Select source context
- Select target context
- `label` — describes the relationship (e.g., "sends orders to", "authenticates via")
- `bidirectional` — default: false

These have no listener/protocol detail — they appear only in the Context diagram.

## Output
Write to `architecture/<system-id>/system.yaml`:
```yaml
metadata:
  name: ...
  description: ...
  owner: ...
  status: active
contexts:
  - id: payment-platform
    name: Payment Platform
    description: ...
    internal: true
context_relationships:
  - id: ctx-payment-to-bank
    source_context: payment-platform
    target_context: bank-integration
    label: sends payment requests to
    bidirectional: false
```
