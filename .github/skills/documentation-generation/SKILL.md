---
name: documentation-generation
description: Generate HLDD, executive summaries, and stakeholder documentation from architecture YAML in Markdown or Confluence format
allowed-tools: ['read', 'edit']
---

# Documentation Generation Skill

Guides the generation of human-readable architecture documentation from structured YAML models.

## When to Use
- User asks for documentation generation
- `@doc-writer` agent is invoked
- Creating HLDD, executive summaries, or stakeholder briefs

## Document Types

| Type | Audience | Format | Content |
|------|----------|--------|---------|
| HLDD | Architects, Engineers | Markdown or Confluence | Full 12-section architecture document |
| Executive Summary | Executives, Managers | Markdown | Non-technical overview with key metrics |
| Security Brief | Security Team | Markdown | Security findings, STRIDE results, compliance |
| Network Brief | Network Team | Markdown | Zone topology, ACL rules, crossing report |

## Files in This Skill
- `hldd-template.md` — 12-section HLDD structure and content guidance
- `confluence-format.md` — Confluence storage format (XHTML + ac:macros)
