#!/usr/bin/env python3
# Copyright (c) 2026 Michael J. Read. All rights reserved.
# SPDX-License-Identifier: BUSL-1.1
"""Sync MITRE ATT&CK Enterprise Matrix data into Doc2ArchAgent context files.

Downloads the latest ATT&CK Enterprise STIX 2.1 bundle from GitHub,
parses techniques and tactics, and generates context/attack-techniques.yaml.

Auto-suggests STRIDE categories for each technique based on tactic membership.
New/unreviewed techniques are flagged with stride_review_status: needs_review.

Usage:
    python tools/sync-attack-data.py [--output <path>] [--version <version>]

Dependencies:
    pip install pyyaml requests

Optional (for diff detection):
    pip install mitreattack-python stix2
"""

import json
import sys
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Error: pyyaml required. pip install pyyaml", file=sys.stderr)
    sys.exit(1)

try:
    import requests
except ImportError:
    # Fallback to urllib for environments without requests
    import urllib.request
    requests = None

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
DEFAULT_OUTPUT = PROJECT_ROOT / "context" / "attack-techniques.yaml"
STRIDE_MAPPING_FILE = PROJECT_ROOT / "context" / "stride-to-attack.yaml"

# STIX 2.1 Enterprise ATT&CK bundle URL (always latest)
ATTACK_URL = "https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/enterprise-attack/enterprise-attack.json"
INDEX_URL = "https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/index.json"

# Tactic-to-STRIDE default mapping (community consensus, not official)
TACTIC_TO_STRIDE = {
    "reconnaissance": "information_disclosure",
    "resource-development": "tampering",
    "initial-access": "spoofing",
    "execution": "tampering",
    "persistence": "tampering",
    "privilege-escalation": "elevation_of_privilege",
    "defense-evasion": "repudiation",
    "credential-access": "spoofing",
    "discovery": "information_disclosure",
    "lateral-movement": "elevation_of_privilege",
    "collection": "information_disclosure",
    "command-and-control": "tampering",
    "exfiltration": "information_disclosure",
    "impact": "denial_of_service",
}


def fetch_url(url: str) -> bytes:
    """Fetch URL content using requests or urllib fallback."""
    if requests:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        return resp.content
    else:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read()


def fetch_attack_bundle(version: str | None = None) -> dict:
    """Download and parse the ATT&CK STIX 2.1 bundle."""
    if version:
        url = f"https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/enterprise-attack/enterprise-attack-{version}.json"
    else:
        url = ATTACK_URL

    print(f"Fetching ATT&CK data from: {url}", file=sys.stderr)
    data = fetch_url(url)
    return json.loads(data)


def get_latest_version() -> str | None:
    """Get the latest ATT&CK version from the index."""
    try:
        data = json.loads(fetch_url(INDEX_URL))
        for domain in data.get("domains", []):
            if domain.get("name") == "Enterprise ATT&CK":
                versions = domain.get("versions", [])
                if versions:
                    return versions[-1].get("version", "")
    except Exception:
        pass
    return None


def parse_stix_bundle(bundle: dict) -> dict:
    """Parse STIX 2.1 bundle into structured technique data."""
    objects = bundle.get("objects", [])

    # Index tactics
    tactics = {}
    for obj in objects:
        if obj.get("type") == "x-mitre-tactic":
            shortname = obj.get("x_mitre_shortname", "")
            tactics[shortname] = {
                "id": _get_external_id(obj),
                "name": obj.get("name", ""),
                "shortname": shortname,
            }

    # Parse techniques (not deprecated, not revoked)
    techniques = []
    sub_technique_map = {}  # parent_id -> list of sub-techniques

    for obj in objects:
        if obj.get("type") != "attack-pattern":
            continue
        if obj.get("x_mitre_deprecated", False) or obj.get("revoked", False):
            continue
        if "enterprise-attack" not in obj.get("x_mitre_domains", []):
            continue

        ext_id = _get_external_id(obj)
        if not ext_id:
            continue

        is_sub = obj.get("x_mitre_is_subtechnique", False)
        technique_tactics = []
        for kcp in obj.get("kill_chain_phases", []):
            if kcp.get("kill_chain_name") == "mitre-attack":
                technique_tactics.append(kcp.get("phase_name", ""))

        entry = {
            "id": ext_id,
            "name": obj.get("name", ""),
            "tactics": sorted(technique_tactics),
            "platforms": sorted(obj.get("x_mitre_platforms", [])),
            "url": f"https://attack.mitre.org/techniques/{ext_id.replace('.', '/')}",
            "description_short": _truncate(obj.get("description", ""), 200),
        }

        if is_sub:
            parent_id = ext_id.rsplit(".", 1)[0] if "." in ext_id else ext_id
            sub_technique_map.setdefault(parent_id, []).append(entry)
        else:
            techniques.append(entry)

    # Sort techniques by ID
    techniques.sort(key=lambda t: t["id"])
    for subs in sub_technique_map.values():
        subs.sort(key=lambda t: t["id"])

    return {
        "tactics": tactics,
        "techniques": techniques,
        "sub_technique_map": sub_technique_map,
    }


def assign_stride_categories(techniques: list[dict], existing_mappings: dict) -> list[dict]:
    """Assign STRIDE categories to techniques.

    Uses existing confirmed mappings from stride-to-attack.yaml.
    For new techniques, auto-suggests based on tactic membership.
    """
    # Build lookup from existing stride-to-attack.yaml
    confirmed = {}
    for category in existing_mappings.get("stride_categories", []):
        stride_name = category.get("id", "")
        for tech in category.get("attack_techniques", []):
            tid = tech.get("id", "")
            if tid:
                confirmed.setdefault(tid, set()).add(stride_name)

    result = []
    for tech in techniques:
        tid = tech["id"]

        if tid in confirmed:
            tech["stride_categories"] = sorted(confirmed[tid])
            tech["stride_review_status"] = "confirmed"
        else:
            # Auto-suggest from tactics
            suggested = set()
            for tactic in tech.get("tactics", []):
                stride = TACTIC_TO_STRIDE.get(tactic)
                if stride:
                    suggested.add(stride)
            tech["stride_categories"] = sorted(suggested) if suggested else ["unknown"]
            tech["stride_review_status"] = "needs_review"

        result.append(tech)

    return result


def generate_output(parsed: dict, techniques_with_stride: list[dict],
                    version: str, sub_map: dict) -> dict:
    """Generate the output YAML structure."""
    # Count stats
    total_techniques = len(techniques_with_stride)
    total_subs = sum(len(v) for v in sub_map.values())
    needs_review = sum(1 for t in techniques_with_stride if t.get("stride_review_status") == "needs_review")

    output = {
        "metadata": {
            "attack_version": version,
            "last_synced": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": "https://github.com/mitre-attack/attack-stix-data",
            "total_techniques": total_techniques,
            "total_sub_techniques": total_subs,
            "total_tactics": len(parsed["tactics"]),
            "needs_review_count": needs_review,
            "stride_mapping_note": "STRIDE categories are auto-suggested from tactic membership. "
                                   "No official MITRE STRIDE-to-ATT&CK mapping exists. "
                                   "Techniques marked needs_review require manual verification.",
        },
        "tactics": [
            {"id": t["id"], "name": t["name"], "shortname": t["shortname"]}
            for t in sorted(parsed["tactics"].values(), key=lambda t: t["id"])
        ],
        "techniques": [],
    }

    for tech in techniques_with_stride:
        entry = {
            "id": tech["id"],
            "name": tech["name"],
            "tactics": tech["tactics"],
            "stride_categories": tech["stride_categories"],
            "stride_review_status": tech["stride_review_status"],
            "platforms": tech["platforms"],
            "url": tech["url"],
        }

        # Add sub-techniques if any
        subs = sub_map.get(tech["id"], [])
        if subs:
            entry["sub_techniques"] = [
                {
                    "id": s["id"],
                    "name": s["name"],
                    "tactics": s["tactics"],
                    "url": s["url"],
                }
                for s in subs
            ]

        output["techniques"].append(entry)

    return output


def _get_external_id(obj: dict) -> str:
    """Extract the ATT&CK external ID (e.g., T1078) from a STIX object."""
    for ref in obj.get("external_references", []):
        if ref.get("source_name") == "mitre-attack":
            return ref.get("external_id", "")
    return ""


def _truncate(text: str, max_len: int) -> str:
    """Truncate text to max_len, adding ellipsis if needed."""
    text = text.replace("\n", " ").strip()
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Sync MITRE ATT&CK data for Doc2ArchAgent.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output YAML path")
    parser.add_argument("--version", help="Specific ATT&CK version (e.g., 18.1). Omit for latest.")
    args = parser.parse_args()

    # Determine version
    version = args.version or get_latest_version() or "unknown"
    print(f"ATT&CK version: {version}", file=sys.stderr)

    # Fetch and parse
    bundle = fetch_attack_bundle(args.version)
    parsed = parse_stix_bundle(bundle)

    print(f"Parsed: {len(parsed['techniques'])} techniques, "
          f"{sum(len(v) for v in parsed['sub_technique_map'].values())} sub-techniques, "
          f"{len(parsed['tactics'])} tactics", file=sys.stderr)

    # Load existing STRIDE mappings for confirmed assignments
    existing_stride = {}
    if STRIDE_MAPPING_FILE.exists():
        with open(STRIDE_MAPPING_FILE) as f:
            existing_stride = yaml.safe_load(f) or {}

    # Assign STRIDE categories
    techniques_with_stride = assign_stride_categories(parsed["techniques"], existing_stride)

    needs_review = sum(1 for t in techniques_with_stride if t.get("stride_review_status") == "needs_review")
    print(f"STRIDE mapping: {len(techniques_with_stride) - needs_review} confirmed, "
          f"{needs_review} needs_review", file=sys.stderr)

    # Generate output
    output = generate_output(parsed, techniques_with_stride, version, parsed["sub_technique_map"])

    # Write
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write("# Auto-generated by tools/sync-attack-data.py\n")
        f.write("# Do not edit manually — run the sync script to update.\n")
        f.write(f"# Source: MITRE ATT&CK Enterprise v{version}\n\n")
        yaml.dump(output, f, default_flow_style=False, sort_keys=False, width=120, allow_unicode=True)

    print(f"Written: {output_path}", file=sys.stderr)
    print(json.dumps({
        "success": True,
        "version": version,
        "techniques": len(techniques_with_stride),
        "needs_review": needs_review,
        "output": str(output_path),
    }))


if __name__ == "__main__":
    main()
