---
description: Extract architecture entities from documents with zero hallucination
---

Extract architecture entities from the provided documents following the zero-hallucination protocol:

1. **Collect**: Inventory all source documents. For each, record filename, format, page count.

2. **Extract in 4 passes**:
   - **Pass 1 (Prose)**: Extract names, descriptions, ownership from narrative text
   - **Pass 2 (Tables)**: Extract protocols, ports, technologies from structured tables
   - **Pass 3 (Diagrams)**: Parse diagram files for component shapes and connections
   - **Pass 4 (Cross-Reference)**: Merge findings, resolve conflicts, boost confidence

3. **Confidence scoring**: Assign numerical confidence (0.0–1.0) to every field. Only include entities with confidence >= 0.95 (adjustable via `metadata.confidence_threshold`).

4. **Provenance**: Write `provenance.yaml` with per-field source citations including:
   - Source document ID and section
   - Exact supporting quote
   - Character span positions (char_start, char_end) where possible
   - Confidence factor breakdown

5. **Validation**: Run `python tools/validate.py` on the generated system.yaml. Fix any ARCH001–ARCH009 errors before presenting to the user.

6. **Present for review**: Show the extracted architecture with citations. Wait for human approval before finalizing.
