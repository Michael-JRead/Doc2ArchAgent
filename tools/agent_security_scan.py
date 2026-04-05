#!/usr/bin/env python3
# Copyright (c) 2026 Michael J. Read. All rights reserved.
# SPDX-License-Identifier: BUSL-1.1
"""
Security scanner for Doc2ArchAgent agent configuration.

Checks agent definitions, skills, rules, and instincts for common
security issues including missing scope boundaries, tool permissions,
error recovery, hallucination guards, and hardcoded secrets.

Usage:
    python tools/agent_security_scan.py [--format text|json] [--strict]

Exit codes:
    0 — No issues found
    1 — Issues found (non-critical)
    2 — Critical issues found
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import List, Tuple

# Severity, Location, Detail
Finding = Tuple[str, str, str]

FINDINGS: List[Finding] = []

PROJECT_ROOT = Path(__file__).parent.parent
AGENTS_DIR = PROJECT_ROOT / ".github" / "agents"
SKILLS_DIR = PROJECT_ROOT / ".github" / "skills"
INSTINCTS_DIR = PROJECT_ROOT / "instincts"
RULES_DIR = PROJECT_ROOT / "rules"


def check_scope_boundaries(agent_file: Path) -> None:
    """Check if agent has explicit scope boundaries."""
    content = agent_file.read_text(encoding="utf-8")
    if "## SCOPE" not in content.upper():
        # Check for scope-like content
        has_scope = any(
            term in content
            for term in ["NEVER modify", "NEVER create", "I ONLY", "I create/modify"]
        )
        if not has_scope:
            FINDINGS.append(
                (
                    "MEDIUM",
                    agent_file.name,
                    "Missing scope restrictions — agent has no explicit "
                    "file access boundaries",
                )
            )


def check_tool_permissions(agent_file: Path) -> None:
    """Check if agent has explicit tool permissions in frontmatter."""
    content = agent_file.read_text(encoding="utf-8")
    if not content.startswith("---"):
        FINDINGS.append(
            ("LOW", agent_file.name, "Missing YAML frontmatter — no tool declarations")
        )
        return

    end = content.find("---", 3)
    if end == -1:
        return

    frontmatter = content[3:end]
    if "tools:" not in frontmatter:
        FINDINGS.append(
            ("MEDIUM", agent_file.name, "Missing tools: declaration in frontmatter")
        )


def check_error_recovery(agent_file: Path) -> None:
    """Check if agent has error recovery instructions."""
    content = agent_file.read_text(encoding="utf-8")
    error_terms = ["error recovery", "error handling", "if validation fails", "✗"]
    if not any(term.lower() in content.lower() for term in error_terms):
        FINDINGS.append(
            ("LOW", agent_file.name, "Missing error recovery instructions")
        )


def check_hallucination_guards(agent_file: Path) -> None:
    """Check if extraction agents have hallucination guards."""
    content = agent_file.read_text(encoding="utf-8")
    name = agent_file.stem.replace(".agent", "")
    extraction_agents = ["doc-collector", "doc-extractor", "architect"]
    if name in extraction_agents:
        guard_terms = [
            "hallucination",
            "NOT_STATED",
            "zero-hallucination",
            "NEVER infer",
            "EXTRACT ONLY",
        ]
        if not any(term in content for term in guard_terms):
            FINDINGS.append(
                (
                    "HIGH",
                    agent_file.name,
                    "Extraction agent missing hallucination guards "
                    "(no zero-hallucination reference)",
                )
            )


def check_instinct_references(agent_file: Path) -> None:
    """Check if agent references shared instincts."""
    content = agent_file.read_text(encoding="utf-8")
    if "instincts/" not in content and "INSTINCTS" not in content:
        FINDINGS.append(
            (
                "LOW",
                agent_file.name,
                "No instinct references — agent doesn't use shared "
                "behavioral patterns",
            )
        )


def check_secrets_in_files(directory: Path) -> None:
    """Check for hardcoded secrets or API keys."""
    secret_patterns = [
        (r"sk-[a-zA-Z0-9]{32,}", "OpenAI API key pattern"),
        (r"ghp_[a-zA-Z0-9]{36}", "GitHub personal access token"),
        (r"glpat-[a-zA-Z0-9\-]{20,}", "GitLab personal access token"),
        (
            r'(?:api[_-]?key|secret|password|token)\s*[:=]\s*["\'][^"\']{8,}["\']',
            "Hardcoded credential",
        ),
    ]
    for f in directory.rglob("*.md"):
        try:
            content = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for pattern, description in secret_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                rel_path = f.relative_to(PROJECT_ROOT)
                FINDINGS.append(
                    ("CRITICAL", str(rel_path), f"Possible {description} found")
                )


def check_handoff_validation(agent_file: Path) -> None:
    """Check if agent validates before handoff."""
    content = agent_file.read_text(encoding="utf-8")
    has_handoffs = "handoffs:" in content or "handoff" in content.lower()
    has_validation = any(
        term in content
        for term in ["validate.py", "validate before", "validation_passed"]
    )
    if has_handoffs and not has_validation:
        FINDINGS.append(
            (
                "LOW",
                agent_file.name,
                "Agent has handoffs but no pre-handoff validation reference",
            )
        )


def run_scan() -> None:
    """Run all security checks."""
    # Check agent files
    if AGENTS_DIR.exists():
        for agent_file in sorted(AGENTS_DIR.glob("*.agent.md")):
            check_scope_boundaries(agent_file)
            check_tool_permissions(agent_file)
            check_error_recovery(agent_file)
            check_hallucination_guards(agent_file)
            check_instinct_references(agent_file)
            check_handoff_validation(agent_file)

    # Check for secrets in all markdown directories
    for directory in [AGENTS_DIR, SKILLS_DIR, INSTINCTS_DIR, RULES_DIR]:
        if directory.exists():
            check_secrets_in_files(directory)


def format_text() -> str:
    """Format findings as human-readable text."""
    if not FINDINGS:
        return "\n  No security issues found. Grade: A\n"

    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    sorted_findings = sorted(
        FINDINGS, key=lambda x: severity_order.get(x[0], 4)
    )

    lines = [
        "",
        "=" * 60,
        f"AGENT SECURITY SCAN — {len(FINDINGS)} finding(s)",
        "=" * 60,
        "",
    ]

    for severity, location, detail in sorted_findings:
        lines.append(f"[{severity}] {location}")
        lines.append(f"  {detail}")
        lines.append("")

    # Grade
    critical = sum(1 for f in FINDINGS if f[0] == "CRITICAL")
    high = sum(1 for f in FINDINGS if f[0] == "HIGH")
    medium = sum(1 for f in FINDINGS if f[0] == "MEDIUM")
    low = sum(1 for f in FINDINGS if f[0] == "LOW")

    if critical > 0:
        grade = "F"
    elif high > 0:
        grade = "D"
    elif medium > 2:
        grade = "C"
    elif medium > 0:
        grade = "B"
    elif low > 0:
        grade = "B+"
    else:
        grade = "A"

    lines.append(
        f"Grade: {grade} | CRITICAL: {critical} | HIGH: {high} | "
        f"MEDIUM: {medium} | LOW: {low}"
    )
    return "\n".join(lines)


def format_json() -> str:
    """Format findings as JSON."""
    return json.dumps(
        {
            "agent_security_scan": {
                "findings_count": len(FINDINGS),
                "critical": sum(1 for f in FINDINGS if f[0] == "CRITICAL"),
                "high": sum(1 for f in FINDINGS if f[0] == "HIGH"),
                "medium": sum(1 for f in FINDINGS if f[0] == "MEDIUM"),
                "low": sum(1 for f in FINDINGS if f[0] == "LOW"),
                "findings": [
                    {
                        "severity": f[0],
                        "location": f[1],
                        "detail": f[2],
                    }
                    for f in FINDINGS
                ],
            }
        },
        indent=2,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Security scanner for agent configuration"
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat LOW findings as failures",
    )
    args = parser.parse_args()

    run_scan()

    if args.format == "json":
        print(format_json())
    else:
        print(format_text())

    # Exit code
    critical = sum(1 for f in FINDINGS if f[0] == "CRITICAL")
    high = sum(1 for f in FINDINGS if f[0] == "HIGH")

    if critical > 0:
        sys.exit(2)
    elif high > 0 or (args.strict and FINDINGS):
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
