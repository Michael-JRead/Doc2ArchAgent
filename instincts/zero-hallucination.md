<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->

# Zero-Hallucination Invariant

**Applies to: ALL agents, ALL interactions.**

This is the foundational principle that governs EVERYTHING in the Doc2ArchAgent pipeline.

## The Invariant

```
For EVERY element E in output YAML:
  There EXISTS a source_reference S in the input documents
  WHERE E is a direct extraction (not inference) from S
  AND S is verifiable by human review.
```

## Rules (Non-Negotiable)

1. **Extract ONLY facts explicitly stated** in source documents or confirmed by the user. If a fact is not written in the document, it does not exist.
2. **Do NOT infer, assume, or generate information** not present in the text. Do not fill gaps with "reasonable" guesses.
3. **Every extracted entity MUST include a source citation:** `[source: filename, section/page]`
4. **Assign confidence to every field** using the multi-factor computation in the confidence-scoring skill.
5. **If a required field is NOT found in any document** — mark it `NOT_STATED` and ask the developer. Never fill it in silently.
6. **If you cannot cite a source for a fact, do NOT extract it.** No citation = no extraction.
7. **Never fill in required fields silently. Never guess. Never infer.** When in doubt, ask.

## Constrained Extraction Controls

1. **EXTRACT ONLY** — Never reason about architecture. Only extract and structure what is explicitly stated. If you find yourself thinking "this system probably has a load balancer," STOP. If it's not in the document, it doesn't exist.
2. **STRUCTURED OUTPUT** — For every extraction, output a structured table matching the target schema fields. Never free-form describe entities. Every field maps to a schema field or is marked NOT_STATED.
3. **STRICT EXTRACTION PROMPT** — "Extract ONLY entities that are EXPLICITLY stated. If a component is implied but not named, mark `is_inferred: true`. If data classification is not stated, use UNKNOWN. Never infer protocols, technologies, or data types not explicitly mentioned."
4. **CHUNKED EXTRACTION** — Process each document section independently. Do NOT let information from Section A influence extraction from Section B. After all sections are extracted, cross-reference in a separate pass.
5. **SOURCE QUOTING** — For every extracted entity, quote the exact source text passage that supports it. If you cannot produce a direct quote, the extraction confidence CANNOT be HIGH.

## Anti-Patterns (NEVER DO)

- "I'll add a Redis cache since most systems have one" — HALLUCINATION
- "The system probably uses OAuth2" — INFERENCE, not extraction
- "I'll assume this is TLS 1.3" — ASSUMPTION without source
- Silently picking one value over another when sources conflict — present BOTH and ask

## Red Flags — You Are Rationalizing If You Think:

| Thought | Reality |
|---------|---------|
| "This is standard architecture, I can fill it in" | Standard for whom? Extract what's stated. |
| "The doc implies this exists" | Implication ≠ explicit statement. Mark NOT_STATED. |
| "I'll add it now and verify later" | Later never comes. Unverified = hallucinated. |
| "The user will catch any mistakes" | You are the first line of defense. Don't outsource accuracy. |
| "It's just a small assumption" | Small assumptions compound into wrong threat models. |
| "Every system has a load balancer" | If the document doesn't say it, it doesn't exist. |

## What "100% Accuracy" Means

- Every element in the output exists in a source document (zero fabrication)
- Every element is correctly typed and connected per the source material (zero misrepresentation)
- When the pipeline doesn't know something, it says so explicitly (zero silent assumptions)
- The human reviewer can verify every element by following provenance links (full traceability)
- The output is a faithful, verifiable *subset* of what the source documents state — it may be incomplete (because the docs are incomplete), but it is NEVER wrong about what it does include
