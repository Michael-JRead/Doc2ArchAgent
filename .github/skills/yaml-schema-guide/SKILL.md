---
name: yaml-schema-guide
description: Quick reference for Doc2ArchAgent YAML schema structure, required fields, valid enums, and naming conventions
allowed-tools: ['read']
---

# Architecture YAML Schema Guide

Consolidated reference for all Doc2ArchAgent YAML schemas. JSON Schema files live in `schemas/`.

## Schema Files

| Schema | File | Validates |
|--------|------|-----------|
| System | `schemas/system.schema.json` | Contexts, containers, components, listeners, relationships |
| System Security | `schemas/system-security.schema.json` | CIA triad, TLS, auth, compliance overlay |
| Networks | `schemas/networks.schema.json` | Network zones, infrastructure resources |
| Networks Security | `schemas/networks-security.schema.json` | Zone segmentation, IDS, ACL rules |
| Deployment | `schemas/deployment.schema.json` | Zone placements |
| Deployment Security | `schemas/deployment-security.schema.json` | Runtime security (image signing, read-only FS) |
| Provenance | `schemas/provenance.schema.json` | Source citations and confidence scores |
| Pattern Meta | `schemas/pattern-meta.schema.json` | Pattern metadata and composition contract |
| Manifest | `schemas/manifest.schema.json` | Deployment composition spec |
| Context | `schemas/context.schema.json` | C4 context definitions |
| Doc Inventory | `schemas/doc-inventory.schema.json` | Document inventory for extraction |
| Diagram Index | `schemas/diagram-index.schema.json` | Diagram catalog |

## Naming Conventions

All YAML entity IDs MUST use **kebab-case**: `^[a-z][a-z0-9]*(-[a-z0-9]+)*$`

Examples: `payment-gateway`, `prod-us-east`, `private-app-tier`

File names: lowercase with hyphens (e.g., `payment-platform.yaml`, `prod-us-east.yaml`)

## Valid Enums

### Entity Status
`proposed` | `active` | `deprecated` | `decommissioned`

### Deployment Status
`proposed` | `approved` | `active` | `deprecated`

### Trust Levels
`trusted` | `semi_trusted` | `untrusted`

### Entity Types (C4)
- **Context**: `internal` | `external`
- **Container**: `service` | `database` | `message-broker` | `cache` | `gateway` | `web-app` | `mobile-app` | `file-store` | `function` | `queue` | `topic`
- **Component**: `module` | `library` | `class` | `interface` | `service` | `handler` | `controller` | `repository` | `adapter`

### Listener Protocols
`http` | `https` | `grpc` | `grpcs` | `tcp` | `tls` | `udp` | `ws` | `wss` | `amqp` | `amqps` | `mqtt` | `mqtts` | `jdbc` | `odbc` | `ldap` | `ldaps` | `ssh` | `sftp` | `ftp` | `ftps` | `smtp` | `smtps` | `dns` | `nfs` | `custom`

### Authentication Methods
`none` | `basic` | `bearer` | `oauth2` | `mtls` | `api_key` | `saml` | `kerberos` | `ldap` | `certificate` | `custom`

### CIA Triad Levels
`low` | `medium` | `high` | `critical`

### Network Zone Types
`dmz` | `private` | `public` | `management` | `data` | `external`

## Core YAML Structures

### system.yaml (minimal)

```yaml
system:
  id: payment-platform
  name: Payment Platform
  version: "1.0.0"

  contexts:
    - id: payment-platform
      name: Payment Platform
      type: internal
      description: Processes credit card payments
      status: active

  containers:
    - id: payment-gateway
      name: Payment Gateway
      context_ref: payment-platform
      type: service
      technology: Java 17
      status: active
      listeners:
        - id: api
          port: 8443
          protocol: https

  components:
    - id: payment-controller
      name: Payment Controller
      container_ref: payment-gateway
      type: controller
      technology: Spring MVC

  relationships:
    - from: payment-gateway
      to: card-processor
      description: Processes payments
      protocol: https
```

### networks.yaml (minimal)

```yaml
networks:
  id: production
  name: Production Network

  zones:
    - id: private-app-tier
      name: Private Application Tier
      type: private
      trust_level: trusted
      description: Internal application servers

  infrastructure_resources: []
```

### deployment.yaml (minimal)

```yaml
deployment:
  id: prod-us-east
  system_ref: payment-platform
  networks_ref: production
  environment: production

  placements:
    - container_ref: payment-gateway
      zone_ref: private-app-tier
      replicas: 2
```

## File Structure

```
architecture/<system-id>/
  system.yaml           # C4 model
  provenance.yaml       # Source citations
  system-security.yaml  # Security overlay
  deployments/          # Per-environment placements
  diagrams/             # Generated diagrams

architecture/
  networks.yaml         # Shared network zones
  networks-security.yaml # Network security overlay
```
