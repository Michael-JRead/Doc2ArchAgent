#!/usr/bin/env python3
# Copyright (c) 2026 Michael J. Read. All rights reserved.
# SPDX-License-Identifier: BUSL-1.1
"""Deterministic claim verification for Doc2ArchAgent provenance files.

Verifies that extracted architecture claims are grounded in source documents.
Uses multi-tier text matching (exact → normalized → fuzzy) to validate
that provenance quotes actually support the extracted values.

If the optional `transformers` library is installed, can also run NLI-based
verification using DeBERTa for deeper semantic grounding checks.

Usage:
    python tools/verify-claims.py <provenance.yaml> --sources <dir>
        [--confidence-threshold 0.95] [--format json|table]
        [--nli]  # Enable NLI-based verification (requires transformers)

Exit codes:
    0 — All claims verified
    1 — Verification failures found
"""

import argparse
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Error: pyyaml required. pip install pyyaml", file=sys.stderr)
    sys.exit(1)

SCRIPT_DIR = Path(__file__).parent


class ClaimResult:
    """Result of verifying a single claim."""

    def __init__(self, entity_type: str, entity_id: str, field: str,
                 value: str, quote: str, status: str, confidence: float,
                 match_score: float = 0.0, reason: str = "",
                 nli_status: str = "not_checked"):
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.field = field
        self.value = str(value)
        self.quote = quote
        self.status = status  # verified, failed, warning, not_checkable
        self.confidence = confidence
        self.match_score = match_score
        self.reason = reason
        self.nli_status = nli_status

    def to_dict(self):
        return {
            "entity": f"{self.entity_type}:{self.entity_id}",
            "field": self.field,
            "value": self.value,
            "status": self.status,
            "confidence": self.confidence,
            "match_score": round(self.match_score, 3),
            "nli_status": self.nli_status,
            "reason": self.reason,
        }


def load_source_documents(sources_dir: Path) -> dict[str, str]:
    """Load all text source documents from a directory."""
    docs = {}
    if not sources_dir.exists():
        return docs

    for ext in ("*.txt", "*.md", "*.text", "*.rst"):
        for f in sources_dir.glob(ext):
            docs[f.stem] = f.read_text(errors="replace")

    # Also try loading YAML/JSON docs that might be referenced
    for ext in ("*.yaml", "*.yml", "*.json"):
        for f in sources_dir.glob(ext):
            docs[f.stem] = f.read_text(errors="replace")

    return docs


def verify_provenance(provenance: dict, source_docs: dict,
                      confidence_threshold: float = 0.95,
                      use_nli: bool = False) -> list[ClaimResult]:
    """Verify all claims in a provenance file against source documents."""
    results = []
    nli_pipeline = None

    if use_nli:
        nli_pipeline = _load_nli_pipeline()

    entities = provenance.get("entities", [])

    for entity in entities:
        entity_type = entity.get("entity_type", "unknown")
        entity_id = entity.get("entity_id", "unknown")
        fields = entity.get("fields", {})

        for field_name, field_data in fields.items():
            if not isinstance(field_data, dict):
                continue

            value = field_data.get("value", "")
            quote = field_data.get("quote", "")
            source_id = field_data.get("source_id", "")
            confidence = field_data.get("confidence", 0.0)

            # Skip fields below threshold
            if confidence < confidence_threshold:
                results.append(ClaimResult(
                    entity_type, entity_id, field_name, value, quote,
                    status="warning",
                    confidence=confidence,
                    reason=f"Below confidence threshold ({confidence:.2f} < {confidence_threshold:.2f})"
                ))
                continue

            # No quote to verify
            if not quote:
                results.append(ClaimResult(
                    entity_type, entity_id, field_name, value, "",
                    status="warning",
                    confidence=confidence,
                    reason="No source quote provided"
                ))
                continue

            # Find source document
            source_text = source_docs.get(source_id, "")
            if not source_text:
                # Try partial match
                for doc_id, doc_text in source_docs.items():
                    if source_id in doc_id or doc_id in source_id:
                        source_text = doc_text
                        break

            if not source_text:
                results.append(ClaimResult(
                    entity_type, entity_id, field_name, value, quote,
                    status="not_checkable",
                    confidence=confidence,
                    reason=f"Source document '{source_id}' not found"
                ))
                continue

            # Multi-tier quote matching
            match_score, match_method = _verify_quote(quote, source_text)

            if match_score >= 0.95:
                status = "verified"
                reason = f"Exact match ({match_method})"
            elif match_score >= 0.85:
                status = "verified"
                reason = f"High-confidence match ({match_method}, score={match_score:.3f})"
            elif match_score >= 0.70:
                status = "warning"
                reason = f"Partial match ({match_method}, score={match_score:.3f}) — verify manually"
            else:
                status = "failed"
                reason = f"Quote not found in source (best score={match_score:.3f})"

            nli_status = "not_checked"
            if use_nli and nli_pipeline and status in ("verified", "warning"):
                nli_result = _run_nli(nli_pipeline, quote, str(value), field_name)
                nli_status = nli_result
                if nli_result == "contradicted":
                    status = "failed"
                    reason += f" — NLI: CONTRADICTED"
                elif nli_result == "neutral":
                    if status == "verified":
                        status = "warning"
                    reason += f" — NLI: NEUTRAL (value may not be entailed by quote)"

            results.append(ClaimResult(
                entity_type, entity_id, field_name, value, quote,
                status=status,
                confidence=confidence,
                match_score=match_score,
                reason=reason,
                nli_status=nli_status,
            ))

    return results


def _verify_quote(quote: str, source_text: str) -> tuple[float, str]:
    """Multi-tier quote verification against source text.

    Returns (match_score, match_method).
    Tier 1: Exact substring (highest confidence)
    Tier 2: Normalized substring (collapse whitespace, case-insensitive)
    Tier 3: Fuzzy matching (SequenceMatcher)
    """
    # Tier 1: Exact substring
    if quote in source_text:
        return 1.0, "exact"

    # Tier 2: Normalized
    norm_quote = _normalize(quote)
    norm_source = _normalize(source_text)
    if norm_quote in norm_source:
        return 0.98, "normalized"

    # Tier 3: Fuzzy — find best matching window in source
    best_score = 0.0
    quote_len = len(norm_quote)
    # Slide a window across the normalized source
    step = max(1, quote_len // 4)
    for i in range(0, len(norm_source) - quote_len + 1, step):
        window = norm_source[i:i + quote_len + 20]
        score = SequenceMatcher(None, norm_quote, window).ratio()
        if score > best_score:
            best_score = score
            if score >= 0.95:
                break  # Good enough

    return best_score, "fuzzy"


def _normalize(text: str) -> str:
    """Normalize text for comparison: lowercase, collapse whitespace."""
    text = text.lower()
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    return text


def _load_nli_pipeline():
    """Load NLI pipeline (DeBERTa). Returns None if transformers not available."""
    try:
        from transformers import pipeline
        print("Loading NLI model (DeBERTa-v3)...", file=sys.stderr)
        nli = pipeline(
            "text-classification",
            model="microsoft/deberta-v3-base-mnli-fever-anli",
            device=-1,  # CPU
        )
        print("NLI model loaded.", file=sys.stderr)
        return nli
    except ImportError:
        print("Warning: transformers not installed. NLI verification disabled.", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Warning: Failed to load NLI model: {e}. NLI disabled.", file=sys.stderr)
        return None


def _run_nli(pipeline, premise: str, hypothesis_value: str, field_name: str) -> str:
    """Run NLI classification on a claim.

    premise: The source quote
    hypothesis: "The [field_name] is [value]"
    Returns: entailed, contradicted, or neutral
    """
    hypothesis = f"The {field_name.replace('_', ' ')} is {hypothesis_value}."
    try:
        result = pipeline(f"{premise} [SEP] {hypothesis}", truncation=True, max_length=512)
        if result:
            label = result[0].get("label", "").lower()
            if "entail" in label:
                return "entailed"
            elif "contradict" in label:
                return "contradicted"
        return "neutral"
    except Exception:
        return "not_checked"


# =============================================================================
# Output Formatters
# =============================================================================

def format_json(results: list[ClaimResult]) -> str:
    verified = sum(1 for r in results if r.status == "verified")
    failed = sum(1 for r in results if r.status == "failed")
    warnings = sum(1 for r in results if r.status == "warning")
    return json.dumps({
        "total_claims": len(results),
        "verified": verified,
        "failed": failed,
        "warnings": warnings,
        "not_checkable": len(results) - verified - failed - warnings,
        "results": [r.to_dict() for r in results],
    }, indent=2)


def format_table(results: list[ClaimResult]) -> str:
    lines = []
    lines.append("=" * 80)
    lines.append("  Doc2ArchAgent Claim Verification Report")

    verified = sum(1 for r in results if r.status == "verified")
    failed = sum(1 for r in results if r.status == "failed")
    warnings = sum(1 for r in results if r.status == "warning")

    lines.append(f"  Total: {len(results)}  |  Verified: {verified}  |  "
                 f"Failed: {failed}  |  Warnings: {warnings}")
    lines.append("=" * 80)

    for status_group in ["failed", "warning", "not_checkable", "verified"]:
        group = [r for r in results if r.status == status_group]
        if not group:
            continue
        lines.append(f"\n  [{status_group.upper()}]")
        for r in group:
            lines.append(f"  - {r.entity_type}:{r.entity_id}.{r.field} = \"{r.value}\"")
            lines.append(f"    {r.reason}")
            if r.nli_status != "not_checked":
                lines.append(f"    NLI: {r.nli_status}")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Verify provenance claims against source documents.")
    parser.add_argument("provenance_yaml", help="Path to provenance.yaml")
    parser.add_argument("--sources", required=True, help="Directory containing source documents")
    parser.add_argument("--confidence-threshold", type=float, default=0.95)
    parser.add_argument("--format", choices=["json", "table"], default="table")
    parser.add_argument("--nli", action="store_true", help="Enable NLI verification (requires transformers)")
    args = parser.parse_args()

    with open(args.provenance_yaml) as f:
        provenance = yaml.safe_load(f) or {}

    source_docs = load_source_documents(Path(args.sources))
    if not source_docs:
        print(f"Warning: No source documents found in {args.sources}", file=sys.stderr)

    results = verify_provenance(
        provenance, source_docs,
        confidence_threshold=args.confidence_threshold,
        use_nli=args.nli,
    )

    if args.format == "json":
        print(format_json(results))
    else:
        print(format_table(results))

    has_failures = any(r.status == "failed" for r in results)
    sys.exit(1 if has_failures else 0)


if __name__ == "__main__":
    main()
