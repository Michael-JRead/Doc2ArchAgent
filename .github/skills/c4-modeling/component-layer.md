<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->

# Layer 3 — Components

Components are the individual deployable services, applications, or processes within a container. Each component has its own technology, platform, resiliency, and listeners.

## Examples
- "MQ Server" (message_queue)
- "API Gateway" (api_gateway)
- "Order DB" (database)
- "Event Processor" (background_service)

## Capture Sequence

For each container:

### 1. Define Components
For each component, capture:
- `name`, `description`, `component_type`, `technology`, `platform`, `resiliency`
- **Security properties** (ask for each):
  - `confidentiality`, `integrity`, `availability` — CIA triad: `critical` | `high` | `medium` | `low`
  - `dfd_element_type` — `process` | `data_store` | `external_entity` (for STRIDE-per-element)
  - `stores_data`, `processes_pii` — for encryption/compliance rules
  - `encryption_at_rest`, `encryption_key_management` — for data-storing components
  - `audit_logging` — for compliance (HIPAA, PCI-DSS Req 10)

### 2. Define Listeners
For each component, capture its listeners:
- `protocol`, `port`, `tls_enabled`, `tls_version_min`
- `authn_mechanism` — `none` | `api_key` | `oauth2` | `mtls` | `certificate` | `basic` | `saml` | `custom`
- `authz_required`, `authz_model`
- **Security properties**: `cipher_suite_policy`, `rate_limiting_enabled`, `exposure`, `api_type`, `admin_interface`, `error_detail_exposure`, `cors_policy`

### 3. Component Relationships
For each relationship:
- Select source component (or external system)
- Select target component
- Display target's listeners; ask which listener to target
- Capture: `label`, `synchronous`, `data_entities`, `data_classification`
- **Security properties**: `interaction_type`, `mutual_authentication`, `input_validation`, `replay_protection`

### 4. Update Container Relationships
Now that listeners exist, revisit each container relationship and resolve `target_listener_ref`.

Capture all components for a container before moving to the next.
