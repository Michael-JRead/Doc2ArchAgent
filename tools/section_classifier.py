#!/usr/bin/env python3
# Copyright (c) 2026 Michael J. Read. All rights reserved.
# SPDX-License-Identifier: BUSL-1.1
"""Enhanced section classification with optional ML-based classification.

Extends classify-sections.py with:
1. LiLT-based semantic classification (when transformers installed)
2. Ensemble scoring (keyword + ML)
3. Architecture-specific entity detection

Usage:
    python tools/section_classifier.py document.md
    python tools/section_classifier.py document.md --use-ml
    python tools/section_classifier.py document.md --model lilt-roberta-en-base

Falls back gracefully to keyword-based classification when ML deps unavailable.
"""

import argparse
import json
import sys
from pathlib import Path

# Import base classifier (classify-sections.py has a hyphen, needs special loading)
sys.path.insert(0, str(Path(__file__).parent))


def _load_classify_sections():
    """Load classify-sections.py as a module (hyphenated name)."""
    import importlib.util
    src = Path(__file__).parent / "classify-sections.py"
    if not src.exists():
        raise FileNotFoundError(f"Base classifier not found: {src}")
    spec = importlib.util.spec_from_file_location("classify_sections_base", str(src))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot create module spec for {src}")
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as e:
        raise ImportError(f"Failed to load {src}: {e}") from e
    return mod


try:
    _cs = _load_classify_sections()
    split_sections = _cs.split_sections
    keyword_classify_section = _cs.classify_section
except (FileNotFoundError, ImportError) as _load_err:
    import sys
    print(f"Warning: Could not load classify-sections.py: {_load_err}", file=sys.stderr)
    split_sections = None
    keyword_classify_section = None


# ---------------------------------------------------------------------------
# ML-based classification
# ---------------------------------------------------------------------------

class LiLTClassifier:
    """LiLT-based document section classifier.

    Uses the Language-Independent Layout Transformer for
    semantic understanding of document sections, fine-tuned
    for architecture document classification.

    Requires: pip install transformers torch
    """

    # Architecture-specific label mapping
    LABEL_MAP = {
        0: "network",
        1: "product",
        2: "security",
        3: "integration",
        4: "deployment",
        5: "data",
    }

    def __init__(self, model_name: str = "lilt-roberta-en-base"):
        self._model_name = model_name
        self._model = None
        self._tokenizer = None

    @property
    def available(self) -> bool:
        try:
            import transformers
            import torch
            return True
        except ImportError:
            return False

    def _load_model(self):
        if self._model is not None:
            return

        from transformers import AutoTokenizer, AutoModelForSequenceClassification

        # Check for fine-tuned model first
        model_dir = Path(__file__).parent / "models" / "section-classifier"
        if model_dir.exists():
            self._tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
            self._model = AutoModelForSequenceClassification.from_pretrained(str(model_dir))
        else:
            # Use base model (will need fine-tuning for best results)
            self._tokenizer = AutoTokenizer.from_pretrained(
                f"SCUT-DLVCLab/{self._model_name}", trust_remote_code=True
            )
            self._model = AutoModelForSequenceClassification.from_pretrained(
                f"SCUT-DLVCLab/{self._model_name}",
                num_labels=len(self.LABEL_MAP),
                trust_remote_code=True,
            )
        self._model.eval()

    def classify(self, text: str, title: str = "") -> dict:
        """Classify a text section.

        Returns dict with classification, confidence, and per-label scores.
        """
        if not self.available:
            return {"error": "transformers/torch not installed"}

        try:
            self._load_model()
        except Exception as e:
            return {"error": f"Model load failed: {e}"}

        import torch

        input_text = f"{title}\n\n{text}" if title else text
        # Truncate to model max length
        inputs = self._tokenizer(
            input_text, return_tensors="pt",
            truncation=True, max_length=512, padding=True,
        )

        with torch.no_grad():
            outputs = self._model(**inputs)
            probs = torch.softmax(outputs.logits, dim=-1)[0]

        scores = {}
        for idx, label in self.LABEL_MAP.items():
            if idx < len(probs):
                scores[label] = round(float(probs[idx]), 3)

        best_idx = int(torch.argmax(probs))
        best_label = self.LABEL_MAP.get(best_idx, "product")
        confidence = float(probs[best_idx])

        return {
            "classification": best_label,
            "confidence": round(confidence, 2),
            "scores": scores,
            "method": "lilt",
        }


# ---------------------------------------------------------------------------
# Ensemble classifier
# ---------------------------------------------------------------------------

def ensemble_classify(
    section: dict,
    ml_classifier: LiLTClassifier | None = None,
    ml_weight: float = 0.6,
) -> dict:
    """Classify a section using keyword + optional ML ensemble.

    Args:
        section: Section dict with 'title' and 'content'.
        ml_classifier: Optional LiLT classifier instance.
        ml_weight: Weight for ML score in ensemble (0.0-1.0).

    Returns:
        Classification dict with method, scores, confidence.
    """
    # Always get keyword classification
    kw_result = keyword_classify_section(section)

    if ml_classifier is None or not ml_classifier.available:
        kw_result["method"] = "keyword"
        return kw_result

    # Get ML classification
    ml_result = ml_classifier.classify(
        section.get("content", ""),
        title=section.get("title", ""),
    )

    if "error" in ml_result:
        kw_result["method"] = "keyword"
        kw_result["ml_error"] = ml_result["error"]
        return kw_result

    # Ensemble: weighted combination
    kw_weight = 1.0 - ml_weight
    all_labels = set(list(kw_result.get("scores", {}).keys()) +
                     list(ml_result.get("scores", {}).keys()))

    combined_scores = {}
    for label in all_labels:
        kw_score = kw_result.get("scores", {}).get(label, 0.0)
        ml_score = ml_result.get("scores", {}).get(label, 0.0)
        combined_scores[label] = round(kw_score * kw_weight + ml_score * ml_weight, 3)

    best_label = max(combined_scores, key=combined_scores.get) if combined_scores else "product"
    best_conf = combined_scores.get(best_label, 0.5)

    return {
        "classification": best_label,
        "confidence": round(min(best_conf, 0.99), 2),
        "scores": combined_scores,
        "method": "ensemble",
        "keyword_result": kw_result.get("classification"),
        "ml_result": ml_result.get("classification"),
    }


# ---------------------------------------------------------------------------
# Architecture entity detection
# ---------------------------------------------------------------------------

# Regex patterns for common architecture entities
ENTITY_PATTERNS = {
    "ip_address": r'\b(?:\d{1,3}\.){3}\d{1,3}(?:/\d{1,2})?\b',
    "port": r'\b(?:port|PORT)\s*:?\s*(\d{1,5})\b',
    "protocol": r'\b(HTTPS?|TLS|SSL|AMQP|MQTT|gRPC|WebSocket|TCP|UDP|SFTP|LDAP|LDAPS)\b',
    "technology": r'\b(PostgreSQL|MySQL|MongoDB|Redis|Kafka|RabbitMQ|Elasticsearch|Nginx|Apache|Tomcat|Docker|Kubernetes|AWS|Azure|GCP)\b',
    "auth_mechanism": r'\b(OAuth\s*2\.?0?|SAML|JWT|mTLS|LDAP|Kerberos|API[- ]?key|Basic\s+Auth|OpenID\s+Connect|OIDC)\b',
}


def detect_entities_in_text(text: str) -> dict[str, list[str]]:
    """Detect architecture-relevant entities in text using regex patterns.

    Returns dict mapping entity type to list of found values.
    """
    import re
    results = {}
    for entity_type, pattern in ENTITY_PATTERNS.items():
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            # Deduplicate while preserving order
            seen = set()
            unique = []
            for m in matches:
                m_lower = m.lower() if isinstance(m, str) else str(m).lower()
                if m_lower not in seen:
                    seen.add(m_lower)
                    unique.append(m if isinstance(m, str) else str(m))
            results[entity_type] = unique

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

# Provide the keyword classifier functions as a module-level import target
try:
    from tools import classify_sections as _cs_mod
    classify_sections_module = _cs_mod
except ImportError:
    classify_sections_module = None


def main():
    parser = argparse.ArgumentParser(
        description="Enhanced section classification with optional ML support.",
    )
    parser.add_argument("document", type=Path, help="Path to document")
    parser.add_argument("--use-ml", action="store_true",
                        help="Enable LiLT ML classification")
    parser.add_argument("--model", default="lilt-roberta-en-base",
                        help="LiLT model name (default: lilt-roberta-en-base)")
    parser.add_argument("--ml-weight", type=float, default=0.6,
                        help="ML weight in ensemble (0.0-1.0, default: 0.6)")
    parser.add_argument("--detect-entities", action="store_true",
                        help="Also detect architecture entities in text")
    parser.add_argument("--format", choices=["json", "text"], default="text")

    args = parser.parse_args()

    if not args.document.exists():
        print(f"Error: {args.document} not found", file=sys.stderr)
        sys.exit(1)

    text = args.document.read_text(encoding="utf-8", errors="replace")
    sections = split_sections(text)

    ml_classifier = None
    if args.use_ml:
        ml_classifier = LiLTClassifier(model_name=args.model)
        if not ml_classifier.available:
            print("Warning: ML deps not available, using keyword-only", file=sys.stderr)
            ml_classifier = None

    results = []
    for section in sections:
        cls_result = ensemble_classify(section, ml_classifier, args.ml_weight)
        entry = {
            "title": section["title"],
            "start_line": section["start_line"],
            "end_line": section["end_line"],
            **cls_result,
        }

        if args.detect_entities:
            entities = detect_entities_in_text(section.get("content", ""))
            if entities:
                entry["detected_entities"] = entities

        results.append(entry)

    output = {
        "document": str(args.document),
        "total_sections": len(results),
        "method": results[0].get("method", "keyword") if results else "keyword",
        "sections": results,
    }

    if args.format == "json":
        print(json.dumps(output, indent=2))
    else:
        print(f"SECTION CLASSIFICATION: {args.document.name}")
        print(f"{'=' * 50}")
        print(f"Method: {output['method']}")
        print(f"Sections: {output['total_sections']}")
        for s in results:
            print(f"  [{s['confidence']:.0%}] {s['classification']:12s} — {s['title']}")
            if s.get("detected_entities"):
                for etype, vals in s["detected_entities"].items():
                    print(f"         {etype}: {', '.join(vals[:3])}")


if __name__ == "__main__":
    main()
