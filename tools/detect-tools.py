#!/usr/bin/env python3
# Copyright (c) 2026 Michael J. Read. All rights reserved.
# SPDX-License-Identifier: BUSL-1.1
"""Cross-platform tool detection for Doc2ArchAgent.

Replaces the bash-only detect-tools.sh with a Python implementation
that works on Linux, macOS, Windows (PowerShell/cmd), and other shells.

Usage:
    python tools/detect-tools.py

Output:
    JSON object with tool name, version, path, and available status.
    Same format as detect-tools.sh for drop-in compatibility.
"""

import importlib
import json
import shutil
import subprocess
import sys


def check_tool(name: str, cmd: str, version_flag: str = "--version") -> dict:
    """Check if a system tool is available."""
    path = shutil.which(cmd)
    if path:
        available = True
        try:
            result = subprocess.run(
                [cmd, version_flag],
                capture_output=True, text=True, timeout=10,
            )
            output = result.stdout.strip() or result.stderr.strip()
            version = output.splitlines()[0] if output else "unknown"
        except Exception:
            version = "unknown"
    else:
        available = False
        path = ""
        version = ""

    return {
        "name": name,
        "command": cmd,
        "available": available,
        "path": path or "",
        "version": version,
    }


def check_python_pkg(pkg: str, import_name: str | None = None) -> dict:
    """Check if a Python package is importable."""
    import_name = import_name or pkg
    try:
        mod = importlib.import_module(import_name)
        available = True
        version = getattr(mod, "__version__", "unknown")
    except ImportError:
        available = False
        version = ""

    return {
        "name": f"python-{pkg}",
        "command": f'python3 -c "import {import_name}"',
        "available": available,
        "path": "",
        "version": version,
    }


def main() -> None:
    tools = []

    # System tools
    tools.append(check_tool("python3", "python3", "--version"))
    tools.append(check_tool("pandoc", "pandoc", "--version"))
    tools.append(check_tool("pdftotext", "pdftotext", "-v"))
    tools.append(check_tool("tesseract", "tesseract", "--version"))
    tools.append(check_tool("git", "git", "--version"))
    tools.append(check_tool("d2", "d2", "--version"))

    # Python packages
    tools.append(check_python_pkg("PyMuPDF", "fitz"))
    tools.append(check_python_pkg("pdfplumber", "pdfplumber"))
    tools.append(check_python_pkg("python-docx", "docx"))
    tools.append(check_python_pkg("rapidfuzz", "rapidfuzz"))
    tools.append(check_python_pkg("beautifulsoup4", "bs4"))
    tools.append(check_python_pkg("html2text", "html2text"))
    tools.append(check_python_pkg("pydantic", "pydantic"))
    tools.append(check_python_pkg("vsdx", "vsdx"))
    tools.append(check_python_pkg("pytesseract", "pytesseract"))
    tools.append(check_python_pkg("Pillow", "PIL"))

    print(json.dumps({"tools": tools}))


if __name__ == "__main__":
    main()
