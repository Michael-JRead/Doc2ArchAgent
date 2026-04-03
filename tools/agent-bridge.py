#!/usr/bin/env python3
# Copyright (c) 2026 Michael J. Read. All rights reserved.
# SPDX-License-Identifier: BUSL-1.1
"""Unified bridge for Copilot agents to invoke deterministic tools.

Provides a single entry point for common operations so agents do not
need to know individual tool scripts.

Usage:
    python tools/agent-bridge.py validate <system.yaml> [networks.yaml] [--format table|json|sarif]
    python tools/agent-bridge.py threat <system.yaml> [--networks <networks.yaml>] [--format table|json|sarif]
    python tools/agent-bridge.py confidence <provenance.yaml> [--threshold 95]
    python tools/agent-bridge.py compose <manifest.yaml> [--validate] [--dry-run]
    python tools/agent-bridge.py check-handoff [<source-agent> <target-agent>]
    python tools/agent-bridge.py check-handoff --all
    python tools/agent-bridge.py diagram validate <file-or-directory>
"""

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
AGENTS_DIR = PROJECT_ROOT / ".github" / "agents"


def _parse_agent_frontmatter(agent_path: Path) -> dict:
    """Parse YAML frontmatter from an .agent.md file."""
    text = agent_path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}

    end = text.index("---", 3)
    frontmatter_text = text[3:end].strip()

    # Simple YAML parsing for the fields we need
    result = {"agents": [], "handoffs": []}
    in_handoffs = False
    current_handoff = {}

    for line in frontmatter_text.split("\n"):
        stripped = line.strip()

        if stripped.startswith("agents:"):
            # Parse inline list: agents: ['a', 'b']
            match = re.search(r"\[(.+)\]", stripped)
            if match:
                result["agents"] = [
                    s.strip().strip("'\"")
                    for s in match.group(1).split(",")
                ]
            continue

        if stripped == "handoffs:":
            in_handoffs = True
            continue

        if in_handoffs:
            if stripped.startswith("- label:"):
                if current_handoff:
                    result["handoffs"].append(current_handoff)
                current_handoff = {"label": stripped.split(":", 1)[1].strip().strip('"')}
            elif stripped.startswith("agent:"):
                current_handoff["agent"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("prompt:"):
                current_handoff["prompt"] = stripped.split(":", 1)[1].strip().strip('"')
            elif not stripped.startswith(("- ", "  ")) and ":" in stripped:
                # End of handoffs section
                if current_handoff:
                    result["handoffs"].append(current_handoff)
                    current_handoff = {}
                in_handoffs = False

    if current_handoff:
        result["handoffs"].append(current_handoff)

    return result


def cmd_validate(args):
    """Run validation via tools/validate.py."""
    import subprocess
    cmd = [sys.executable, str(PROJECT_ROOT / "tools" / "validate.py")]
    cmd.append(str(args.file))
    if args.networks:
        cmd.append(str(args.networks))
    cmd.extend(["--format", args.format])
    if args.strict:
        cmd.append("--strict")
    result = subprocess.run(cmd, capture_output=False)
    sys.exit(result.returncode)


def cmd_threat(args):
    """Run threat analysis via tools/threat-rules.py."""
    import subprocess
    cmd = [sys.executable, str(PROJECT_ROOT / "tools" / "threat-rules.py")]
    cmd.append(str(args.file))
    if args.networks:
        cmd.extend(["--networks", str(args.networks)])
    if args.deployment:
        cmd.extend(["--deployment", str(args.deployment)])
    cmd.extend(["--format", args.format])
    result = subprocess.run(cmd, capture_output=False)
    sys.exit(result.returncode)


def cmd_confidence(args):
    """Run confidence scoring via tools/confidence.py."""
    import subprocess
    cmd = [sys.executable, str(PROJECT_ROOT / "tools" / "confidence.py")]
    subcmd = getattr(args, "confidence_command", "score")
    cmd.append(subcmd)
    if subcmd == "score":
        cmd.extend(["--threshold", str(args.threshold)])
        if args.method:
            cmd.extend(["--method", args.method])
        if getattr(args, "field_present", False):
            cmd.append("--field-present")
        if getattr(args, "source_count", None) is not None:
            cmd.extend(["--source-count", str(args.source_count)])
    elif subcmd == "enrich":
        if getattr(args, "provenance", None):
            cmd.append(str(args.provenance))
        cmd.extend(["--threshold", str(args.threshold)])
    elif subcmd == "report":
        if getattr(args, "provenance", None):
            cmd.append(str(args.provenance))
        cmd.extend(["--threshold", str(args.threshold)])
    result = subprocess.run(cmd, capture_output=False)
    sys.exit(result.returncode)


def cmd_compose(args):
    """Run deployment composition via tools/compose.py."""
    import subprocess
    cmd = [sys.executable, str(PROJECT_ROOT / "tools" / "compose.py")]
    cmd.append(str(args.manifest))
    if args.validate:
        cmd.append("--validate")
    if args.dry_run:
        cmd.append("--dry-run")
    result = subprocess.run(cmd, capture_output=False)
    sys.exit(result.returncode)


def cmd_check_handoff(args):
    """Validate agent handoff declarations are consistent."""
    if not AGENTS_DIR.exists():
        print(f"Error: {AGENTS_DIR} not found", file=sys.stderr)
        sys.exit(1)

    agent_files = sorted(AGENTS_DIR.glob("*.agent.md"))
    agents = {}
    for af in agent_files:
        name = af.stem.replace(".agent", "")
        agents[name] = _parse_agent_frontmatter(af)

    if args.all:
        # Check all agents
        errors = []
        for name, data in sorted(agents.items()):
            handoff_targets = [h["agent"] for h in data["handoffs"]]
            declared = set(data["agents"])
            for target in handoff_targets:
                if target not in declared:
                    errors.append(
                        f"  {name}: handoff target '{target}' not in agents: {sorted(declared)}"
                    )

        if errors:
            print(f"HANDOFF CONSISTENCY ERRORS ({len(errors)}):")
            for e in errors:
                print(e)
            sys.exit(1)
        else:
            print(f"All {len(agents)} agents have consistent handoff declarations.")
            # Print summary
            for name, data in sorted(agents.items()):
                handoff_targets = [h["agent"] for h in data["handoffs"]]
                print(f"  {name}: agents={sorted(data['agents'])} handoffs={handoff_targets}")
            sys.exit(0)

    elif args.source and args.target:
        source_data = agents.get(args.source)
        if not source_data:
            print(f"Error: Agent '{args.source}' not found", file=sys.stderr)
            sys.exit(1)

        handoff_targets = [h["agent"] for h in source_data["handoffs"]]
        declared = set(source_data["agents"])

        is_in_agents = args.target in declared
        is_in_handoffs = args.target in handoff_targets

        result = {
            "source": args.source,
            "target": args.target,
            "in_agents_list": is_in_agents,
            "in_handoffs_list": is_in_handoffs,
            "valid": is_in_agents and is_in_handoffs,
        }
        print(json.dumps(result, indent=2))
        sys.exit(0 if result["valid"] else 1)
    else:
        print("Error: Provide --all or <source-agent> <target-agent>", file=sys.stderr)
        sys.exit(1)


def cmd_diagram(args):
    """Delegate to validate-diagram.py for diagram syntax validation."""
    import subprocess

    validate_script = PROJECT_ROOT / "tools" / "validate-diagram.py"
    if not validate_script.exists():
        print("Error: tools/validate-diagram.py not found", file=sys.stderr)
        sys.exit(1)

    path = args.path
    if path.is_dir():
        cmd = [sys.executable, str(validate_script), "all", str(path)]
    elif path.suffix == ".puml":
        cmd = [sys.executable, str(validate_script), "plantuml", str(path)]
    elif path.suffix == ".drawio":
        cmd = [sys.executable, str(validate_script), "drawio", str(path)]
    elif path.suffix == ".md":
        cmd = [sys.executable, str(validate_script), "mermaid", str(path)]
    else:
        print(f"Error: Unknown diagram format for '{path}'", file=sys.stderr)
        sys.exit(1)

    if hasattr(args, "format") and args.format == "json":
        cmd.append("--format")
        cmd.append("json")

    result = subprocess.run(cmd, capture_output=False)
    sys.exit(result.returncode)


def main():
    parser = argparse.ArgumentParser(
        description="Unified bridge for Copilot agents to invoke deterministic tools.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # validate
    p_val = subparsers.add_parser("validate", help="Run YAML validation")
    p_val.add_argument("file", type=Path, help="system.yaml to validate")
    p_val.add_argument("networks", type=Path, nargs="?", default=None,
                       help="Optional networks.yaml")
    p_val.add_argument("--format", choices=["json", "table", "sarif"], default="table")
    p_val.add_argument("--strict", action="store_true")

    # threat
    p_threat = subparsers.add_parser("threat", help="Run threat analysis")
    p_threat.add_argument("file", type=Path, help="system.yaml to analyze")
    p_threat.add_argument("--networks", type=Path, default=None)
    p_threat.add_argument("--deployment", type=Path, default=None)
    p_threat.add_argument("--format", choices=["json", "table", "sarif"], default="table")

    # confidence
    p_conf = subparsers.add_parser("confidence", help="Score confidence")
    conf_sub = p_conf.add_subparsers(dest="confidence_command")
    conf_score = conf_sub.add_parser("score", help="Calculate a confidence score")
    conf_score.add_argument("--threshold", type=int, default=95)
    conf_score.add_argument("--method", default=None,
                            help="Extraction method (native_text, ocr, vlm, etc.)")
    conf_score.add_argument("--field-present", action="store_true",
                            help="Field was explicitly stated in source")
    conf_score.add_argument("--source-count", type=int, default=1,
                            help="Number of confirming sources")
    conf_enrich = conf_sub.add_parser("enrich",
                                       help="Enrich provenance YAML with numeric scores")
    conf_enrich.add_argument("provenance", type=Path, help="provenance.yaml path")
    conf_enrich.add_argument("--threshold", type=int, default=95)
    conf_report = conf_sub.add_parser("report",
                                       help="Generate markdown confidence report")
    conf_report.add_argument("provenance", type=Path, help="provenance.yaml path")
    conf_report.add_argument("--threshold", type=int, default=95)

    # compose
    p_comp = subparsers.add_parser("compose", help="Compose deployment from manifest")
    p_comp.add_argument("manifest", type=Path, help="manifest.yaml path")
    p_comp.add_argument("--validate", action="store_true")
    p_comp.add_argument("--dry-run", action="store_true")

    # check-handoff
    p_handoff = subparsers.add_parser("check-handoff",
                                       help="Validate agent handoff declarations")
    p_handoff.add_argument("source", nargs="?", default=None, help="Source agent name")
    p_handoff.add_argument("target", nargs="?", default=None, help="Target agent name")
    p_handoff.add_argument("--all", action="store_true",
                           help="Check all agents for consistency")

    # diagram
    p_diagram = subparsers.add_parser("diagram",
                                       help="Diagram validation and utilities")
    diagram_sub = p_diagram.add_subparsers(dest="diagram_command", required=True)
    p_diag_val = diagram_sub.add_parser("validate",
                                         help="Validate diagram syntax")
    p_diag_val.add_argument("path", type=Path,
                            help="Diagram file or directory to validate")
    p_diag_val.add_argument("--format", choices=["text", "json"], default="text")

    args = parser.parse_args()

    commands = {
        "validate": cmd_validate,
        "threat": cmd_threat,
        "confidence": cmd_confidence,
        "compose": cmd_compose,
        "check-handoff": cmd_check_handoff,
        "diagram": cmd_diagram,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
