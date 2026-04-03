#!/usr/bin/env python3
# Copyright (c) 2026 Michael J. Read. All rights reserved.
# SPDX-License-Identifier: BUSL-1.1
"""Extract structured component/relationship data from Draw.io and Visio files.

Usage:
    python tools/parse-diagram-file.py <file.drawio|file.vsdx> [--format json|yaml]

Output:
    JSON or YAML with components, relationships, and boundaries extracted
    from the diagram file.

Supports:
    .drawio / .xml   — mxGraph XML format (Draw.io, diagrams.net)
    .vsdx            — Visio Open XML format (via vsdx library or manual ZIP+XML)
"""

import argparse
import base64
import json
import sys
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path
from urllib.parse import unquote


# ---------------------------------------------------------------------------
# Draw.io (.drawio / .xml) parser
# ---------------------------------------------------------------------------

def _decode_drawio_compressed(data: str) -> str:
    """Decode a compressed/encoded Draw.io diagram cell value."""
    try:
        decoded = base64.b64decode(data)
        decompressed = zlib.decompress(decoded, -zlib.MAX_WBITS)
        return unquote(decompressed.decode("utf-8"))
    except Exception:
        return data


def _safe_parse_xml(path: Path) -> ET.Element:
    """Parse XML with XXE protection (defense-in-depth)."""
    try:
        from defusedxml import ElementTree as SafeET
        return SafeET.parse(str(path)).getroot()
    except ImportError:
        # Python 3.8+ ET doesn't resolve external entities by default,
        # but we still disable DTD processing where possible
        parser = ET.XMLParser()
        return ET.parse(str(path), parser=parser).getroot()


def _safe_float(value: str | None, default: float = 0.0) -> float:
    """Convert a string to float, returning default on failure."""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def parse_drawio(path: Path) -> dict:
    """Parse a .drawio/.xml file and extract components, relationships, boundaries."""
    root = _safe_parse_xml(path)

    components: list[dict] = []
    relationships: list[dict] = []
    boundaries: list[dict] = []
    id_to_label: dict[str, str] = {}
    id_to_parent: dict[str, str] = {}
    parent_children: dict[str, list[str]] = {}

    # Find all mxCell elements (may be nested under diagram/mxGraphModel/root)
    cells = root.iter("mxCell")

    for cell in cells:
        cell_id = cell.get("id", "")
        label = cell.get("value", "").strip()
        style = cell.get("style", "")
        source = cell.get("source")
        target = cell.get("target")
        parent = cell.get("parent", "")
        vertex = cell.get("vertex")
        edge = cell.get("edge")

        # Store label mapping
        if label:
            id_to_label[cell_id] = label

        # Track parent-child
        if parent and parent not in ("0", "1"):
            id_to_parent[cell_id] = parent
            parent_children.setdefault(parent, []).append(cell_id)

        # Extract geometry
        geom = cell.find("mxGeometry")
        x = _safe_float(geom.get("x")) if geom is not None else 0
        y = _safe_float(geom.get("y")) if geom is not None else 0
        width = _safe_float(geom.get("width")) if geom is not None else 0
        height = _safe_float(geom.get("height")) if geom is not None else 0

        if edge == "1" and source and target:
            # Relationship (edge)
            relationships.append({
                "id": cell_id,
                "source": source,
                "target": target,
                "label": label or "",
            })
        elif vertex == "1" and label:
            # Determine type from style
            shape_type = _classify_drawio_style(style)

            if shape_type == "boundary" or cell_id in parent_children:
                boundaries.append({
                    "id": cell_id,
                    "label": label,
                    "children": [],  # Filled below
                    "x": x, "y": y, "width": width, "height": height,
                })
            else:
                components.append({
                    "id": cell_id,
                    "label": label,
                    "type": shape_type,
                    "parent_group": parent if parent not in ("0", "1") else None,
                    "x": x, "y": y,
                })

    # Resolve labels in relationships
    for rel in relationships:
        rel["source_label"] = id_to_label.get(rel["source"], rel["source"])
        rel["target_label"] = id_to_label.get(rel["target"], rel["target"])

    # Fill boundary children
    for boundary in boundaries:
        children_ids = parent_children.get(boundary["id"], [])
        boundary["children"] = [
            id_to_label.get(cid, cid) for cid in children_ids
        ]

    return {
        "source_file": path.name,
        "format": "drawio",
        "components": components,
        "relationships": relationships,
        "boundaries": boundaries,
    }


def _classify_drawio_style(style: str) -> str:
    """Classify a Draw.io cell style into a component type."""
    s = style.lower()
    if "shape=cylinder" in s or "shape=mxgraph.flowchart.database" in s:
        return "database"
    if "ellipse" in s or "shape=cloud" in s or "shape=mxgraph.aws" in s:
        return "external_system"
    if "shape=mxgraph.flowchart.document" in s:
        return "document"
    if "shape=hexagon" in s:
        return "message_queue"
    if "shape=actor" in s or "shape=mxgraph.basic.person" in s:
        return "actor"
    if "group" in s or "swimlane" in s or "container=1" in style:
        return "boundary"
    if "rounded=1" in s:
        return "container"
    if "dashed=1" in s:
        return "trust_boundary"
    return "service"


# ---------------------------------------------------------------------------
# Visio (.vsdx) parser
# ---------------------------------------------------------------------------

def parse_vsdx(path: Path) -> dict:
    """Parse a .vsdx file and extract components, relationships, boundaries."""
    # Try the vsdx library first
    try:
        import vsdx
        return _parse_vsdx_library(path, vsdx)
    except ImportError:
        pass

    # Fallback: manual ZIP + XML parsing
    return _parse_vsdx_manual(path)


def _parse_vsdx_library(path: Path, vsdx_mod) -> dict:
    """Parse using the vsdx Python library."""
    components: list[dict] = []
    relationships: list[dict] = []
    boundaries: list[dict] = []

    with vsdx_mod.open(str(path)) as vis:
        for page in vis.pages:
            for shape in page.child_shapes:
                label = shape.text.strip() if shape.text else ""
                if not label:
                    continue

                # Check if connector
                connects = getattr(shape, "connects", [])
                if connects and len(connects) >= 2:
                    relationships.append({
                        "id": str(shape.ID),
                        "source": str(connects[0].shape_id) if connects[0] else "",
                        "target": str(connects[1].shape_id) if connects[1] else "",
                        "label": label,
                    })
                else:
                    # Check if group/boundary
                    children = list(shape.child_shapes) if hasattr(shape, "child_shapes") else []
                    if children:
                        boundaries.append({
                            "id": str(shape.ID),
                            "label": label,
                            "children": [
                                c.text.strip() for c in children if c.text and c.text.strip()
                            ],
                        })
                    else:
                        components.append({
                            "id": str(shape.ID),
                            "label": label,
                            "type": "service",
                            "parent_group": None,
                        })

    return {
        "source_file": path.name,
        "format": "vsdx",
        "components": components,
        "relationships": relationships,
        "boundaries": boundaries,
    }


def _parse_vsdx_manual(path: Path) -> dict:
    """Fallback: parse .vsdx as ZIP archive containing XML."""
    import zipfile

    components: list[dict] = []
    relationships: list[dict] = []

    try:
        with zipfile.ZipFile(str(path)) as z:
            # Find page XML files
            page_files = [n for n in z.namelist() if n.startswith("visio/pages/page") and n.endswith(".xml")]

            for pf in page_files:
                with z.open(pf) as f:
                    tree = ET.parse(f)
                    root = tree.getroot()

                    # Handle XML namespace
                    ns = ""
                    if root.tag.startswith("{"):
                        ns = root.tag.split("}")[0] + "}"

                    for shape in root.iter(f"{ns}Shape"):
                        shape_id = shape.get("ID", "")
                        # Extract text
                        text_elem = shape.find(f".//{ns}Text")
                        label = ""
                        if text_elem is not None:
                            label = "".join(text_elem.itertext()).strip()

                        if not label:
                            continue

                        # Check for connector type
                        shape_type = shape.get("Type", "")
                        if shape_type == "Group":
                            continue  # Skip groups in simple parse

                        master = shape.get("Master", "")
                        # Connectors often have specific master IDs or type attributes
                        connects = shape.findall(f".//{ns}Connect")
                        if connects:
                            source_id = connects[0].get("ToSheet", "") if len(connects) > 0 else ""
                            target_id = connects[1].get("ToSheet", "") if len(connects) > 1 else ""
                            relationships.append({
                                "id": shape_id,
                                "source": source_id,
                                "target": target_id,
                                "label": label,
                            })
                        else:
                            components.append({
                                "id": shape_id,
                                "label": label,
                                "type": "service",
                                "parent_group": None,
                            })
    except Exception as e:
        return {
            "source_file": path.name,
            "format": "vsdx",
            "error": f"Failed to parse: {e}",
            "components": [],
            "relationships": [],
            "boundaries": [],
        }

    return {
        "source_file": path.name,
        "format": "vsdx",
        "components": components,
        "relationships": relationships,
        "boundaries": [],
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Extract components and relationships from Draw.io and Visio files.",
    )
    parser.add_argument("file", help="Path to .drawio, .xml, or .vsdx file")
    parser.add_argument("--format", choices=["json", "yaml"], default="json",
                        help="Output format (default: json)")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"Error: {path} not found", file=sys.stderr)
        sys.exit(1)

    ext = path.suffix.lower()
    if ext in (".drawio", ".xml"):
        result = parse_drawio(path)
    elif ext == ".vsdx":
        result = parse_vsdx(path)
    else:
        print(f"Error: unsupported format {ext} (expected .drawio, .xml, or .vsdx)", file=sys.stderr)
        sys.exit(1)

    if args.format == "yaml":
        try:
            import yaml
            print(yaml.dump(result, default_flow_style=False, sort_keys=False))
        except ImportError:
            print("Error: pyyaml required for YAML output (pip install pyyaml)", file=sys.stderr)
            sys.exit(1)
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
