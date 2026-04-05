<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->

# system.yaml Rules

Schema source of truth: `schemas/system.schema.json`

## Required Top-Level Sections
- `metadata` — name, description, owner, status (all required)
- `contexts` — at least one context
- `containers` — at least one container per context
- `components` — at least one component per container

## Metadata Fields
- `name`: Human-readable system name
- `description`: One-sentence purpose
- `owner`: Team or individual responsible
- `status`: `proposed` | `active` | `deprecated` | `decommissioned` | `example`
- `compliance_frameworks`: Array of framework IDs (e.g., `PCI-DSS`, `SOC2`, `GDPR`)
- `confidence_threshold`: 0.0–1.0, default 0.95

## Entity Rules
- Every `container` must reference a valid `context_id`
- Every `component` must reference a valid `container_id`
- `component_type` enum: `api`, `service`, `database`, `data_store`, `message_broker`, `gateway`, `ui`, `batch`, `function`, `proxy`, `cache`, `search`, `monitoring`, `logging`, `other`
- Listeners require: `id`, `protocol`, `port`, `tls_enabled`, `authn_mechanism`

## Relationship Rules
- `component_relationships` connect source → target via `target_listener_ref`
- Both `source_component` and `target_component` must resolve to existing component IDs
- `target_listener_ref` must resolve to a listener ID on the target component
- `synchronous`: boolean indicating sync vs async communication
- `data_classification`: `public` | `internal` | `confidential` | `restricted`
