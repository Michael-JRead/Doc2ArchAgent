#!/usr/bin/env python3
# Copyright (c) 2026 Michael J. Read. All rights reserved.
# SPDX-License-Identifier: BUSL-1.1
"""Confidence scoring framework for Doc2ArchAgent.

Provides a unified, user-adjustable confidence scoring system (0-100 scale)
that integrates with provenance tracking, document extraction, validation,
and threat analysis.

Usage as library:
    from tools.confidence import ConfidenceScorer, ExtractionMethod

    scorer = ConfidenceScorer(default_threshold=95)
    score = scorer.score(
        method=ExtractionMethod.NATIVE_TEXT,
        field_present=True,
        source_count=2,
    )

Usage as CLI:
    python tools/confidence.py --threshold 90 --method ocr --field-present
"""

import argparse
import json
import sys
from enum import Enum


class ExtractionMethod(str, Enum):
    """How a value was extracted from source documents."""
    NATIVE_TEXT = "native_text"          # PyMuPDF / python-docx direct text
    TABLE_EXTRACTION = "table"           # pdfplumber / ML table extraction
    OCR = "ocr"                          # Tesseract / OpenDoc OCR
    VLM = "vlm"                          # Vision Language Model analysis
    DIAGRAM_PARSE = "diagram_parse"      # Draw.io / Visio XML parsing
    STRUCTURIZR = "structurizr"          # Structurizr DSL ingestion
    K8S_MANIFEST = "k8s_manifest"        # Kubernetes YAML ingestion
    TERRAFORM = "terraform"              # Terraform HCL ingestion
    OPENAPI = "openapi"                  # OpenAPI spec ingestion
    USER_PROVIDED = "user_provided"      # Manually entered by user
    INFERRED = "inferred"                # Derived from other extracted data
    LAYOUT_DETECTION = "layout_detection" # ML layout analysis (DocLayout-YOLO)
    CROSS_REF = "cross_ref"             # Cross-document entity resolution


# Base confidence per extraction method (0-100).
# These represent the inherent reliability of each extraction approach.
METHOD_BASE_CONFIDENCE = {
    ExtractionMethod.USER_PROVIDED: 100,
    ExtractionMethod.NATIVE_TEXT: 95,
    ExtractionMethod.STRUCTURIZR: 95,
    ExtractionMethod.K8S_MANIFEST: 95,
    ExtractionMethod.TERRAFORM: 95,
    ExtractionMethod.OPENAPI: 95,
    ExtractionMethod.DIAGRAM_PARSE: 90,
    ExtractionMethod.TABLE_EXTRACTION: 85,
    ExtractionMethod.LAYOUT_DETECTION: 80,
    ExtractionMethod.CROSS_REF: 75,
    ExtractionMethod.OCR: 70,
    ExtractionMethod.VLM: 65,
    ExtractionMethod.INFERRED: 60,
}


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


class ConfidenceScorer:
    """Compute and evaluate confidence scores for extracted architecture data.

    Attributes:
        default_threshold: Minimum confidence to consider a value reliable (0-100).
                          Default 95. User-adjustable via CLI or config.
    """

    def __init__(self, default_threshold: int = 95):
        self.default_threshold = _clamp(default_threshold, 0, 100)

    def score(
        self,
        method: ExtractionMethod | str,
        *,
        field_present: bool = True,
        source_count: int = 1,
        ocr_char_confidence: float | None = None,
        quote_match_ratio: float | None = None,
        nli_status: str | None = None,
        verified: bool = False,
    ) -> int:
        """Calculate a confidence score (0-100) for an extracted value.

        Args:
            method: How the value was extracted.
            field_present: True if the field was explicitly stated in source.
                          False if it was absent/inferred.
            source_count: Number of independent sources confirming this value.
            ocr_char_confidence: Average OCR character confidence (0.0-1.0),
                                only relevant for OCR method.
            quote_match_ratio: Fuzzy match ratio between quote and source (0.0-1.0).
            nli_status: NLI verification result (entailed/contradicted/neutral).
            verified: Whether a human has verified the extraction.

        Returns:
            Integer confidence score 0-100.
        """
        if verified:
            return 100

        # Resolve method enum
        if isinstance(method, str):
            try:
                method = ExtractionMethod(method)
            except ValueError:
                method = ExtractionMethod.INFERRED

        base = METHOD_BASE_CONFIDENCE.get(method, 50)

        # Adjust for field presence
        if not field_present:
            base = base * 0.6  # Absent fields get 40% penalty

        # Adjust for OCR character-level confidence
        if method == ExtractionMethod.OCR and ocr_char_confidence is not None:
            # Scale base by OCR quality: 0.9+ OCR = small bonus, <0.6 = big penalty
            ocr_factor = 0.5 + (ocr_char_confidence * 0.5)
            base = base * ocr_factor

        # Boost for multiple confirming sources (diminishing returns)
        if source_count > 1:
            boost = min(15, (source_count - 1) * 5)
            base = base + boost

        # Adjust for quote match quality
        if quote_match_ratio is not None:
            if quote_match_ratio >= 0.9:
                base = base + 5
            elif quote_match_ratio < 0.6:
                base = base - 15

        # NLI verification adjustments
        if nli_status == "entailed":
            base = base + 5
        elif nli_status == "contradicted":
            base = base * 0.3  # Heavy penalty for contradiction
        elif nli_status == "neutral":
            base = base - 5

        return int(_clamp(round(base), 0, 100))

    def to_category(self, score: int) -> str:
        """Convert numeric score to categorical label.

        Returns one of: HIGH, MEDIUM, LOW, UNCERTAIN, NOT_STATED
        """
        if score >= 85:
            return "HIGH"
        elif score >= 65:
            return "MEDIUM"
        elif score >= 40:
            return "LOW"
        elif score >= 1:
            return "UNCERTAIN"
        return "NOT_STATED"

    def meets_threshold(self, score: int, threshold: int | None = None) -> bool:
        """Check if a score meets the confidence threshold."""
        t = threshold if threshold is not None else self.default_threshold
        return score >= t

    def score_document_extraction(self, conversion_result: dict) -> int:
        """Score confidence for a document conversion result from convert-docs.py.

        Args:
            conversion_result: A single file result dict from the conversion report.

        Returns:
            Integer confidence score 0-100.
        """
        method_str = conversion_result.get("method", "")
        quality = conversion_result.get("quality", "medium")

        # Map conversion method to ExtractionMethod
        if "pymupdf" in method_str:
            method = ExtractionMethod.NATIVE_TEXT
        elif "python-docx" in method_str:
            method = ExtractionMethod.NATIVE_TEXT
        elif "tesseract" in method_str or "ocr" in method_str:
            method = ExtractionMethod.OCR
        elif "html2text" in method_str or "beautifulsoup" in method_str:
            method = ExtractionMethod.NATIVE_TEXT
        elif "pandoc" in method_str:
            method = ExtractionMethod.NATIVE_TEXT
        elif "direct-copy" in method_str:
            method = ExtractionMethod.NATIVE_TEXT
        else:
            method = ExtractionMethod.INFERRED

        ocr_conf = conversion_result.get("ocr_confidence")

        score = self.score(
            method=method,
            field_present=True,
            ocr_char_confidence=ocr_conf,
        )

        # Quality override
        if quality == "low":
            score = int(score * 0.7)
        elif quality == "high" and score < 90:
            score = min(score + 5, 95)

        return int(_clamp(score, 0, 100))

    # Field weights for aggregate entity scoring
    FIELD_WEIGHTS = {
        "name": 1.5,
        "technology": 1.5,
        "type": 1.2,
        "description": 1.0,
        "protocol": 1.2,
        "port": 1.0,
        "status": 0.8,
    }

    def score_entity(self, entity_fields: dict[str, int]) -> dict:
        """Compute aggregate confidence for a complete entity.

        Uses weighted average of field-level scores where critical fields
        (name, technology) weigh more than descriptive fields.

        Args:
            entity_fields: Mapping of field_name -> confidence_score (0-100).

        Returns:
            Dict with aggregate_score, level, meets_threshold, and per-field breakdown.
        """
        if not entity_fields:
            return {
                "aggregate_score": 0,
                "level": "NOT_STATED",
                "meets_threshold": False,
                "field_count": 0,
            }

        weighted_sum = 0.0
        total_weight = 0.0
        for field, score in entity_fields.items():
            weight = self.FIELD_WEIGHTS.get(field, 1.0)
            weighted_sum += score * weight
            total_weight += weight

        aggregate = int(round(weighted_sum / total_weight)) if total_weight > 0 else 0

        return {
            "aggregate_score": aggregate,
            "level": self.to_category(aggregate),
            "meets_threshold": self.meets_threshold(aggregate),
            "field_count": len(entity_fields),
        }

    def generate_report(self, provenance: dict) -> str:
        """Generate a markdown confidence report from enriched provenance.

        Returns a markdown string with summary table by confidence tier.
        """
        lines = [
            "# Confidence Report",
            "",
        ]

        stats = provenance.get("statistics", {})
        if stats:
            lines.extend([
                f"**Threshold:** {stats.get('confidence_threshold', 95)}%  ",
                f"**Average Confidence:** {stats.get('average_confidence', 0)}%  ",
                f"**Above Threshold:** {stats.get('fields_above_threshold', 0)}  ",
                f"**Below Threshold:** {stats.get('fields_below_threshold', 0)}  ",
                "",
            ])

        # Tier breakdown
        tiers = {"HIGH": [], "MEDIUM": [], "LOW": [], "UNCERTAIN": [], "NOT_STATED": []}
        for entity in provenance.get("entities", []):
            entity_id = entity.get("id", "unknown")
            for field_name, field_data in entity.get("fields", {}).items():
                if not isinstance(field_data, dict):
                    continue
                score = field_data.get("confidence_score", 0)
                cat = self.to_category(score)
                tiers[cat].append(f"{entity_id}.{field_name} ({score})")

        lines.extend([
            "## By Confidence Tier",
            "",
            "| Tier | Count | Fields |",
            "|------|-------|--------|",
        ])
        for tier, fields in tiers.items():
            preview = ", ".join(fields[:5])
            if len(fields) > 5:
                preview += f", ... (+{len(fields) - 5} more)"
            lines.append(f"| {tier} | {len(fields)} | {preview} |")

        return "\n".join(lines) + "\n"

    def enrich_provenance(self, provenance: dict, threshold: int | None = None) -> dict:
        """Add numeric confidence scores to a provenance YAML dict.

        Mutates the provenance dict in-place, adding:
          - entities[].fields[].confidence_score (int, 0-100)
          - entities[].fields[].meets_threshold (bool)
          - statistics.confidence_threshold (int)
          - statistics.fields_above_threshold (int)
          - statistics.fields_below_threshold (int)
          - statistics.average_confidence (float)

        Returns the enriched dict.
        """
        t = threshold if threshold is not None else self.default_threshold
        all_scores: list[int] = []

        for entity in provenance.get("entities", []):
            for field_name, field_data in entity.get("fields", {}).items():
                if not isinstance(field_data, dict):
                    continue

                # Determine extraction method from pass/source
                pass_type = field_data.get("pass", "")
                method_map = {
                    "prose": ExtractionMethod.NATIVE_TEXT,
                    "table": ExtractionMethod.TABLE_EXTRACTION,
                    "diagram": ExtractionMethod.DIAGRAM_PARSE,
                    "cross-ref": ExtractionMethod.CROSS_REF,
                    "user-provided": ExtractionMethod.USER_PROVIDED,
                }
                method = method_map.get(pass_type, ExtractionMethod.INFERRED)

                cat = field_data.get("confidence", "MEDIUM")
                verified = field_data.get("verified", False)
                nli = field_data.get("nli_status")

                numeric = self.score(
                    method=method,
                    field_present=(cat != "NOT_STATED"),
                    verified=verified,
                    nli_status=nli,
                )

                field_data["confidence_score"] = numeric
                field_data["meets_threshold"] = self.meets_threshold(numeric, t)
                all_scores.append(numeric)

        # Update statistics
        stats = provenance.setdefault("statistics", {})
        stats["confidence_threshold"] = int(t)
        stats["fields_above_threshold"] = sum(1 for s in all_scores if s >= t)
        stats["fields_below_threshold"] = sum(1 for s in all_scores if s < t)
        stats["average_confidence"] = round(sum(all_scores) / len(all_scores), 1) if all_scores else 0.0

        return provenance


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Confidence scoring for Doc2ArchAgent extractions.",
    )
    sub = parser.add_subparsers(dest="command")

    # Subcommand: score
    score_p = sub.add_parser("score", help="Calculate a confidence score")
    score_p.add_argument("--method", required=True, choices=[m.value for m in ExtractionMethod])
    score_p.add_argument("--field-present", action="store_true", default=True)
    score_p.add_argument("--field-absent", action="store_true")
    score_p.add_argument("--source-count", type=int, default=1)
    score_p.add_argument("--ocr-confidence", type=float, default=None)
    score_p.add_argument("--quote-match", type=float, default=None)
    score_p.add_argument("--nli-status", choices=["entailed", "contradicted", "neutral"])
    score_p.add_argument("--verified", action="store_true")
    score_p.add_argument("--threshold", type=int, default=95)

    # Subcommand: enrich
    enrich_p = sub.add_parser("enrich", help="Enrich a provenance YAML with numeric scores")
    enrich_p.add_argument("provenance_file", help="Path to provenance.yaml")
    enrich_p.add_argument("--threshold", type=int, default=95)
    enrich_p.add_argument("--output", default=None, help="Output path (default: overwrite)")

    # Subcommand: report
    report_p = sub.add_parser("report", help="Generate markdown confidence report")
    report_p.add_argument("provenance_file", help="Path to provenance.yaml")
    report_p.add_argument("--threshold", type=int, default=95)
    report_p.add_argument("--output", default=None, help="Output markdown path (default: stdout)")

    # Subcommand: set-threshold
    thresh_p = sub.add_parser("set-threshold", help="Display recommended threshold info")
    thresh_p.add_argument("value", type=int, help="New threshold value (0-100)")

    args = parser.parse_args()

    if args.command == "score":
        scorer = ConfidenceScorer(default_threshold=args.threshold)
        result = scorer.score(
            method=args.method,
            field_present=not args.field_absent,
            source_count=args.source_count,
            ocr_char_confidence=args.ocr_confidence,
            quote_match_ratio=args.quote_match,
            nli_status=args.nli_status,
            verified=args.verified,
        )
        category = scorer.to_category(result)
        meets = scorer.meets_threshold(result, args.threshold)
        print(json.dumps({
            "score": result,
            "category": category,
            "threshold": args.threshold,
            "meets_threshold": meets,
        }, indent=2))

    elif args.command == "enrich":
        import yaml as _yaml
        scorer = ConfidenceScorer(default_threshold=args.threshold)
        with open(args.provenance_file) as f:
            prov = _yaml.safe_load(f) or {}
        enriched = scorer.enrich_provenance(prov, args.threshold)
        out_path = args.output or args.provenance_file
        with open(out_path, "w") as f:
            _yaml.dump(enriched, f, default_flow_style=False, sort_keys=False)
        print(f"Enriched {len(enriched.get('entities', []))} entities → {out_path}")

    elif args.command == "report":
        import yaml as _yaml
        scorer = ConfidenceScorer(default_threshold=args.threshold)
        with open(args.provenance_file) as f:
            prov = _yaml.safe_load(f) or {}
        # Ensure enriched
        scorer.enrich_provenance(prov, args.threshold)
        report = scorer.generate_report(prov)
        if args.output:
            with open(args.output, "w") as f:
                f.write(report)
            print(f"Report written to {args.output}")
        else:
            print(report)

    elif args.command == "set-threshold":
        value = max(0, min(100, args.value))
        print(json.dumps({
            "threshold": value,
            "description": f"Entities with confidence below {value}% will require human verification.",
            "note": "Set metadata.confidence_threshold in your YAML files to apply this threshold.",
        }, indent=2))

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
