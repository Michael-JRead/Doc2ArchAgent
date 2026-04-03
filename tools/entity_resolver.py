#!/usr/bin/env python3
# Copyright (c) 2026 Michael J. Read. All rights reserved.
# SPDX-License-Identifier: BUSL-1.1
"""Cross-document entity resolution for Doc2ArchAgent.

Detects and merges duplicate architecture entities (components, containers,
zones, external systems) that appear across multiple source documents with
different names or slightly different spellings.

Uses fuzzy string matching (rapidfuzz) with architecture-aware normalization.

Usage:
    python tools/entity_resolver.py architecture/system.yaml
    python tools/entity_resolver.py architecture/system.yaml --threshold 80 --dry-run
    python tools/entity_resolver.py architecture/system.yaml --format json
"""

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

try:
    from rapidfuzz import fuzz, process
except ImportError:
    fuzz = None
    process = None


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

# Common architecture abbreviations and their expansions
ABBREVIATIONS = {
    "db": "database",
    "svc": "service",
    "srv": "server",
    "lb": "load-balancer",
    "gw": "gateway",
    "fw": "firewall",
    "mq": "message-queue",
    "k8s": "kubernetes",
    "cfg": "config",
    "mgmt": "management",
    "auth": "authentication",
    "msg": "message",
    "proc": "processor",
    "app": "application",
    "api-gw": "api-gateway",
    "rds": "relational-database-service",
    "elb": "elastic-load-balancer",
    "alb": "application-load-balancer",
    "nlb": "network-load-balancer",
    "cdn": "content-delivery-network",
    "waf": "web-application-firewall",
    "vpc": "virtual-private-cloud",
}

# Noise words to strip for comparison
NOISE_WORDS = {
    "the", "a", "an", "for", "of", "in", "on", "to", "and", "or",
    "our", "their", "this", "that", "internal", "external", "main",
    "primary", "secondary", "prod", "production", "dev", "development",
    "staging", "test", "testing",
}


def normalize_entity_name(name: str) -> str:
    """Normalize an entity name for fuzzy comparison.

    Applies: lowercase, kebab-to-spaces, abbreviation expansion,
    noise word removal, whitespace collapse.
    """
    if not name:
        return ""

    # Lowercase and convert separators to spaces
    n = name.lower()
    n = n.replace("-", " ").replace("_", " ").replace(".", " ")

    # Expand abbreviations
    words = n.split()
    expanded = []
    for w in words:
        if w in ABBREVIATIONS:
            expanded.append(ABBREVIATIONS[w])
        else:
            expanded.append(w)

    # Remove noise words
    filtered = [w for w in expanded if w not in NOISE_WORDS]
    if not filtered:
        filtered = expanded  # Don't remove everything

    return " ".join(filtered)


# ---------------------------------------------------------------------------
# Entity extraction from YAML
# ---------------------------------------------------------------------------

def extract_entities(system: dict) -> list[dict]:
    """Extract all named entities from a system YAML dict."""
    entities = []

    for ctx in system.get("contexts", []):
        if isinstance(ctx, dict) and ctx.get("id"):
            entities.append({
                "type": "context",
                "id": ctx["id"],
                "name": ctx.get("name", ctx["id"]),
                "description": ctx.get("description", ""),
            })

    for ctr in system.get("containers", []):
        if isinstance(ctr, dict) and ctr.get("id"):
            entities.append({
                "type": "container",
                "id": ctr["id"],
                "name": ctr.get("name", ctr["id"]),
                "technology": ctr.get("technology", ""),
                "description": ctr.get("description", ""),
            })

    for comp in system.get("components", []):
        if isinstance(comp, dict) and comp.get("id"):
            entities.append({
                "type": "component",
                "id": comp["id"],
                "name": comp.get("name", comp["id"]),
                "technology": comp.get("technology", ""),
                "description": comp.get("description", ""),
            })

    for ext in system.get("external_systems", []):
        if isinstance(ext, dict) and ext.get("id"):
            entities.append({
                "type": "external_system",
                "id": ext["id"],
                "name": ext.get("name", ext["id"]),
                "description": ext.get("description", ""),
            })

    for de in system.get("data_entities", []):
        if isinstance(de, dict) and de.get("id"):
            entities.append({
                "type": "data_entity",
                "id": de["id"],
                "name": de.get("name", de["id"]),
                "description": de.get("description", ""),
            })

    return entities


# ---------------------------------------------------------------------------
# Resolution engine
# ---------------------------------------------------------------------------

def find_duplicates(
    entities: list[dict],
    threshold: int = 80,
    same_type_only: bool = True,
) -> list[dict]:
    """Find potential duplicate entities using fuzzy matching.

    Args:
        entities: List of entity dicts from extract_entities().
        threshold: Minimum fuzzy match score (0-100) to consider a pair.
        same_type_only: If True, only compare entities of the same type.

    Returns:
        List of duplicate candidate dicts with match details.
    """
    if fuzz is None:
        return [{"error": "rapidfuzz not installed (pip install rapidfuzz)"}]

    duplicates = []
    seen_pairs: set[tuple[str, str]] = set()

    for i, a in enumerate(entities):
        for j, b in enumerate(entities):
            if j <= i:
                continue

            if same_type_only and a["type"] != b["type"]:
                continue

            pair_key = tuple(sorted([a["id"], b["id"]]))
            if pair_key in seen_pairs:
                continue

            # Compare normalized names
            norm_a = normalize_entity_name(a["name"])
            norm_b = normalize_entity_name(b["name"])

            name_score = fuzz.ratio(norm_a, norm_b)

            # Also compare IDs
            id_score = fuzz.ratio(
                normalize_entity_name(a["id"]),
                normalize_entity_name(b["id"]),
            )

            # Technology match bonus
            tech_bonus = 0
            if a.get("technology") and b.get("technology"):
                tech_score = fuzz.ratio(
                    a["technology"].lower(),
                    b["technology"].lower(),
                )
                if tech_score > 80:
                    tech_bonus = 10

            # Combined score: weighted average + tech bonus
            combined = (name_score * 0.6 + id_score * 0.4) + tech_bonus

            if combined >= threshold:
                seen_pairs.add(pair_key)
                duplicates.append({
                    "entity_a": {"id": a["id"], "name": a["name"], "type": a["type"]},
                    "entity_b": {"id": b["id"], "name": b["name"], "type": b["type"]},
                    "name_score": round(name_score, 1),
                    "id_score": round(id_score, 1),
                    "combined_score": round(combined, 1),
                    "normalized_a": norm_a,
                    "normalized_b": norm_b,
                    "suggested_canonical": a["id"] if len(a["id"]) <= len(b["id"]) else b["id"],
                })

    # Sort by combined score descending
    duplicates.sort(key=lambda d: d["combined_score"], reverse=True)
    return duplicates


def _rewrite_references(system: dict, old_id: str, new_id: str) -> int:
    """Rewrite all references from old_id to new_id across the system YAML.

    Returns the number of references rewritten.
    """
    count = 0

    # Reference fields in relationships that may point to entities
    REF_FIELDS = {
        "context_relationships": ["source_context", "target_context"],
        "container_relationships": ["source_container", "target_container"],
        "component_relationships": [
            "source_component", "target_component", "target_listener_ref",
        ],
    }

    # Rewrite relationship references
    for rel_key, fields in REF_FIELDS.items():
        for rel in system.get(rel_key, []):
            if not isinstance(rel, dict):
                continue
            for field in fields:
                if rel.get(field) == old_id:
                    rel[field] = new_id
                    count += 1

    # Rewrite container→context references
    for ctr in system.get("containers", []):
        if isinstance(ctr, dict) and ctr.get("context_id") == old_id:
            ctr["context_id"] = new_id
            count += 1

    # Rewrite component→container references
    for comp in system.get("components", []):
        if isinstance(comp, dict) and comp.get("container_id") == old_id:
            comp["container_id"] = new_id
            count += 1

    # Rewrite data_entities references in relationships
    for rel in system.get("component_relationships", []):
        if isinstance(rel, dict) and isinstance(rel.get("data_entities"), list):
            for i, de_id in enumerate(rel["data_entities"]):
                if de_id == old_id:
                    rel["data_entities"][i] = new_id
                    count += 1

    # Rewrite trust_boundary zone references
    for tb in system.get("trust_boundaries", []):
        if isinstance(tb, dict):
            if tb.get("source_zone") == old_id:
                tb["source_zone"] = new_id
                count += 1
            if tb.get("target_zone") == old_id:
                tb["target_zone"] = new_id
                count += 1

    return count


def _remove_entity_by_id(system: dict, entity_id: str, entity_type: str) -> bool:
    """Remove a duplicate entity from its collection. Returns True if removed."""
    TYPE_TO_KEY = {
        "context": "contexts",
        "container": "containers",
        "component": "components",
        "external_system": "external_systems",
        "data_entity": "data_entities",
    }
    key = TYPE_TO_KEY.get(entity_type, "")
    if not key or key not in system:
        return False

    before = len(system[key])
    system[key] = [e for e in system[key] if not (isinstance(e, dict) and e.get("id") == entity_id)]
    return len(system[key]) < before


def resolve_duplicates(
    system: dict,
    duplicates: list[dict],
    *,
    auto_merge: bool = False,
) -> dict:
    """Apply duplicate resolutions to a system YAML dict.

    Args:
        system: The system YAML dict.
        duplicates: Duplicate pairs from find_duplicates().
        auto_merge: If True, automatically merge high-confidence duplicates
                    (score >= 95), rewriting all references to the canonical ID
                    and removing the duplicate entity.

    Returns:
        Dict with resolution summary and optionally modified system.
    """
    resolutions = []

    for dup in duplicates:
        if dup.get("error"):
            continue

        resolution = {
            "pair": f"{dup['entity_a']['id']} <-> {dup['entity_b']['id']}",
            "score": dup["combined_score"],
            "suggested_canonical": dup["suggested_canonical"],
            "action": "review",  # Default: manual review
        }

        if auto_merge and dup["combined_score"] >= 95:
            canonical = dup["suggested_canonical"]
            obsolete_id = (
                dup["entity_b"]["id"]
                if canonical == dup["entity_a"]["id"]
                else dup["entity_a"]["id"]
            )
            obsolete_type = (
                dup["entity_b"]["type"]
                if canonical == dup["entity_a"]["id"]
                else dup["entity_a"]["type"]
            )

            refs_rewritten = _rewrite_references(system, obsolete_id, canonical)
            removed = _remove_entity_by_id(system, obsolete_id, obsolete_type)

            resolution["action"] = "auto-merged"
            resolution["refs_rewritten"] = refs_rewritten
            resolution["entity_removed"] = removed
        elif dup["combined_score"] >= 90:
            resolution["action"] = "likely-duplicate"
        elif dup["combined_score"] >= 80:
            resolution["action"] = "possible-duplicate"

        resolutions.append(resolution)

    return {
        "total_entities": len(extract_entities(system)),
        "duplicate_candidates": len(resolutions),
        "auto_merged": sum(1 for r in resolutions if r["action"] == "auto-merged"),
        "needs_review": sum(1 for r in resolutions if r["action"] != "auto-merged"),
        "resolutions": resolutions,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Cross-document entity resolution for Doc2ArchAgent.",
    )
    parser.add_argument("system_yaml", type=Path, help="Path to system.yaml")
    parser.add_argument("--threshold", type=int, default=80,
                        help="Minimum fuzzy match score (0-100, default: 80)")
    parser.add_argument("--cross-type", action="store_true",
                        help="Compare entities across different types")
    parser.add_argument("--auto-merge", action="store_true",
                        help="Auto-merge duplicates with score >= 95")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show duplicates without modifying files")
    parser.add_argument("--format", choices=["json", "text"], default="text",
                        help="Output format")

    args = parser.parse_args()

    if not args.system_yaml.exists():
        print(f"Error: {args.system_yaml} not found", file=sys.stderr)
        sys.exit(1)

    with open(args.system_yaml) as f:
        system = yaml.safe_load(f) or {}

    entities = extract_entities(system)
    duplicates = find_duplicates(
        entities,
        threshold=args.threshold,
        same_type_only=not args.cross_type,
    )

    result = resolve_duplicates(system, duplicates, auto_merge=args.auto_merge and not args.dry_run)

    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        print(f"ENTITY RESOLUTION REPORT")
        print(f"{'=' * 50}")
        print(f"Total entities:       {result['total_entities']}")
        print(f"Duplicate candidates: {result['duplicate_candidates']}")
        if result['auto_merged'] > 0:
            print(f"Auto-merged:          {result['auto_merged']}")
        if result['needs_review'] > 0:
            print(f"Needs review:         {result['needs_review']}")

        if result["resolutions"]:
            print(f"\nDuplicate pairs:")
            for r in result["resolutions"]:
                icon = {"auto-merged": "✓", "likely-duplicate": "⚠",
                        "possible-duplicate": "?", "review": "?"}.get(r["action"], "?")
                print(f"  {icon} {r['pair']} (score: {r['score']:.0f}) → {r['action']}")
                print(f"    Suggested canonical: {r['suggested_canonical']}")
        else:
            print(f"\nNo duplicates found above threshold {args.threshold}.")


if __name__ == "__main__":
    main()
