---
name: confidence-scoring
description: Assess and enrich entity confidence scores in provenance.yaml using the deterministic scoring framework
allowed-tools: ['execute', 'read']
---

# Confidence Scoring Skill

Assess confidence levels for extracted architecture entities using the deterministic scoring framework. Confidence scores determine whether entities can be auto-accepted or require human verification.

## Commands

### Score a single extraction

```bash
python tools/confidence.py --method native_text --field-present --source-count 2
```

### Score with custom threshold

```bash
python tools/confidence.py --threshold 90 --method ocr --field-present
```

### Library usage (in Python tools)

```python
from tools.confidence import ConfidenceScorer, ExtractionMethod

scorer = ConfidenceScorer(default_threshold=95)
score = scorer.score(
    method=ExtractionMethod.NATIVE_TEXT,
    field_present=True,
    source_count=2,
)
# Returns: {"score": 97, "level": "HIGH", "meets_threshold": True}
```

## Extraction Method Hierarchy

Base confidence scores by extraction method (0-100):

| Method | Base Score | Description |
|--------|-----------|-------------|
| `user_provided` | 100 | Manually entered by user |
| `native_text` | 95 | Direct text extraction (PyMuPDF, python-docx) |
| `structurizr` | 95 | Structurizr DSL ingestion |
| `k8s_manifest` | 95 | Kubernetes YAML ingestion |
| `terraform` | 95 | Terraform HCL ingestion |
| `openapi` | 95 | OpenAPI spec ingestion |
| `diagram_parse` | 90 | Draw.io / Visio XML parsing |
| `table` | 85 | PDF table extraction (pdfplumber) |
| `layout_detection` | 80 | ML layout analysis (DocLayout-YOLO) |
| `cross_ref` | 75 | Cross-document entity resolution |
| `ocr` | 70 | OCR text extraction (Tesseract) |
| `vlm` | 65 | Vision Language Model analysis |
| `inferred` | 50 | Derived from other extracted data |

## Score Adjustments

The base score is adjusted by these factors:

| Factor | Adjustment | Condition |
|--------|-----------|-----------|
| Field present | +0 | Value explicitly found in source |
| Field absent | -10 | Value not found, using default |
| Multiple sources (2+) | +3 | Corroborated across documents |
| Multiple sources (3+) | +5 | Strongly corroborated |
| Cross-reference match | +5 | Entity resolved across documents |

## Confidence Levels

| Level | Score Range | Action |
|-------|------------|--------|
| `HIGH` | 90-100 | Auto-present to user, no verification needed |
| `MEDIUM` | 70-89 | Present with verification prompt |
| `LOW` | 50-69 | Flag for manual review, block auto-inclusion |
| `UNCERTAIN` | 25-49 | Requires human input before proceeding |
| `NOT_STATED` | 0-24 | Block progress, must be provided by user |

## Default Threshold

The default confidence threshold is **95%** (0.95). Entities below this threshold require human verification before inclusion in the architecture model. Users can adjust via `metadata.confidence_threshold` in the YAML files.

## Provenance Integration

Every scored entity must have a corresponding entry in `provenance.yaml`:

```yaml
provenance:
  - entity_id: payment-gateway
    field: technology
    value: "Java 17"
    source_document: "architecture-overview.pdf"
    source_section: "Technology Stack"
    source_quote: "The payment gateway is built on Java 17"
    extraction_method: native_text
    confidence_score: 95
    confidence_level: HIGH
```

## Zero-Hallucination Rule

- `HIGH` confidence: Auto-present, cite source
- `MEDIUM` confidence: Present with "needs verification" flag
- `LOW` / `UNCERTAIN`: Block auto-inclusion, require user confirmation
- `NOT_STATED`: Stop progress, ask user to provide the value
- **NEVER** infer or assume values not explicitly stated in source documents
