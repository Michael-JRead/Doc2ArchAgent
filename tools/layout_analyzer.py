#!/usr/bin/env python3
# Copyright (c) 2026 Michael J. Read. All rights reserved.
# SPDX-License-Identifier: BUSL-1.1
"""Layout-detection-first document analysis pipeline for Doc2ArchAgent.

Renders PDF/image pages, runs ML layout detection (DocLayout-YOLO), and routes
detected regions to specialized extractors (text, tables, figures, formulas).

Also includes schema-driven extraction templates for common architecture
document formats (HLD, LLD, network diagrams).

Usage:
    python tools/layout_analyzer.py input.pdf --output-dir ./extracted
    python tools/layout_analyzer.py input.pdf --schema hld --format json

Dependencies (optional — install via: pip install doc2archagent[ml]):
    doclayout-yolo, onnxruntime, Pillow

Falls back gracefully to basic extraction when ML deps are not available.
"""

import argparse
import json
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Region types from DocLayNet / DocLayout-YOLO
# ---------------------------------------------------------------------------

class RegionType:
    TEXT = "Text"
    PICTURE = "Picture"
    CAPTION = "Caption"
    SECTION_HEADER = "Section-header"
    FOOTNOTE = "Footnote"
    FORMULA = "Formula"
    TABLE = "Table"
    LIST_ITEM = "List-item"
    PAGE_HEADER = "Page-header"
    PAGE_FOOTER = "Page-footer"
    TITLE = "Title"


class DetectedRegion:
    """A detected region on a document page."""

    def __init__(self, region_type: str, confidence: float, bbox: list,
                 page_index: int, text: str = "", metadata: dict | None = None):
        self.region_type = region_type
        self.confidence = confidence
        self.bbox = bbox
        self.page_index = page_index
        self.text = text
        self.metadata = metadata or {}


class PageAnalysis:
    """Analysis results for a single page."""

    def __init__(self, page_index: int, regions: list | None = None,
                 full_text: str = "", tables: list | None = None,
                 figures: list | None = None, headers: list | None = None):
        self.page_index = page_index
        self.regions = regions or []
        self.full_text = full_text
        self.tables = tables or []
        self.figures = figures or []
        self.headers = headers or []


class DocumentAnalysis:
    """Complete analysis of a document."""

    def __init__(self, source_file: str, pages: list,
                 schema_detected: str = "", extraction_method: str = "basic",
                 metadata: dict | None = None):
        self.source_file = source_file
        self.pages = pages
        self.schema_detected = schema_detected
        self.extraction_method = extraction_method
        self.metadata = metadata or {}


# ---------------------------------------------------------------------------
# Layout detection
# ---------------------------------------------------------------------------

def _load_yolo_model():
    """Load DocLayout-YOLO model if available."""
    try:
        from doclayout_yolo import YOLOv10
    except ImportError:
        return None

    model_paths = [
        Path(__file__).parent / "models" / "doclayout_yolo_docstructbench.pt",
        Path.home() / ".cache" / "doc2archagent" / "doclayout_yolo.pt",
    ]
    for p in model_paths:
        if p.exists():
            try:
                return YOLOv10(str(p))
            except Exception:
                continue
    return None


def detect_layout(page_image, page_index: int = 0, model=None) -> list[DetectedRegion]:
    """Detect layout regions in a page image using YOLO.

    Args:
        page_image: PIL Image or image path.
        page_index: Page number (0-indexed).
        model: Pre-loaded YOLO model (or None to auto-load).

    Returns:
        List of detected regions sorted by vertical position.
    """
    if model is None:
        model = _load_yolo_model()
    if model is None:
        return []

    try:
        results = model.predict(page_image, conf=0.25)
    except Exception:
        return []

    regions = []
    for r in results:
        if not hasattr(r, "boxes") or r.boxes is None:
            continue
        names = getattr(r, "names", {})
        for box in r.boxes:
            label_idx = int(box.cls[0]) if box.cls is not None else -1
            conf = float(box.conf[0]) if box.conf is not None else 0.0
            label = names.get(label_idx, f"class_{label_idx}")
            bbox = box.xyxy[0].tolist() if box.xyxy is not None else []
            regions.append(DetectedRegion(
                region_type=label,
                confidence=conf,
                bbox=bbox,
                page_index=page_index,
            ))

    # Sort by vertical position (top to bottom)
    regions.sort(key=lambda r: r.bbox[1] if len(r.bbox) >= 2 else 0)
    return regions


# ---------------------------------------------------------------------------
# Region extractors
# ---------------------------------------------------------------------------

def extract_text_region(page_image, region: DetectedRegion) -> str:
    """Extract text from a detected text region using OCR."""
    try:
        from PIL import Image
        import pytesseract
    except ImportError:
        return ""

    if not isinstance(page_image, Image.Image):
        page_image = Image.open(page_image)

    if len(region.bbox) >= 4:
        try:
            x1, y1, x2, y2 = [int(v) for v in region.bbox[:4]]
        except (ValueError, TypeError):
            cropped = page_image
        else:
            cropped = page_image.crop((x1, y1, x2, y2))
    else:
        cropped = page_image

    try:
        return pytesseract.image_to_string(cropped).strip()
    except Exception:
        return ""


def extract_table_region(page_image, region: DetectedRegion) -> dict:
    """Extract a table from a detected region.

    Tries pdfplumber-style extraction on the cropped region,
    falling back to OCR-based table parsing.
    """
    try:
        from PIL import Image
    except ImportError:
        return {"headers": [], "rows": [], "raw_text": ""}

    if not isinstance(page_image, Image.Image):
        page_image = Image.open(page_image)

    if len(region.bbox) >= 4:
        try:
            x1, y1, x2, y2 = [int(v) for v in region.bbox[:4]]
        except (ValueError, TypeError):
            cropped = page_image
        else:
            cropped = page_image.crop((x1, y1, x2, y2))
    else:
        cropped = page_image

    # Try OCR and parse as table
    try:
        import pytesseract
        text = pytesseract.image_to_string(cropped).strip()
    except Exception:
        text = ""

    # Simple heuristic: lines with | or tab separators
    lines = [l for l in text.split("\n") if l.strip()]
    if not lines:
        return {"headers": [], "rows": [], "raw_text": text}

    # Detect separator
    sep = "|" if "|" in text else "\t"
    rows = []
    for line in lines:
        if set(line.strip()) <= {"-", "|", "+", " ", "="}:
            continue  # Skip separator lines
        cells = [c.strip() for c in line.split(sep) if c.strip()]
        if cells:
            rows.append(cells)

    headers = rows[0] if rows else []
    data_rows = rows[1:] if len(rows) > 1 else []

    return {
        "headers": headers,
        "rows": data_rows,
        "raw_text": text,
    }


# ---------------------------------------------------------------------------
# Schema-driven extraction templates
# ---------------------------------------------------------------------------

EXTRACTION_TEMPLATES = {
    "hld": {
        "name": "High-Level Design Document",
        "expected_sections": [
            "system_overview", "architecture_overview", "components",
            "data_flow", "security", "deployment", "interfaces",
        ],
        "key_fields": {
            "system_name": {"keywords": ["system name", "application name", "project name"]},
            "owner": {"keywords": ["owner", "team", "responsible"]},
            "components": {"keywords": ["component", "service", "module", "subsystem"]},
            "technology": {"keywords": ["technology", "stack", "framework", "language"]},
            "deployment": {"keywords": ["deployment", "infrastructure", "hosting", "cloud"]},
        },
    },
    "lld": {
        "name": "Low-Level Design Document",
        "expected_sections": [
            "component_design", "database_schema", "api_design",
            "sequence_diagrams", "error_handling", "security_controls",
        ],
        "key_fields": {
            "components": {"keywords": ["class", "module", "service", "endpoint"]},
            "apis": {"keywords": ["api", "endpoint", "route", "method"]},
            "database": {"keywords": ["table", "schema", "column", "index"]},
            "protocols": {"keywords": ["protocol", "http", "grpc", "amqp", "mqtt"]},
        },
    },
    "network": {
        "name": "Network Architecture Document",
        "expected_sections": [
            "network_zones", "firewall_rules", "routing",
            "load_balancing", "dns", "vpn",
        ],
        "key_fields": {
            "zones": {"keywords": ["zone", "dmz", "vlan", "subnet", "segment"]},
            "firewalls": {"keywords": ["firewall", "acl", "rule", "allow", "deny"]},
            "routing": {"keywords": ["route", "gateway", "nat", "proxy"]},
            "addresses": {"keywords": ["ip", "cidr", "address", "range"]},
        },
    },
    "security": {
        "name": "Security Architecture Document",
        "expected_sections": [
            "authentication", "authorization", "encryption",
            "key_management", "compliance", "audit",
        ],
        "key_fields": {
            "authn": {"keywords": ["authentication", "login", "sso", "oauth", "saml", "ldap"]},
            "authz": {"keywords": ["authorization", "rbac", "permission", "role", "policy"]},
            "encryption": {"keywords": ["encryption", "tls", "ssl", "certificate", "cipher"]},
            "compliance": {"keywords": ["compliance", "pci", "sox", "gdpr", "hipaa", "nist"]},
        },
    },
}


def detect_document_schema(text: str) -> tuple[str, float]:
    """Auto-detect which extraction template best fits the document.

    Returns:
        Tuple of (template_name, confidence_score).
    """
    text_lower = text.lower()
    scores: dict[str, float] = {}

    for tmpl_name, tmpl in EXTRACTION_TEMPLATES.items():
        score = 0.0
        for field_name, field_def in tmpl["key_fields"].items():
            for kw in field_def["keywords"]:
                count = text_lower.count(kw)
                if count > 0:
                    score += min(count, 5)  # Cap per-keyword contribution

        # Bonus for section heading matches
        for section in tmpl["expected_sections"]:
            section_words = section.replace("_", " ")
            if section_words in text_lower:
                score += 3.0

        scores[tmpl_name] = score

    if not scores or max(scores.values()) == 0:
        return "hld", 0.3  # Default with low confidence

    best = max(scores, key=scores.get)
    total = sum(scores.values())
    confidence = scores[best] / total if total > 0 else 0.0

    return best, round(confidence, 2)


def extract_with_template(text: str, template_name: str) -> dict:
    """Extract structured data from text using a named template.

    Returns a dict mapping field names to extracted values.
    """
    tmpl = EXTRACTION_TEMPLATES.get(template_name)
    if not tmpl:
        return {"error": f"Unknown template: {template_name}"}

    results = {
        "template": template_name,
        "template_name": tmpl["name"],
        "fields": {},
        "sections_found": [],
        "sections_missing": [],
    }

    text_lower = text.lower()
    lines = text.split("\n")

    # Find sections
    for section in tmpl["expected_sections"]:
        section_words = section.replace("_", " ")
        found = any(section_words in line.lower() for line in lines if line.strip().startswith("#"))
        if found:
            results["sections_found"].append(section)
        else:
            results["sections_missing"].append(section)

    # Extract key fields
    for field_name, field_def in tmpl["key_fields"].items():
        matches = []
        for kw in field_def["keywords"]:
            for i, line in enumerate(lines):
                if kw in line.lower():
                    # Extract the line and surrounding context
                    context = lines[max(0, i - 1):min(len(lines), i + 3)]
                    matches.append({
                        "keyword": kw,
                        "line": i + 1,
                        "context": "\n".join(context),
                    })
        results["fields"][field_name] = {
            "match_count": len(matches),
            "matches": matches[:5],  # Cap at 5 matches per field
        }

    return results


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------

def analyze_document(
    file_path: Path,
    *,
    schema: str | None = None,
    use_layout_detection: bool = True,
) -> DocumentAnalysis:
    """Run the full layout-detection-first analysis pipeline.

    Args:
        file_path: Path to PDF or image file.
        schema: Force a specific extraction template (hld/lld/network/security).
        use_layout_detection: Whether to attempt ML layout detection.

    Returns:
        DocumentAnalysis with per-page results.
    """
    ext = file_path.suffix.lower()
    pages: list[PageAnalysis] = []
    full_text = ""

    if ext == ".pdf":
        pages, full_text = _analyze_pdf(file_path, use_layout_detection)
    elif ext in (".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"):
        pages, full_text = _analyze_image(file_path, use_layout_detection)
    else:
        # Text-based: read directly
        try:
            full_text = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            full_text = ""
        pages = [PageAnalysis(page_index=0, regions=[], full_text=full_text)]

    # Schema detection
    detected_schema = schema
    schema_conf = 1.0
    if not detected_schema:
        detected_schema, schema_conf = detect_document_schema(full_text)

    method = "basic"
    if any(p.regions for p in pages):
        method = "layout-detection"
    elif full_text:
        method = "text-extraction"

    return DocumentAnalysis(
        source_file=str(file_path),
        pages=pages,
        schema_detected=detected_schema,
        extraction_method=method,
        metadata={
            "schema_confidence": schema_conf,
            "total_pages": len(pages),
            "total_regions": sum(len(p.regions) for p in pages),
            "total_tables": sum(len(p.tables) for p in pages),
            "total_figures": sum(len(p.figures) for p in pages),
        },
    )


def _analyze_pdf(file_path: Path, use_layout: bool) -> tuple[list[PageAnalysis], str]:
    """Analyze a PDF file page by page."""
    pages = []
    full_text_parts = []

    # Try PyMuPDF for text extraction
    try:
        import fitz
        doc = fitz.open(str(file_path))
        for i, page in enumerate(doc):
            text = page.get_text("text")
            full_text_parts.append(text)
            pages.append(PageAnalysis(page_index=i, regions=[], full_text=text))
        doc.close()
    except ImportError:
        pass

    # Try layout detection on rendered pages
    if use_layout:
        model = _load_yolo_model()
        if model is not None:
            try:
                from pdf2image import convert_from_path
                images = convert_from_path(str(file_path))
                for i, img in enumerate(images):
                    regions = detect_layout(img, page_index=i, model=model)
                    if i < len(pages):
                        pages[i].regions = regions
                    else:
                        pages.append(PageAnalysis(page_index=i, regions=regions))

                    # Classify regions
                    for region in regions:
                        if region.region_type == RegionType.TABLE:
                            table_data = extract_table_region(img, region)
                            if i < len(pages):
                                pages[i].tables.append(table_data)
                        elif region.region_type == RegionType.PICTURE:
                            if i < len(pages):
                                pages[i].figures.append({
                                    "bbox": region.bbox,
                                    "confidence": region.confidence,
                                })
                        elif region.region_type in (RegionType.TITLE, RegionType.SECTION_HEADER):
                            header_text = extract_text_region(img, region)
                            if header_text and i < len(pages):
                                pages[i].headers.append(header_text)
            except Exception:
                pass

    return pages, "\n\n".join(full_text_parts)


def _analyze_image(file_path: Path, use_layout: bool) -> tuple[list[PageAnalysis], str]:
    """Analyze a single image file."""
    try:
        from PIL import Image
    except ImportError:
        return [PageAnalysis(page_index=0, regions=[])], ""

    img = Image.open(str(file_path))
    try:
        regions = []
        if use_layout:
            regions = detect_layout(img, page_index=0)

        # OCR for text
        text = ""
        try:
            import pytesseract
            text = pytesseract.image_to_string(img)
        except Exception:
            pass

        page = PageAnalysis(page_index=0, regions=regions, full_text=text)
    finally:
        img.close()

    for region in regions:
        if region.region_type == RegionType.TABLE:
            page.tables.append(extract_table_region(img, region))
        elif region.region_type == RegionType.PICTURE:
            page.figures.append({"bbox": region.bbox, "confidence": region.confidence})

    return [page], text


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Layout-detection-first document analysis for Doc2ArchAgent.",
    )
    parser.add_argument("document", type=Path, help="Path to PDF or image file")
    parser.add_argument("--schema", choices=list(EXTRACTION_TEMPLATES.keys()),
                        help="Force extraction template (default: auto-detect)")
    parser.add_argument("--no-layout", action="store_true",
                        help="Skip ML layout detection")
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="Directory for extracted output files")
    parser.add_argument("--format", choices=["json", "text"], default="text",
                        help="Output format")

    args = parser.parse_args()

    if not args.document.exists():
        print(f"Error: {args.document} not found", file=sys.stderr)
        sys.exit(1)

    analysis = analyze_document(
        args.document,
        schema=args.schema,
        use_layout_detection=not args.no_layout,
    )

    # Apply template extraction
    full_text = "\n\n".join(p.full_text for p in analysis.pages)
    template_results = extract_with_template(full_text, analysis.schema_detected)

    output = {
        "source": analysis.source_file,
        "extraction_method": analysis.extraction_method,
        "detected_schema": analysis.schema_detected,
        "metadata": analysis.metadata,
        "template_extraction": template_results,
        "pages": [
            {
                "page": p.page_index + 1,
                "regions": len(p.regions),
                "tables": len(p.tables),
                "figures": len(p.figures),
                "headers": p.headers,
            }
            for p in analysis.pages
        ],
    }

    if args.format == "json":
        print(json.dumps(output, indent=2))
    else:
        print(f"DOCUMENT ANALYSIS: {args.document.name}")
        print(f"{'=' * 50}")
        print(f"Method:    {analysis.extraction_method}")
        print(f"Schema:    {analysis.schema_detected} "
              f"(confidence: {analysis.metadata.get('schema_confidence', 0):.0%})")
        print(f"Pages:     {analysis.metadata.get('total_pages', 0)}")
        print(f"Regions:   {analysis.metadata.get('total_regions', 0)}")
        print(f"Tables:    {analysis.metadata.get('total_tables', 0)}")
        print(f"Figures:   {analysis.metadata.get('total_figures', 0)}")

        if template_results.get("sections_found"):
            print(f"\nSections found: {', '.join(template_results['sections_found'])}")
        if template_results.get("sections_missing"):
            print(f"Sections missing: {', '.join(template_results['sections_missing'])}")

    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        report_path = args.output_dir / f"{args.document.stem}-analysis.json"
        report_path.write_text(json.dumps(output, indent=2))
        print(f"\nReport: {report_path}")


if __name__ == "__main__":
    main()
