<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->

# STRIDE Threat Analysis Methodology

Every data flow crossing a trust boundary is automatically flagged for STRIDE analysis. This is deterministic: based on schema fields, not AI inference.

## Per-Relationship STRIDE Checks

For each `component_relationship` with a `target_listener_ref`, evaluate all six categories:

### Spoofing
- `authn_mechanism == "none"` → `✗ [HIGH]` No authentication
- `authn_mechanism == "api_key"` on internet-facing → `⚠ [MEDIUM]` Weak auth for boundary
- Strong authn (`oauth2`, `mtls`, `certificate`) → `✓` Documented

### Tampering
- `data_classification == "confidential"` AND `tls_enabled == false` → `✗ [HIGH]` No transport integrity
- `tls_enabled == true` → `✓` Transport integrity protected

### Repudiation
- Crosses trust boundary AND no logging in target zone → `⚠ [MEDIUM]` No audit trail
- Check `infrastructure_resources` for `resource_type: logging` → `✓` Audit present

### Information Disclosure
- `tls_enabled == false` on internet-facing → `✗ [HIGH]` Data exposed in transit
- `tls_enabled == false` on internal → `⚠ [MEDIUM]` Unencrypted internal data
- `data_classification == "confidential"` over unencrypted channel → `✗ [HIGH]`

### Denial of Service
- Internet-facing listener without WAF → `⚠ [MEDIUM]` Potential DoS target
- Check `infrastructure_resources` for `resource_type: waf`

### Elevation of Privilege
- `authz_required == false` → `⚠ [MEDIUM]` No authorization
- `authz_required == false` AND internet-facing → `✗ [HIGH]`
- `authz_model == "none"` AND sensitive data → `⚠ [MEDIUM]`

## DFD Element Mapping

| DFD Element | Schema Mapping | STRIDE Applicability |
|---|---|---|
| External Entity | `external_systems[]` | Spoofing |
| Process | `components` (api, service, web_app, background_service) | All six |
| Data Store | `components` (database, cache, message_queue) | T, R, I, D |
| Data Flow | `component_relationships[]` | T, I, D |
| Trust Boundary | `trust_boundaries[]` + zone crossings | All at crossings |

## Report Format
```
| Relationship | S | T | R | I | D | E | Risk Level |
|---|---|---|---|---|---|---|---|
| user → api-gw | ✓ | ✓ | ⚠ | ✓ | ⚠ | ✓ | MEDIUM |
```
