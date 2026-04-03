#!/usr/bin/env python3
# Copyright (c) 2026 Michael J. Read. All rights reserved.
# SPDX-License-Identifier: BUSL-1.1
"""Deterministic provenance validation for Doc2ArchAgent.

Validates that every citation in provenance.yaml actually exists in the
source documents. Implements the Separation Principle: no LLM involvement.

Usage:
    python tools/validate-provenance.py <provenance.yaml> <context-dir> [<system.yaml>]

Output:
    JSON to stdout: {"valid": bool, "errors": [...], "warnings": [...]}

Dependencies:
    Required: pyyaml
    Optional: rapidfuzz (for fuzzy quote matching — pip install rapidfuzz)
"""

import json
import sys
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_CONFIDENCE = {"HIGH", "MEDIUM", "LOW", "UNCERTAIN", "NOT_STATED"}
VALID_ENTITY_TYPES = {
    "context", "container", "component", "listener",
    "relationship", "zone", "external_system",
    "data_entity", "trust_boundary", "metadata",
}
VALID_PASSES = {"prose", "table", "diagram", "cross-ref", "user-provided"}
VALID_EXTRACTION_METHODS = {
    "direct_read", "pandoc", "pdftotext", "ocr", "vision",
    "python-docx", "pymupdf", "html2text", "tesseract-ocr",
    "pymupdf+pdfplumber-tables", "direct-copy", "raw-read",
}

# Fuzzy match threshold for quote verification (0-100)
# Enterprise-grade threshold: 85 reduces false negatives on paraphrased claims
QUOTE_MATCH_THRESHOLD = 85


# ---------------------------------------------------------------------------
# Fuzzy matching
# ---------------------------------------------------------------------------

def _fuzzy_match(quote: str, source_text: str) -> float:
    """Return fuzzy match score (0-100) for a quote within source text.
    Uses rapidfuzz if available, falls back to difflib."""
    if not quote or not source_text:
        return 0.0

    # Normalize whitespace
    quote = " ".join(quote.split())
    source_text = " ".join(source_text.split())

    try:
        from rapidfuzz import fuzz
        return fuzz.partial_ratio(quote.lower(), source_text.lower())
    except ImportError:
        pass

    # Fallback to stdlib difflib
    from difflib import SequenceMatcher
    # For partial matching, check sliding windows
    quote_lower = quote.lower()
    source_lower = source_text.lower()
    q_len = len(quote_lower)

    if q_len == 0:
        return 0.0

    best = 0.0
    # Slide through source in chunks roughly the size of the quote
    step = max(1, q_len // 4)
    for i in range(0, max(1, len(source_lower) - q_len + 1), step):
        window = source_lower[i:i + q_len + q_len // 2]
        ratio = SequenceMatcher(None, quote_lower, window).ratio() * 100
        if ratio > best:
            best = ratio
        if best >= 95:
            break

    return best


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_provenance(
    provenance_path: str,
    context_dir: str,
    system_path: str | None = None,
) -> dict:
    """Run all provenance validation checks."""
    errors: list[str] = []
    warnings: list[str] = []

    # --- Load provenance ---
    try:
        with open(provenance_path) as f:
            prov = yaml.safe_load(f) or {}
    except Exception as e:
        return {"valid": False, "errors": [f"Cannot load provenance YAML: {e}"], "warnings": []}

    context_path = Path(context_dir)

    # --- Load source documents for quote verification ---
    source_texts: dict[str, str] = {}
    if context_path.is_dir():
        for fp in context_path.iterdir():
            if fp.is_file() and fp.suffix in (".txt", ".md", ".csv", ".json", ".yaml", ".yml"):
                try:
                    source_texts[fp.name] = fp.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    pass

    # --- Load system.yaml for cross-reference ---
    system: dict = {}
    if system_path:
        try:
            with open(system_path) as f:
                system = yaml.safe_load(f) or {}
        except Exception as e:
            warnings.append(f"Cannot load system YAML for cross-reference: {e}")

    # --- Check required top-level fields ---
    for field in ("extraction_date", "pipeline_version", "documents_analyzed", "entities"):
        if field not in prov:
            errors.append(f"Missing required top-level field: {field}")

    # --- Validate documents_analyzed ---
    docs_analyzed = prov.get("documents_analyzed", [])
    if not isinstance(docs_analyzed, list):
        errors.append("documents_analyzed must be a list")
        docs_analyzed = []

    cited_files: set[str] = set()
    for i, doc in enumerate(docs_analyzed):
        if not isinstance(doc, dict):
            errors.append(f"documents_analyzed[{i}]: must be a dict")
            continue

        doc_file = doc.get("file", "")
        if not doc_file:
            errors.append(f"documents_analyzed[{i}]: missing 'file' field")
            continue

        cited_files.add(doc_file)

        # Check extraction method
        method = doc.get("extraction_method", "")
        if method and method not in VALID_EXTRACTION_METHODS:
            warnings.append(f"documents_analyzed[{i}] ({doc_file}): "
                          f"unknown extraction_method '{method}'")

        # Verify source file exists in context directory
        if source_texts and doc_file not in source_texts:
            # Check without extension variations
            found = any(
                doc_file.rsplit(".", 1)[0] == existing.rsplit(".", 1)[0]
                for existing in source_texts
            )
            if not found:
                warnings.append(f"documents_analyzed[{i}] ({doc_file}): "
                              f"source file not found in {context_dir}")

    # --- Validate entities ---
    entities = prov.get("entities", [])
    if not isinstance(entities, list):
        errors.append("entities must be a list")
        entities = []

    entity_ids_in_prov: set[str] = set()
    quote_checks = 0
    quote_matches = 0

    for i, entity in enumerate(entities):
        if not isinstance(entity, dict):
            errors.append(f"entities[{i}]: must be a dict")
            continue

        eid = entity.get("entity_id", "")
        if not eid:
            errors.append(f"entities[{i}]: missing entity_id")
            continue

        entity_ids_in_prov.add(eid)

        etype = entity.get("entity_type", "")
        if etype and etype not in VALID_ENTITY_TYPES:
            warnings.append(f"Entity '{eid}': unknown entity_type '{etype}'")

        # Validate fields
        fields = entity.get("fields", {})
        if not isinstance(fields, dict):
            errors.append(f"Entity '{eid}': fields must be a dict")
            continue

        for field_name, field_data in fields.items():
            if not isinstance(field_data, dict):
                continue

            # Confidence enum
            conf = field_data.get("confidence", "")
            if conf and conf not in VALID_CONFIDENCE:
                errors.append(f"Entity '{eid}'.{field_name}: "
                            f"invalid confidence '{conf}' "
                            f"(must be one of {', '.join(sorted(VALID_CONFIDENCE))})")

            # Pass enum
            pass_val = field_data.get("pass", "")
            if pass_val and pass_val not in VALID_PASSES:
                warnings.append(f"Entity '{eid}'.{field_name}: "
                              f"unknown pass '{pass_val}'")

            # Source file reference
            source_ref = field_data.get("source", "")
            if source_ref:
                # Extract filename from "filename, section" format
                source_file = source_ref.split(",")[0].strip()
                if source_file and cited_files and source_file not in cited_files:
                    warnings.append(f"Entity '{eid}'.{field_name}: "
                                  f"source '{source_file}' not in documents_analyzed")

            # Quote verification
            quote = field_data.get("quote")
            if quote and source_texts:
                quote_checks += 1
                source_ref = field_data.get("source", "")
                source_file = source_ref.split(",")[0].strip()

                # Find source text — try exact name, then stem match
                src_text = source_texts.get(source_file, "")
                if not src_text:
                    for name, text in source_texts.items():
                        if name.rsplit(".", 1)[0] == source_file.rsplit(".", 1)[0]:
                            src_text = text
                            break

                if src_text:
                    score = _fuzzy_match(quote, src_text)
                    if score >= QUOTE_MATCH_THRESHOLD:
                        quote_matches += 1
                    elif score >= 50:
                        warnings.append(
                            f"Entity '{eid}'.{field_name}: quote has weak match "
                            f"(score {score:.0f}, threshold {QUOTE_MATCH_THRESHOLD}) "
                            f"in '{source_file}'"
                        )
                    else:
                        errors.append(
                            f"Entity '{eid}'.{field_name}: quote NOT FOUND "
                            f"(score {score:.0f}) in '{source_file}'"
                        )
                else:
                    warnings.append(
                        f"Entity '{eid}'.{field_name}: cannot verify quote — "
                        f"source '{source_file}' not available"
                    )

    # --- Validate statistics ---
    stats = prov.get("statistics", {})
    if isinstance(stats, dict):
        total = stats.get("total_fields_extracted", 0)
        computed_total = sum(
            len(e.get("fields", {})) for e in entities if isinstance(e, dict)
        )
        if total != computed_total:
            warnings.append(
                f"Statistics mismatch: total_fields_extracted={total} "
                f"but counted {computed_total} fields in entities"
            )

        # Confidence breakdown
        conf_counts: dict[str, int] = {}
        for entity in entities:
            if not isinstance(entity, dict):
                continue
            for field_data in entity.get("fields", {}).values():
                if isinstance(field_data, dict):
                    c = field_data.get("confidence", "")
                    if c:
                        conf_counts[c] = conf_counts.get(c, 0) + 1

        for level in ("high_confidence", "medium_confidence", "low_confidence", "uncertain"):
            stated = stats.get(level, 0)
            conf_key = level.replace("_confidence", "").upper()
            actual = conf_counts.get(conf_key, 0)
            if stated and actual and stated != actual:
                warnings.append(
                    f"Statistics mismatch: {level}={stated} "
                    f"but counted {actual} {conf_key} fields"
                )

    # --- Cross-reference with system.yaml ---
    if system:
        system_entity_ids: set[str] = set()
        # Collect all IDs from system.yaml
        for ctx in system.get("contexts", []):
            if isinstance(ctx, dict) and "id" in ctx:
                system_entity_ids.add(ctx["id"])
            for cont in ctx.get("containers", []) if isinstance(ctx, dict) else []:
                if isinstance(cont, dict) and "id" in cont:
                    system_entity_ids.add(cont["id"])
                for comp in cont.get("components", []) if isinstance(cont, dict) else []:
                    if isinstance(comp, dict) and "id" in comp:
                        system_entity_ids.add(comp["id"])

        # Check for entities in system.yaml without provenance
        for sid in system_entity_ids:
            if sid not in entity_ids_in_prov:
                warnings.append(
                    f"Entity '{sid}' exists in system.yaml but has no provenance entry"
                )

        # Check for orphaned provenance entries
        if system_entity_ids:
            for pid in entity_ids_in_prov:
                if pid not in system_entity_ids and pid != system.get("name", ""):
                    warnings.append(
                        f"Entity '{pid}' in provenance but not found in system.yaml"
                    )

    # --- Validate conflicts_resolved ---
    conflicts = prov.get("conflicts_resolved", [])
    if isinstance(conflicts, list):
        for i, conflict in enumerate(conflicts):
            if not isinstance(conflict, dict):
                continue
            if "entity_id" not in conflict:
                errors.append(f"conflicts_resolved[{i}]: missing entity_id")
            if "resolution" not in conflict:
                warnings.append(f"conflicts_resolved[{i}]: missing resolution")

    # --- Summary ---
    valid = len(errors) == 0

    # Add quote verification summary
    if quote_checks > 0:
        match_rate = (quote_matches / quote_checks) * 100
        if match_rate < 80:
            warnings.append(
                f"Quote verification: {quote_matches}/{quote_checks} quotes matched "
                f"({match_rate:.0f}%) — below 80% threshold"
            )

    return {"valid": valid, "errors": errors, "warnings": warnings}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 3:
        print(
            "Usage: python tools/validate-provenance.py "
            "<provenance.yaml> <context-dir> [<system.yaml>]",
            file=sys.stderr,
        )
        print(
            "\nValidates provenance citations against source documents.\n"
            "Output: JSON {valid, errors, warnings}",
            file=sys.stderr,
        )
        sys.exit(1)

    provenance_path = sys.argv[1]
    context_dir = sys.argv[2]
    system_path = sys.argv[3] if len(sys.argv) > 3 else None

    result = validate_provenance(provenance_path, context_dir, system_path)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
