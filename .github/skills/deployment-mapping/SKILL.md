---
name: deployment-mapping
description: Place containers and components into network zones, compute derived links, and detect zone crossings for deployment environments
allowed-tools: ['read', 'edit']
---

# Deployment Mapping Skill

Guides the process of placing architecture components into network zones for specific deployment environments.

## When to Use
- User asks to deploy/place containers into zones
- `@deployer` agent is invoked
- Creating or modifying deployment YAML

## Files in This Skill
- `zone-placement.md` — Container-to-zone placement logic and multi-network awareness
- `derived-links.md` — Automatic link computation from component relationships and zone placements
