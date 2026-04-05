<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->
---
name: brainstorming
description: Use when starting any new architecture modeling task, adding a new system, or when the user describes what they want to build — enforces design-first workflow before any implementation or extraction begins
allowed-tools:
  - execute
  - edit
---

# Brainstorming — Design Before Implementation

## Overview

Understand the problem fully before producing any architecture YAML. Do NOT jump into extraction, modeling, or diagram generation until you have a design the user has approved.

**Core principle:** No implementation without an approved design.

## Hard Gate

```
DO NOT invoke any extraction agent, write any YAML, generate any diagram,
or take any implementation action until you have presented a design
and the user has approved it.
```

## The Process

### Step 1: Explore Project Context

Before asking questions, gather what already exists:
- Check `architecture/` for existing system YAML
- Check `deployments/` for existing deployment manifests
- Check `patterns/` for applicable patterns
- Check `context/` for threat rules and compliance mappings
- Read any documents the user has provided or referenced

### Step 2: Ask Clarifying Questions

Ask questions **one at a time** to understand:
- What system or capability is being modeled?
- What documentation sources are available?
- What is the deployment context (cloud provider, regions, zones)?
- What compliance frameworks apply (PCI-DSS, SOC2, HIPAA, GDPR)?
- What level of detail is needed (C4 context only, or full component-level)?

Prefer multiple-choice questions when the options are knowable:
```
What C4 depth do you need?
1. Context level only (systems and external actors)
2. Container level (services, databases, message queues)
3. Full component level (listeners, internal modules)
```

### Step 3: Propose Approaches

Present 2-3 approaches with trade-offs:
```
## Approach A: Full Extraction Pipeline
- Run @doc-collector → @doc-extractor → @architect
- Pros: Maximum coverage, verifiable provenance
- Cons: Requires complete documentation

## Approach B: Pattern-Based Composition
- Start from existing patterns in patterns/products/
- Pros: Fast, reuses validated templates
- Cons: May miss system-specific details

## Approach C: Hybrid (Recommended)
- Apply pattern for infrastructure, extract for business logic
- Pros: Balanced speed and accuracy
- Cons: Requires careful merge of pattern and extraction data
```

### Step 4: Present Design in Sections

Break the design into digestible sections. Seek approval after each:

1. **System boundary and contexts** — What's in scope, what's external?
2. **Container inventory** — What services, databases, queues exist?
3. **Network topology** — What zones, what trust boundaries?
4. **Security posture** — Authentication, encryption, compliance?
5. **Deployment strategy** — Where does each container land?

Keep each section under 300 words. Wait for user approval before proceeding.

### Step 5: Write Design Document

Save the approved design to:
```
docs/architecture-designs/YYYY-MM-DD-<system-id>-design.md
```

Include: system boundary, container inventory, key relationships, security requirements, open questions.

### Step 6: Self-Review

Before showing the user, verify:
- [ ] No placeholders ("TBD", "TODO", "similar to...")
- [ ] No contradictions between sections
- [ ] Every container has at least one relationship
- [ ] Security requirements are specific, not vague
- [ ] Compliance frameworks are correctly mapped

### Step 7: User Review

Present the design document for final approval. Only after approval, proceed to:
- Invoke **writing-plans** skill to create an implementation plan, OR
- Hand off to `@architect` for interactive modeling

## Red Flags — You Are Rationalizing If You Think:

| Thought | Reality |
|---------|---------|
| "The docs are clear enough, let me just start extracting" | Extraction without design = hallucination risk |
| "I'll design as I go" | Architecture drift. Design first. |
| "The user seems impatient" | Bad design costs more than 5 minutes of questions |
| "This is a simple system" | Simple systems have hidden complexity. Ask. |
| "I already know this architecture" | You know what you've read. Verify with the user. |

## Integration

- **Next step:** `writing-plans` (to create implementation plan) or `@architect` (for interactive modeling)
- **Required instincts:** zero-hallucination, user-confirmation, provenance-awareness
