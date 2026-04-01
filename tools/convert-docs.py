#!/usr/bin/env python3
# Copyright (c) 2024-2026 Michael J. Read. All rights reserved.
# SPDX-License-Identifier: BUSL-1.1
"""Unified document conversion for Doc2ArchAgent.

Converts PDF, DOCX, HTML, and image files to plain text with table
preservation, generating a conversion report for the doc-collector agent.

Usage:
    python tools/convert-docs.py <input-dir> <output-dir> [--system-id NAME] [--format json]

Output:
    Converted .txt/.md files in <output-dir>
    conversion-report.json with per-file details

Dependencies (install via: pip install -r tools/requirements.txt):
    Required: pyyaml
    PDF:      PyMuPDF, pdfplumber
    OCR:      pytesseract, Pillow, pdf2image
    DOCX:     python-docx
    HTML:     beautifulsoup4, html2text
    Diagrams: vsdx (optional)
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Lazy imports — each converter only imports what it needs so the script
# degrades gracefully when optional packages are missing.
# ---------------------------------------------------------------------------

def _try_import(module_name: str):
    """Return module or None if not installed."""
    try:
        return __import__(module_name)
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# Conversion functions
# ---------------------------------------------------------------------------

def convert_pdf_text(src: Path, dst: Path) -> dict:
    """Extract text from a text-based PDF using PyMuPDF, with pdfplumber
    table extraction as enrichment."""
    fitz = _try_import("fitz")
    if fitz is None:
        return {"status": "skipped", "reason": "PyMuPDF not installed (pip install PyMuPDF)"}

    doc = fitz.open(str(src))
    text_pages: list[str] = []
    has_tables = False

    for page in doc:
        page_text = page.get_text("text")
        text_pages.append(page_text)

    full_text = "\n\n".join(text_pages)
    doc.close()

    # Detect scanned PDF: negligible text output
    if len(full_text.strip()) < 50:
        return {"status": "scanned", "reason": "PDF appears scanned (no extractable text)"}

    # Try pdfplumber for table enrichment
    pdfplumber = _try_import("pdfplumber")
    table_md = ""
    if pdfplumber:
        try:
            with pdfplumber.open(str(src)) as pdf:
                for i, page in enumerate(pdf.pages):
                    tables = page.extract_tables()
                    for t_idx, table in enumerate(tables):
                        if not table:
                            continue
                        has_tables = True
                        table_md += f"\n\n### Table (page {i + 1}, table {t_idx + 1})\n\n"
                        # Build markdown table
                        header = table[0]
                        table_md += "| " + " | ".join(str(c or "") for c in header) + " |\n"
                        table_md += "| " + " | ".join("---" for _ in header) + " |\n"
                        for row in table[1:]:
                            table_md += "| " + " | ".join(str(c or "") for c in row) + " |\n"
        except Exception:
            pass  # Non-critical — text extraction already succeeded

    output = full_text
    if table_md:
        output += "\n\n---\n## Extracted Tables\n" + table_md

    dst.write_text(output, encoding="utf-8")
    return {
        "status": "converted",
        "method": "pymupdf" + ("+pdfplumber-tables" if has_tables else ""),
        "quality": "high",
        "has_tables": has_tables,
        "pages": len(text_pages),
    }


def convert_pdf_ocr(src: Path, dst: Path) -> dict:
    """OCR a scanned PDF using pytesseract + pdf2image."""
    pytesseract = _try_import("pytesseract")
    pdf2image = _try_import("pdf2image")

    if pytesseract is None or pdf2image is None:
        return {
            "status": "skipped",
            "reason": "OCR requires pytesseract and pdf2image (pip install pytesseract pdf2image)",
        }

    try:
        images = pdf2image.convert_from_path(str(src))
    except Exception as e:
        return {"status": "error", "reason": f"pdf2image failed: {e}"}

    ocr_pages: list[str] = []
    for img in images:
        text = pytesseract.image_to_string(img)
        ocr_pages.append(text)

    full_text = "\n\n".join(ocr_pages)
    if len(full_text.strip()) < 20:
        return {"status": "error", "reason": "OCR produced no usable text"}

    dst.write_text(full_text, encoding="utf-8")

    # Rough confidence from average character confidence
    try:
        data = pytesseract.image_to_data(images[0], output_type=pytesseract.Output.DICT)
        confs = [int(c) for c in data["conf"] if int(c) > 0]
        avg_conf = sum(confs) / len(confs) if confs else 0
    except Exception:
        avg_conf = 0

    return {
        "status": "converted",
        "method": "tesseract-ocr",
        "quality": "medium",
        "ocr_confidence": round(avg_conf / 100, 2),
        "pages": len(images),
    }


def convert_pdf(src: Path, dst: Path) -> dict:
    """Convert PDF: try text extraction first, fall back to OCR."""
    result = convert_pdf_text(src, dst)
    if result.get("status") == "scanned":
        return convert_pdf_ocr(src, dst)
    return result


def convert_docx(src: Path, dst: Path) -> dict:
    """Convert DOCX with table preservation using python-docx."""
    docx = _try_import("docx")
    if docx is None:
        # Fallback: try pandoc
        if shutil.which("pandoc"):
            rc = os.system(f'pandoc "{src}" -t plain -o "{dst}" 2>/dev/null')
            if rc == 0:
                return {"status": "converted", "method": "pandoc", "quality": "high", "has_tables": False}
        return {"status": "skipped", "reason": "python-docx not installed and pandoc not available"}

    from docx import Document

    doc = Document(str(src))
    parts: list[str] = []
    has_tables = False

    for element in doc.element.body:
        tag = element.tag.split("}")[-1] if "}" in element.tag else element.tag

        if tag == "p":
            # Paragraph
            para = element
            text_runs = []
            for run in para.iter():
                run_tag = run.tag.split("}")[-1] if "}" in run.tag else run.tag
                if run_tag == "t" and run.text:
                    text_runs.append(run.text)
            if text_runs:
                parts.append("".join(text_runs))

        elif tag == "tbl":
            # Table → markdown
            has_tables = True
            rows: list[list[str]] = []
            for tr in element:
                tr_tag = tr.tag.split("}")[-1] if "}" in tr.tag else tr.tag
                if tr_tag != "tr":
                    continue
                cells: list[str] = []
                for tc in tr:
                    tc_tag = tc.tag.split("}")[-1] if "}" in tc.tag else tc.tag
                    if tc_tag != "tc":
                        continue
                    cell_text = []
                    for p in tc.iter():
                        p_tag = p.tag.split("}")[-1] if "}" in p.tag else p.tag
                        if p_tag == "t" and p.text:
                            cell_text.append(p.text)
                    cells.append(" ".join(cell_text))
                if cells:
                    rows.append(cells)

            if rows:
                md_table = "\n| " + " | ".join(rows[0]) + " |\n"
                md_table += "| " + " | ".join("---" for _ in rows[0]) + " |\n"
                for row in rows[1:]:
                    # Pad row to match header length
                    padded = row + [""] * (len(rows[0]) - len(row))
                    md_table += "| " + " | ".join(padded[:len(rows[0])]) + " |\n"
                parts.append(md_table)

    dst.write_text("\n\n".join(parts), encoding="utf-8")
    return {"status": "converted", "method": "python-docx", "quality": "high", "has_tables": has_tables}


def convert_html(src: Path, dst: Path) -> dict:
    """Convert HTML to plain text."""
    html2text_mod = _try_import("html2text")
    bs4 = _try_import("bs4")

    raw = src.read_text(encoding="utf-8", errors="replace")

    if html2text_mod:
        h = html2text_mod.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True
        h.body_width = 0
        text = h.handle(raw)
        dst.write_text(text, encoding="utf-8")
        return {"status": "converted", "method": "html2text", "quality": "high"}

    if bs4:
        soup = bs4.BeautifulSoup(raw, "html.parser")
        text = soup.get_text(separator="\n", strip=True)
        dst.write_text(text, encoding="utf-8")
        return {"status": "converted", "method": "beautifulsoup4", "quality": "high"}

    # Fallback: pandoc
    if shutil.which("pandoc"):
        rc = os.system(f'pandoc "{src}" -t plain -o "{dst}" 2>/dev/null')
        if rc == 0:
            return {"status": "converted", "method": "pandoc", "quality": "high"}

    # Last resort: raw read
    dst.write_text(raw, encoding="utf-8")
    return {"status": "converted", "method": "raw-read", "quality": "medium"}


def convert_image(src: Path, dst: Path) -> dict:
    """OCR an image file using pytesseract."""
    pytesseract = _try_import("pytesseract")
    pil = _try_import("PIL")

    if pytesseract is None or pil is None:
        return {"status": "skipped", "reason": "Image OCR requires pytesseract and Pillow"}

    from PIL import Image

    try:
        img = Image.open(str(src))
        text = pytesseract.image_to_string(img)
    except Exception as e:
        return {"status": "error", "reason": f"OCR failed: {e}"}

    if len(text.strip()) < 10:
        return {
            "status": "skipped",
            "reason": "OCR produced minimal text — paste image into Copilot Chat for Vision analysis",
        }

    dst.write_text(text, encoding="utf-8")
    return {"status": "converted", "method": "tesseract-ocr", "quality": "medium"}


def copy_text(src: Path, dst: Path) -> dict:
    """Copy text files as-is."""
    shutil.copy2(str(src), str(dst))
    return {"status": "converted", "method": "direct-copy", "quality": "high"}


# ---------------------------------------------------------------------------
# File type routing
# ---------------------------------------------------------------------------

EXTENSION_MAP = {
    ".pdf": convert_pdf,
    ".docx": convert_docx,
    ".doc": convert_docx,  # Will fail gracefully if python-docx can't handle .doc
    ".html": convert_html,
    ".htm": convert_html,
    ".png": convert_image,
    ".jpg": convert_image,
    ".jpeg": convert_image,
    ".tiff": convert_image,
    ".tif": convert_image,
    ".bmp": convert_image,
    ".txt": copy_text,
    ".md": copy_text,
    ".csv": copy_text,
    ".json": copy_text,
    ".yaml": copy_text,
    ".yml": copy_text,
}

SKIP_EXTENSIONS = {".xlsx", ".xls", ".pptx", ".ppt", ".zip", ".tar", ".gz"}


def convert_file(src: Path, output_dir: Path) -> dict:
    """Convert a single file, returning a result dict."""
    ext = src.suffix.lower()

    if ext in SKIP_EXTENSIONS:
        return {"source": src.name, "status": "skipped", "reason": f"Unsupported format ({ext})"}

    # Diagram files handled by parse-diagram-file.py, not here
    if ext in (".drawio", ".xml", ".vsdx"):
        return {
            "source": src.name,
            "status": "skipped",
            "reason": f"Diagram file — use tools/parse-diagram-file.py instead",
        }

    converter = EXTENSION_MAP.get(ext)
    if converter is None:
        return {"source": src.name, "status": "skipped", "reason": f"Unknown format ({ext})"}

    # Determine output filename
    out_ext = ".md" if ext in (".docx", ".doc", ".html", ".htm") else ".txt"
    dst = output_dir / (src.stem + out_ext)

    try:
        result = converter(src, dst)
    except Exception as e:
        result = {"status": "error", "reason": str(e)}

    result["source"] = src.name
    if result.get("status") == "converted":
        result["output"] = dst.name
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Convert architecture documents for Doc2ArchAgent ingestion.",
        epilog="Output: converted text files + conversion-report.json",
    )
    parser.add_argument("input_dir", help="Directory containing source documents")
    parser.add_argument("output_dir", help="Directory for converted text files")
    parser.add_argument("--system-id", default=None, help="System ID for context naming")
    parser.add_argument("--format", choices=["json", "text"], default="text",
                        help="Report output format (default: text)")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    if not input_dir.is_dir():
        print(f"Error: {input_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Collect files (non-recursive, skip hidden files)
    files = sorted(f for f in input_dir.iterdir() if f.is_file() and not f.name.startswith("."))

    if not files:
        print(f"No files found in {input_dir}", file=sys.stderr)
        sys.exit(1)

    results: list[dict] = []
    tools_used: dict[str, str] = {}

    for f in files:
        result = convert_file(f, output_dir)
        results.append(result)

        method = result.get("method", "")
        if method and method not in tools_used:
            # Record tool version
            if "pymupdf" in method:
                fitz = _try_import("fitz")
                if fitz:
                    tools_used["pymupdf"] = getattr(fitz, "version", ("unknown",))[0]
            elif "pdfplumber" in method:
                mod = _try_import("pdfplumber")
                if mod:
                    tools_used["pdfplumber"] = getattr(mod, "__version__", "unknown")
            elif "python-docx" in method:
                tools_used["python-docx"] = "installed"
            elif "tesseract" in method:
                tools_used["pytesseract"] = "installed"
            elif "html2text" in method:
                mod = _try_import("html2text")
                if mod:
                    tools_used["html2text"] = getattr(mod, "__version__", "unknown")
            elif "pandoc" in method:
                tools_used["pandoc"] = "installed"

    # Build warnings
    warnings: list[str] = []
    for r in results:
        if r.get("status") == "error":
            warnings.append(f"{r['source']}: {r.get('reason', 'unknown error')}")
        elif r.get("status") == "skipped":
            warnings.append(f"{r['source']}: {r.get('reason', 'skipped')}")
        elif r.get("quality") == "medium":
            warnings.append(f"{r['source']}: quality is medium — manual review recommended")

    report = {
        "files": results,
        "tools_used": tools_used,
        "warnings": warnings,
        "summary": {
            "total": len(results),
            "converted": sum(1 for r in results if r.get("status") == "converted"),
            "skipped": sum(1 for r in results if r.get("status") == "skipped"),
            "errors": sum(1 for r in results if r.get("status") == "error"),
        },
    }

    # Write report
    report_path = output_dir / "conversion-report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print(f"DOCUMENT CONVERSION COMPLETE")
        print(f"{'=' * 40}")
        print(f"Files found: {report['summary']['total']}")
        for r in results:
            status_icon = {"converted": "✓", "skipped": "✗", "error": "⚠", "scanned": "⚠"}.get(
                r.get("status", ""), "?"
            )
            method = r.get("method", r.get("reason", ""))
            output = r.get("output", "")
            print(f"  {status_icon} {r['source']:30s} → {output or method}")
        print(f"\nConverted: {report['summary']['converted']} | "
              f"Skipped: {report['summary']['skipped']} | "
              f"Errors: {report['summary']['errors']}")
        if warnings:
            print(f"\nWarnings:")
            for w in warnings:
                print(f"  ⚠ {w}")
        print(f"\nReport: {report_path}")


if __name__ == "__main__":
    main()
