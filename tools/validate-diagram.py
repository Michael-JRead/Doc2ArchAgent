#!/usr/bin/env python3
# Copyright (c) 2026 Michael J. Read. All rights reserved.
# SPDX-License-Identifier: BUSL-1.1
"""Deterministic syntax validation for generated diagram files.

Validates Mermaid, PlantUML, and Draw.io diagram files against known
syntax rules to catch common LLM hallucination errors before they
reach users or external tools.

Usage:
    python tools/validate-diagram.py mermaid <file.md>
    python tools/validate-diagram.py plantuml <file.puml>
    python tools/validate-diagram.py drawio <file.drawio>
    python tools/validate-diagram.py all <diagrams-directory>

Exit codes:
    0 — No errors
    1 — Errors found
"""

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


# ---------------------------------------------------------------------------
# Mermaid Validation
# ---------------------------------------------------------------------------

def validate_mermaid(filepath: Path) -> dict:
    """Validate Mermaid flowchart syntax for common errors."""
    text = filepath.read_text(encoding="utf-8")
    errors = []
    warnings = []

    # Extract mermaid code block content
    mermaid_blocks = re.findall(r'```mermaid\s*\n(.*?)```', text, re.DOTALL)
    if not mermaid_blocks:
        # Try raw mermaid (no code fence)
        if text.strip().startswith("flowchart") or text.strip().startswith("graph"):
            mermaid_blocks = [text]
        else:
            errors.append("No mermaid code block found (expected ```mermaid ... ```)")
            return {"valid": False, "errors": errors, "warnings": warnings}

    for block in mermaid_blocks:
        lines = block.strip().split("\n")
        if not lines:
            errors.append("Empty mermaid block")
            continue

        # Check 1: Must start with flowchart or graph declaration
        first_line = lines[0].strip()
        # Skip init directives
        content_start = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("%%{") or stripped == "":
                continue
            content_start = i
            break

        decl_line = lines[content_start].strip() if content_start < len(lines) else ""
        if not re.match(r'^(flowchart|graph)\s+(TB|TD|BT|LR|RL)', decl_line):
            errors.append(
                f"Line {content_start + 1}: Must start with 'flowchart <direction>' "
                f"(TB|TD|BT|LR|RL), got: '{decl_line[:50]}'"
            )

        # Check 2: Deprecated 'graph' usage
        if decl_line.startswith("graph "):
            warnings.append(
                f"Line {content_start + 1}: 'graph' is deprecated, use 'flowchart' instead"
            )

        # Check 3: Balanced subgraph/end pairs
        subgraph_count = 0
        end_count = 0
        subgraph_stack = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("subgraph "):
                subgraph_count += 1
                subgraph_stack.append(i)
            elif stripped == "end":
                end_count += 1
                if subgraph_stack:
                    subgraph_stack.pop()
                else:
                    errors.append(f"Line {i}: 'end' without matching 'subgraph'")

        if subgraph_stack:
            for line_num in subgraph_stack:
                errors.append(f"Line {line_num}: 'subgraph' without matching 'end'")

        # Check 4: 'End' or 'END' instead of 'end'
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped in ("End", "END", "eND"):
                errors.append(
                    f"Line {i}: '{stripped}' must be lowercase 'end' — "
                    f"capitalized forms break Mermaid parsing"
                )

        # Check 5: Collect defined node IDs and check edge references
        node_ids = set()
        edge_refs = []

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            # Skip comments and directives
            if stripped.startswith("%%") or stripped.startswith("classDef") or stripped.startswith("class "):
                continue
            if stripped.startswith("subgraph "):
                # Extract subgraph id
                match = re.match(r'subgraph\s+(\S+)', stripped)
                if match:
                    node_ids.add(match.group(1).split("[")[0].split("(")[0])
                continue

            # Node definition: id["label"] or id[label] or id(label) etc.
            node_match = re.match(r'^(\w[\w-]*)\s*[\[\({\|>]', stripped)
            if node_match:
                node_ids.add(node_match.group(1))

            # Edge: source -->|label| target or source --> target
            edge_match = re.findall(
                r'(\w[\w-]*)\s*(?:-->|-.->|==>|---|-.-|===|~~~|--[ox]|<-->)\s*(?:\|[^|]*\|\s*)?(\w[\w-]*)',
                stripped
            )
            for src, tgt in edge_match:
                edge_refs.append((i, src, tgt))

        # Check edge references point to defined nodes
        for line_num, src, tgt in edge_refs:
            if src not in node_ids and src != "Legend":
                warnings.append(
                    f"Line {line_num}: Edge source '{src}' not found as defined node"
                )
            if tgt not in node_ids and tgt != "Legend":
                warnings.append(
                    f"Line {line_num}: Edge target '{tgt}' not found as defined node"
                )

        # Check 6: Unquoted special characters in labels
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            # Check for unquoted parentheses in node labels
            label_match = re.search(r'\w+\[([^\]"]+)\]', stripped)
            if label_match:
                label = label_match.group(1)
                if "(" in label or ")" in label:
                    warnings.append(
                        f"Line {i}: Unquoted parentheses in label may cause parse errors — "
                        f"use double quotes: [\"...\"]"
                    )

        # Check 7: Empty subgraphs
        in_subgraph = False
        subgraph_start = 0
        subgraph_content = 0
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("subgraph "):
                in_subgraph = True
                subgraph_start = i
                subgraph_content = 0
            elif stripped == "end" and in_subgraph:
                if subgraph_content == 0:
                    warnings.append(
                        f"Line {subgraph_start}: Empty subgraph — may cause rendering issues"
                    )
                in_subgraph = False
            elif in_subgraph and stripped and not stripped.startswith("direction"):
                subgraph_content += 1

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "stats": {
            "nodes": len(node_ids),
            "edges": len(edge_refs),
            "subgraphs": subgraph_count,
        },
    }


# ---------------------------------------------------------------------------
# PlantUML C4 Validation
# ---------------------------------------------------------------------------

def validate_plantuml(filepath: Path) -> dict:
    """Validate PlantUML C4 diagram syntax for common errors."""
    text = filepath.read_text(encoding="utf-8")
    lines = text.split("\n")
    errors = []
    warnings = []

    # Check 1: @startuml and @enduml
    stripped_lines = [l.strip() for l in lines if l.strip()]
    if not stripped_lines or not stripped_lines[0].startswith("@startuml"):
        errors.append("File must start with @startuml")
    if not stripped_lines or not stripped_lines[-1].startswith("@enduml"):
        errors.append("File must end with @enduml")

    # Check 2: !include with C4/ prefix
    includes = [l for l in lines if l.strip().startswith("!include")]
    c4_includes = [l for l in includes if "<C4/" in l or "C4_" in l]
    if not c4_includes:
        warnings.append("No C4 include found — expected !include <C4/C4_*>")

    for inc in includes:
        stripped = inc.strip()
        # Check for missing C4/ prefix in stdlib includes
        if re.match(r'!include\s+<C4_(Context|Container|Component|Deployment)>', stripped):
            errors.append(
                f"Missing 'C4/' prefix: '{stripped}' — must be '!include <C4/C4_...>'"
            )

    # Check 3: Alias naming — must be alphanumeric + underscore only
    macro_pattern = re.compile(
        r'(?:Person|System|Container|Component|ContainerDb|ContainerQueue|'
        r'ComponentDb|ComponentQueue|Deployment_Node|Node|'
        r'Person_Ext|System_Ext|Container_Ext|ContainerDb_Ext|ContainerQueue_Ext|'
        r'Component_Ext|ComponentDb_Ext|SystemDb|SystemQueue)\s*\(\s*(\w[^,)]*)'
    )
    aliases = set()
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("'") or stripped.startswith("@"):
            continue

        for match in macro_pattern.finditer(stripped):
            alias = match.group(1).strip()
            aliases.add(alias)
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', alias):
                errors.append(
                    f"Line {i}: Invalid alias '{alias}' — must be alphanumeric + underscore only "
                    f"(no hyphens). Convert kebab-case to snake_case."
                )

    # Check 4: Single quotes in macro arguments
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("'"):
            continue
        # Look for macro calls with single-quoted arguments
        if re.search(r"(Person|System|Container|Component|Node)\w*\([^)]*'[^']*'", stripped):
            errors.append(
                f"Line {i}: Single quotes found in macro arguments — use double quotes only"
            )

    # Check 5: Multi-line macro calls
    in_macro = False
    macro_start = 0
    paren_depth = 0
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("'") or stripped.startswith("@") or stripped.startswith("!"):
            continue

        # Check if a macro call starts on this line
        if re.match(r'(Person|System|Container|Component|Deployment_Node|Node|Rel|BiRel|Lay_)\w*\(', stripped):
            open_count = stripped.count("(")
            close_count = stripped.count(")")
            if open_count > close_count:
                errors.append(
                    f"Line {i}: Macro call split across multiple lines — "
                    f"all macro calls must be on ONE line"
                )

    # Check 6: Balanced braces for boundaries
    brace_stack = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("'"):
            continue
        for char in stripped:
            if char == "{":
                brace_stack.append(i)
            elif char == "}":
                if brace_stack:
                    brace_stack.pop()
                else:
                    errors.append(f"Line {i}: Unmatched closing brace '}}'")

    for line_num in brace_stack:
        errors.append(f"Line {line_num}: Unmatched opening brace '{{'")

    # Check 7: SHOW_LEGEND() must be last meaningful line before @enduml
    found_legend = False
    found_after_legend = False
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if "SHOW_LEGEND" in stripped or "LAYOUT_WITH_LEGEND" in stripped:
            found_legend = True
            continue
        if found_legend and stripped and not stripped.startswith("'") and stripped != "@enduml":
            found_after_legend = True
            warnings.append(
                f"Line {i}: Content found after SHOW_LEGEND() — "
                f"only comments allowed between SHOW_LEGEND() and @enduml"
            )

    if not found_legend:
        warnings.append("No SHOW_LEGEND() or LAYOUT_WITH_LEGEND() found")

    # Check 8: LAYOUT_LEFT_RIGHT() usage (discouraged)
    for i, line in enumerate(lines, 1):
        if "LAYOUT_LEFT_RIGHT()" in line:
            warnings.append(
                f"Line {i}: LAYOUT_LEFT_RIGHT() rotates Rel_* directions — "
                f"use LAYOUT_LANDSCAPE() instead for predictable behavior"
            )

    # Check 9: ELK pragma (unsupported in many environments)
    for i, line in enumerate(lines, 1):
        if "!pragma layout elk" in line.lower():
            warnings.append(
                f"Line {i}: '!pragma layout elk' — ELK not available in all environments, "
                f"may cause errors"
            )

    # Check 10: Rel between boundaries (not leaf elements)
    boundary_aliases = set()
    boundary_pattern = re.compile(
        r'(?:Enterprise_Boundary|System_Boundary|Container_Boundary|Boundary)\s*\(\s*(\w+)'
    )
    for line in lines:
        match = boundary_pattern.search(line.strip())
        if match:
            boundary_aliases.add(match.group(1))

    rel_pattern = re.compile(r'(?:Rel|BiRel)\w*\(\s*(\w+)\s*,\s*(\w+)')
    for i, line in enumerate(lines, 1):
        match = rel_pattern.search(line.strip())
        if match:
            src, tgt = match.group(1), match.group(2)
            if src in boundary_aliases or tgt in boundary_aliases:
                errors.append(
                    f"Line {i}: Rel() connects boundary '{src if src in boundary_aliases else tgt}' — "
                    f"connect leaf elements, not boundaries"
                )

    # Check 11: Unescaped Creole characters in labels
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("'") or stripped.startswith("@") or stripped.startswith("!"):
            continue
        # Look for // in quoted strings (triggers italic)
        string_matches = re.findall(r'"([^"]*)"', stripped)
        for s in string_matches:
            if "//" in s and "~/" not in s:
                warnings.append(
                    f"Line {i}: Unescaped '//' in label may trigger italic formatting — "
                    f"escape with '~/~/'"
                )
            if "**" in s and "~*" not in s:
                warnings.append(
                    f"Line {i}: Unescaped '**' in label may trigger bold formatting — "
                    f"escape with '~*~*'"
                )

    # Check 12: skinparam nodesep/ranksep (unreliable)
    for i, line in enumerate(lines, 1):
        if re.match(r'\s*skinparam\s+(nodesep|ranksep)', line):
            warnings.append(
                f"Line {i}: skinparam nodesep/ranksep not reliably supported — "
                f"use wrapWidth and linetype instead"
            )

    # Check 13: Include level matches macros used
    has_component_macro = any(
        re.search(r'\bComponent(Db|Queue|_Ext|Db_Ext|Queue_Ext)?\s*\(', l)
        for l in lines
    )
    has_component_include = any("C4_Component" in l for l in includes)
    if has_component_macro and not has_component_include:
        errors.append(
            "Component() macros used but C4_Component not included — "
            "add !include <C4/C4_Component>"
        )

    has_deployment_macro = any(
        re.search(r'\b(Deployment_Node|Node)\s*\(', l)
        for l in lines if not l.strip().startswith("'")
    )
    has_deployment_include = any("C4_Deployment" in l for l in includes)
    if has_deployment_macro and not has_deployment_include:
        errors.append(
            "Deployment_Node()/Node() macros used but C4_Deployment not included — "
            "add !include <C4/C4_Deployment>"
        )

    # Check 14: Rel source/target reference defined aliases
    for i, line in enumerate(lines, 1):
        match = rel_pattern.search(line.strip())
        if match:
            src, tgt = match.group(1), match.group(2)
            if aliases and src not in aliases and src not in boundary_aliases:
                warnings.append(
                    f"Line {i}: Rel source '{src}' not found as defined element"
                )
            if aliases and tgt not in aliases and tgt not in boundary_aliases:
                warnings.append(
                    f"Line {i}: Rel target '{tgt}' not found as defined element"
                )

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "stats": {
            "aliases": len(aliases),
            "boundaries": len(boundary_aliases),
            "includes": len(c4_includes),
        },
    }


# ---------------------------------------------------------------------------
# Draw.io XML Validation
# ---------------------------------------------------------------------------

def validate_drawio(filepath: Path) -> dict:
    """Validate Draw.io XML for structural correctness."""
    text = filepath.read_text(encoding="utf-8")
    errors = []
    warnings = []

    # Check 1: XML well-formedness
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        errors.append(f"XML parse error: {e}")
        return {"valid": False, "errors": errors, "warnings": warnings}

    # Check 2: Root element must be <mxfile>
    if root.tag != "mxfile":
        errors.append(f"Root element must be 'mxfile', got '{root.tag}'")
        return {"valid": False, "errors": errors, "warnings": warnings}

    # Check 3: Must have at least one <diagram> child
    diagrams = root.findall("diagram")
    if not diagrams:
        errors.append("No <diagram> element found inside <mxfile>")
        return {"valid": False, "errors": errors, "warnings": warnings}

    all_vertex_ids = set()
    all_ids = set()

    for diagram in diagrams:
        # Check 4: mxGraphModel structure
        graph_model = diagram.find("mxGraphModel")
        if graph_model is None:
            errors.append(
                f"Diagram '{diagram.get('name', 'unnamed')}': missing <mxGraphModel>"
            )
            continue

        graph_root = graph_model.find("root")
        if graph_root is None:
            errors.append(
                f"Diagram '{diagram.get('name', 'unnamed')}': missing <root> inside mxGraphModel"
            )
            continue

        cells = graph_root.findall("mxCell")

        # Check 5: Must have cells with id="0" and id="1"
        cell_ids = {c.get("id") for c in cells}
        if "0" not in cell_ids:
            errors.append("Missing required mxCell with id='0' (root cell)")
        if "1" not in cell_ids:
            errors.append("Missing required mxCell with id='1' (default layer)")

        # Check 6: Unique IDs
        for cell in cells:
            cell_id = cell.get("id")
            if cell_id in all_ids:
                errors.append(f"Duplicate cell id='{cell_id}'")
            all_ids.add(cell_id)

        # Collect vertex and edge info
        vertices = {}
        edges = []
        for cell in cells:
            cell_id = cell.get("id")
            if cell.get("vertex") == "1":
                vertices[cell_id] = cell
                all_vertex_ids.add(cell_id)
            if cell.get("edge") == "1":
                edges.append(cell)

        # Check 7: Edge source/target reference existing vertices
        for edge in edges:
            edge_id = edge.get("id", "?")
            source = edge.get("source")
            target = edge.get("target")

            if source and source not in all_vertex_ids and source not in cell_ids:
                errors.append(
                    f"Edge id='{edge_id}': source='{source}' not found as vertex"
                )
            if target and target not in all_vertex_ids and target not in cell_ids:
                errors.append(
                    f"Edge id='{edge_id}': target='{target}' not found as vertex"
                )

        # Check 8: All vertices must have geometry
        for cell_id, cell in vertices.items():
            if cell_id in ("0", "1"):
                continue
            geo = cell.find("mxGeometry")
            if geo is None:
                warnings.append(
                    f"Vertex id='{cell_id}': missing <mxGeometry> — "
                    f"may cause rendering issues"
                )

        # Check 9: Container children have valid parent references
        for cell in cells:
            parent = cell.get("parent")
            if parent and parent not in cell_ids:
                errors.append(
                    f"Cell id='{cell.get('id')}': parent='{parent}' not found"
                )

        # Check 10: Geometry overlap detection for vertices
        vertex_rects = []
        for cell_id, cell in vertices.items():
            if cell_id in ("0", "1"):
                continue
            geo = cell.find("mxGeometry")
            if geo is not None and geo.get("relative") != "1":
                try:
                    x = float(geo.get("x", 0))
                    y = float(geo.get("y", 0))
                    w = float(geo.get("width", 0))
                    h = float(geo.get("height", 0))
                    parent = cell.get("parent", "1")
                    if w > 0 and h > 0:
                        vertex_rects.append((cell_id, x, y, w, h, parent))
                except (ValueError, TypeError):
                    pass

        # Only check overlap for cells with the same parent
        for i, (id1, x1, y1, w1, h1, p1) in enumerate(vertex_rects):
            for j, (id2, x2, y2, w2, h2, p2) in enumerate(vertex_rects):
                if j <= i or p1 != p2:
                    continue
                # Check if rectangles overlap
                if (x1 < x2 + w2 and x1 + w1 > x2 and
                        y1 < y2 + h2 and y1 + h1 > y2):
                    # Check if one is a container for the other
                    is_container = (
                        any(c.get("parent") == id1 for c in cells) or
                        any(c.get("parent") == id2 for c in cells)
                    )
                    if not is_container:
                        warnings.append(
                            f"Vertices '{id1}' and '{id2}' overlap at "
                            f"({x1},{y1}) and ({x2},{y2})"
                        )

        # Check 11: Style string syntax
        for cell in cells:
            style = cell.get("style", "")
            if style and "=" in style:
                # Style should be semicolon-delimited key=value pairs
                parts = style.rstrip(";").split(";")
                for part in parts:
                    if part and "=" not in part and part not in (
                        "html", "rounded", "dashed", "vertical", "horizontal",
                        "text", "swimlane", "group", "line", "image",
                    ):
                        # Some style values are flags without =
                        pass  # Allow flag-style values

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "stats": {
            "diagrams": len(diagrams),
            "vertices": len(all_vertex_ids),
            "edges": len(edges) if diagrams else 0,
        },
    }


# ---------------------------------------------------------------------------
# Batch validation
# ---------------------------------------------------------------------------

def validate_directory(dirpath: Path) -> dict:
    """Validate all diagram files in a directory."""
    results = {}

    for ext, validator, fmt in [
        (".md", validate_mermaid, "mermaid"),
        (".puml", validate_plantuml, "plantuml"),
        (".drawio", validate_drawio, "drawio"),
    ]:
        for filepath in sorted(dirpath.rglob(f"*{ext}")):
            # Skip non-diagram .md files
            if ext == ".md":
                content = filepath.read_text(encoding="utf-8")
                if "```mermaid" not in content and not content.strip().startswith("flowchart"):
                    continue

            result = validator(filepath)
            result["format"] = fmt
            results[str(filepath)] = result

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Validate diagram file syntax for Mermaid, PlantUML, and Draw.io.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_mermaid = subparsers.add_parser("mermaid", help="Validate Mermaid flowchart")
    p_mermaid.add_argument("file", type=Path)

    p_plantuml = subparsers.add_parser("plantuml", help="Validate PlantUML C4")
    p_plantuml.add_argument("file", type=Path)

    p_drawio = subparsers.add_parser("drawio", help="Validate Draw.io XML")
    p_drawio.add_argument("file", type=Path)

    p_all = subparsers.add_parser("all", help="Validate all diagrams in a directory")
    p_all.add_argument("directory", type=Path)

    parser.add_argument("--format", choices=["text", "json"], default="text")

    args = parser.parse_args()

    if args.command == "all":
        results = validate_directory(args.directory)
        if args.format == "json":
            print(json.dumps(results, indent=2))
        else:
            total_errors = 0
            total_warnings = 0
            for filepath, result in results.items():
                e = len(result["errors"])
                w = len(result["warnings"])
                total_errors += e
                total_warnings += w
                icon = "✓" if result["valid"] else "✗"
                print(f"  {icon} {filepath} ({result['format']}) — {e} errors, {w} warnings")
                for err in result["errors"]:
                    print(f"    ✗ {err}")
                for warn in result["warnings"]:
                    print(f"    ⚠ {warn}")

            status = "PASS" if total_errors == 0 else "FAIL"
            print(f"\n{status}: {len(results)} files, {total_errors} errors, {total_warnings} warnings")

        sys.exit(0 if all(r["valid"] for r in results.values()) else 1)

    else:
        validators = {
            "mermaid": validate_mermaid,
            "plantuml": validate_plantuml,
            "drawio": validate_drawio,
        }
        result = validators[args.command](args.file)

        if args.format == "json":
            print(json.dumps(result, indent=2))
        else:
            icon = "✓" if result["valid"] else "✗"
            print(f"{icon} {args.file}")
            for err in result["errors"]:
                print(f"  ✗ {err}")
            for warn in result["warnings"]:
                print(f"  ⚠ {warn}")
            if result.get("stats"):
                stats_str = ", ".join(f"{k}={v}" for k, v in result["stats"].items())
                print(f"  Stats: {stats_str}")

        sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
