<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->

# Provenance Awareness

**Applies to: ALL agents that create or consume architecture data.**

## Core Rule

Always track where information came from. Every architecture entity should be traceable to its origin — whether that's a source document, user input, a pattern library, or an inference that was explicitly confirmed.

## Provenance Sources

| Source Type | How to Cite | Confidence |
|-------------|-------------|------------|
| Source document | `[source: filename, section/page, quote]` | Based on extraction method |
| User input | `[source: user, conversation]` | HIGH (explicit confirmation) |
| Pattern library | `[source: pattern/<pattern-id>]` | HIGH (curated) |
| Inferred | `[source: inferred, requires verification]` | LOW (must be confirmed) |
| Default value | `[source: schema default]` | MEDIUM |

## Confidence Levels

- **HIGH** — Exact text match in source document, or explicit user confirmation
- **MEDIUM** — Interpreted from context with reasonable certainty
- **LOW** — Implied but not explicitly stated
- **UNCERTAIN** — Conflicting information from multiple sources
- **NOT_STATED** — Required field with no source information at all

## When Consuming Provenance

When reading architecture YAML produced by another agent:
- Check `provenance.yaml` for confidence levels
- Flag any `NOT_STATED` or `LOW` confidence fields to the user
- Do not treat low-confidence data as authoritative

## When Producing Provenance

When writing architecture YAML:
- Write corresponding entries in `provenance.yaml`
- Include source references for every extracted entity
- Use the confidence-scoring skill for systematic scoring
