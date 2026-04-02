#!/usr/bin/env python3
# Copyright (c) 2026 Michael J. Read. All rights reserved.
# SPDX-License-Identifier: BUSL-1.1
"""Classify document sections as network, product, security, or integration.

Reads a text/markdown document, splits it into sections by headings, and
classifies each section by architectural concern. Used by @doc-collector to
route mixed-content documents to the correct pattern's contexts/sources/.

Usage:
    python tools/classify-sections.py context/my-system/vendor-guide.md
    python tools/classify-sections.py context/my-system/vendor-guide.md --output-dir /tmp/split
    python tools/classify-sections.py context/my-system/vendor-guide.md --dry-run

Output:
    JSON classification manifest to stdout. With --output-dir, also writes
    split section files to the specified directory.
"""

import argparse
import json
import re
import sys
from pathlib import Path

# --- Classification keyword sets ---

NETWORK_KEYWORDS = {
    'firewall', 'vlan', 'subnet', 'dmz', 'zone', 'routing', 'segmentation',
    'network topology', 'cidr', 'acl', 'ingress', 'egress', 'load balancer',
    'waf', 'web application firewall', 'network diagram', 'ip address',
    'network zone', 'network design', 'data center network', 'vpn',
    'proxy', 'reverse proxy', 'nat', 'gateway', 'network security',
    'network architecture', 'network config', 'network requirement',
    'bandwidth', 'latency', 'network interface', 'nic', 'switch', 'router',
}

PRODUCT_KEYWORDS = {
    'container', 'component', 'queue', 'api', 'service', 'deployment',
    'installation', 'configuration', 'administration', 'console',
    'application', 'server', 'database', 'cluster', 'instance',
    'queue manager', 'channel', 'listener', 'endpoint', 'client',
    'connection factory', 'topic', 'subscription', 'message',
    'web console', 'admin console', 'management', 'monitoring',
    'high availability', 'failover', 'backup', 'restore', 'upgrade',
    'schema', 'table', 'index', 'replication', 'partition',
}

SECURITY_KEYWORDS = {
    'tls', 'ssl', 'certificate', 'authentication', 'authorization',
    'encryption', 'cipher', 'key management', 'ldap', 'oauth', 'saml',
    'mfa', 'multi-factor', 'rbac', 'role-based', 'access control',
    'security policy', 'audit', 'compliance', 'pci', 'sox', 'gdpr',
    'vulnerability', 'patch', 'hardening', 'security config',
    'keystore', 'truststore', 'credential', 'password', 'token',
    'mutual auth', 'mtls', 'certificate auth',
}

INTEGRATION_KEYWORDS = {
    'integration', 'interface', 'protocol', 'rest', 'soap', 'grpc',
    'webhook', 'callback', 'event', 'publish', 'subscribe', 'adapter',
    'connector', 'bridge', 'gateway', 'middleware', 'edi', 'batch',
    'file transfer', 'sftp', 'mq client', 'jms', 'amqp', 'kafka',
    'data flow', 'message flow', 'request-response', 'async',
}

# Heading patterns
HEADING_RE = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
UNDERLINE_HEADING_RE = re.compile(r'^(.+)\n[=\-]{3,}$', re.MULTILINE)


def split_sections(text: str) -> list[dict]:
    """Split document text into sections by markdown headings."""
    sections = []
    lines = text.split('\n')
    current_title = "Introduction"
    current_level = 0
    current_lines: list[str] = []
    current_start = 1

    for i, line in enumerate(lines, 1):
        heading_match = HEADING_RE.match(line)
        if heading_match:
            # Save previous section
            if current_lines:
                sections.append({
                    "title": current_title,
                    "level": current_level,
                    "start_line": current_start,
                    "end_line": i - 1,
                    "content": '\n'.join(current_lines),
                })
            current_title = heading_match.group(2).strip()
            current_level = len(heading_match.group(1))
            current_lines = []
            current_start = i
        else:
            current_lines.append(line)

    # Last section
    if current_lines:
        sections.append({
            "title": current_title,
            "level": current_level,
            "start_line": current_start,
            "end_line": len(lines),
            "content": '\n'.join(current_lines),
        })

    return sections


def classify_section(section: dict) -> dict:
    """Classify a section by its content and title."""
    text = (section.get("title", "") + " " + section.get("content", "")).lower()

    scores = {
        "network": 0.0,
        "product": 0.0,
        "security": 0.0,
        "integration": 0.0,
    }

    for keyword in NETWORK_KEYWORDS:
        if keyword in text:
            scores["network"] += 1.0
    for keyword in PRODUCT_KEYWORDS:
        if keyword in text:
            scores["product"] += 1.0
    for keyword in SECURITY_KEYWORDS:
        if keyword in text:
            scores["security"] += 1.0
    for keyword in INTEGRATION_KEYWORDS:
        if keyword in text:
            scores["integration"] += 1.0

    # Title keywords get double weight
    title_lower = section.get("title", "").lower()
    for keyword in NETWORK_KEYWORDS:
        if keyword in title_lower:
            scores["network"] += 2.0
    for keyword in PRODUCT_KEYWORDS:
        if keyword in title_lower:
            scores["product"] += 2.0
    for keyword in SECURITY_KEYWORDS:
        if keyword in title_lower:
            scores["security"] += 2.0
    for keyword in INTEGRATION_KEYWORDS:
        if keyword in title_lower:
            scores["integration"] += 2.0

    total = sum(scores.values())
    if total == 0:
        return {
            "classification": "product",  # default to product
            "confidence": 0.5,
            "scores": scores,
        }

    # Normalize scores
    normalized = {k: round(v / total, 3) for k, v in scores.items()}

    # Primary classification
    primary = max(scores, key=scores.get)
    confidence = round(scores[primary] / total, 2)

    # Check if ambiguous (top two are close)
    sorted_scores = sorted(scores.values(), reverse=True)
    if len(sorted_scores) >= 2 and sorted_scores[0] > 0:
        ratio = sorted_scores[1] / sorted_scores[0]
        if ratio > 0.7:
            confidence = max(0.5, confidence - 0.15)

    # Security sections that primarily discuss product security config
    # should be routed to product (the product's own security needs)
    if primary == "security" and scores["product"] > scores["network"]:
        primary = "product"
        confidence = max(0.6, confidence - 0.1)

    return {
        "classification": primary,
        "confidence": round(min(confidence, 0.99), 2),
        "scores": normalized,
    }


def classify_document(file_path: Path) -> dict:
    """Classify all sections in a document."""
    with open(file_path) as f:
        text = f.read()

    sections = split_sections(text)
    results = []

    for section in sections:
        classification = classify_section(section)
        results.append({
            "title": section["title"],
            "start_line": section["start_line"],
            "end_line": section["end_line"],
            "line_count": section["end_line"] - section["start_line"] + 1,
            "classification": classification["classification"],
            "confidence": classification["confidence"],
            "scores": classification["scores"],
        })

    # Summary
    class_counts = {}
    for r in results:
        c = r["classification"]
        class_counts[c] = class_counts.get(c, 0) + 1

    return {
        "document": str(file_path),
        "total_sections": len(results),
        "classification_summary": class_counts,
        "sections": results,
    }


def split_and_write(file_path: Path, output_dir: Path) -> dict:
    """Classify, split, and write section files to output directory."""
    result = classify_document(file_path)

    with open(file_path) as f:
        text = f.read()

    sections = split_sections(text)
    stem = file_path.stem

    output_dir.mkdir(parents=True, exist_ok=True)

    # Group sections by classification
    groups: dict[str, list[dict]] = {}
    for section, classification in zip(sections, result["sections"]):
        cls = classification["classification"]
        if cls not in groups:
            groups[cls] = []
        groups[cls].append(section)

    files_written = []
    for cls, section_list in groups.items():
        out_file = output_dir / f"{stem}_{cls}-sections.md"
        with open(out_file, "w") as f:
            f.write(f"# {stem} — {cls} sections\n\n")
            f.write(f"# Split from: {file_path.name}\n")
            f.write(f"# Classification: {cls}\n\n")
            for section in section_list:
                level = section.get("level", 2) or 2
                f.write(f"{'#' * level} {section['title']}\n\n")
                f.write(section["content"])
                f.write("\n\n")
        files_written.append(str(out_file))

    result["files_written"] = files_written
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Classify document sections by architectural concern")
    parser.add_argument("document", type=Path,
                        help="Path to text/markdown document")
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="Directory to write split section files")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print classification without writing files")
    args = parser.parse_args()

    if not args.document.exists():
        print(json.dumps({
            "error": f"File not found: {args.document}",
        }))
        sys.exit(1)

    if args.dry_run or not args.output_dir:
        result = classify_document(args.document)
    else:
        result = split_and_write(args.document, args.output_dir)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
