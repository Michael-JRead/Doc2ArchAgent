---
name: document-ingestion
description: Guide for collecting, converting, and extracting architecture entities from source documents with full provenance tracking
allowed-tools: ['execute', 'read']
---

# Document Ingestion Skill

End-to-end pipeline for converting architecture documents into structured YAML with provenance tracking.

## Pipeline Overview

```
Source Documents → convert-docs.py → classify-sections.py → @doc-extractor → system.yaml + provenance.yaml
```

## Step 1: Convert Documents

Convert PDF, DOCX, HTML, and image files to plain text:

```bash
python tools/convert-docs.py <input-dir> <output-dir> --system-id <name>
```

**Example:**
```bash
python tools/convert-docs.py architecture/docs/ context/payment-platform/ --system-id payment-platform
```

**Output:**
- Converted `.txt` / `.md` files in output directory
- `conversion-report.json` with per-file details (pages, extraction method, quality)

**Supported formats:**
| Format | Engine | Quality |
|--------|--------|---------|
| PDF (text) | PyMuPDF | High (native_text) |
| PDF (scanned) | Tesseract OCR | Medium (ocr) |
| DOCX | python-docx | High (native_text) |
| HTML | BeautifulSoup + html2text | High (native_text) |
| Images | Tesseract OCR / VLM | Low-Medium (ocr/vlm) |
| Visio (.vsdx) | vsdx library | High (diagram_parse) |

## Step 2: Classify Sections

Split documents by architectural concern:

```bash
python tools/classify-sections.py <document> --dry-run
```

**Dry run** shows classification without writing files. When satisfied:

```bash
python tools/classify-sections.py <document> --output-dir patterns/<type>/<id>/contexts/sources/
```

**Classification categories:**
- `network` — Network topology, zones, firewalls, subnets
- `product` — Application architecture, components, containers
- `security` — Authentication, encryption, compliance requirements
- `integration` — APIs, data flows, external system connections
- `operational` — Deployment, monitoring, scaling, DR

## Step 3: Build Document Inventory

Create `doc-inventory.yaml` conforming to `schemas/doc-inventory.schema.json`:

```yaml
documents:
  - id: arch-overview
    title: Architecture Overview
    source_path: architecture/docs/arch-overview.pdf
    converted_path: context/payment-platform/arch-overview.md
    format: pdf
    extraction_method: native_text
    pages: 45
    sections_classified: true
    quality_score: 0.95
```

## Step 4: Extract Entities

The `@doc-extractor` agent reads converted documents and extracts entities. This is the LLM-driven step that follows the **Zero-Hallucination Invariant**:

### Rules

1. **Extract ONLY** facts explicitly stated in source documents
2. **NEVER** infer, assume, or fill in "typical" patterns
3. **Every** extracted entity must have a provenance entry with:
   - `source_document` — Which document
   - `source_section` — Which section/heading
   - `source_quote` — Exact text quoted
   - `extraction_method` — How it was extracted
   - `confidence_score` — Numeric confidence (0-100)
4. **Chunk processing** — Process one document section at a time to prevent cross-contamination
5. **Human approval** — Present extracted entities for user confirmation before writing YAML

### Confidence Routing

| Confidence | Action |
|------------|--------|
| HIGH (90-100) | Auto-present with source citation |
| MEDIUM (70-89) | Present with "needs verification" flag |
| LOW (50-69) | Flag for manual review |
| UNCERTAIN (25-49) | Require user confirmation |
| NOT_STATED (0-24) | Block progress, ask user |

## Detect Available Tools

Before starting, check which conversion tools are installed:

```bash
python tools/detect-tools.py
```

This reports available PDF, OCR, DOCX, and image processing capabilities.
