#!/usr/bin/env bash
# Detect available document conversion tools and report as JSON.
#
# Usage:
#     bash tools/detect-tools.sh
#
# Output:
#     JSON object with tool name, version, path, and available status.

set -euo pipefail

json_tools=()

check_tool() {
    local name="$1"
    local cmd="$2"
    local version_flag="${3:---version}"

    local path version available

    if path=$(command -v "$cmd" 2>/dev/null); then
        available=true
        version=$(eval "$cmd $version_flag 2>&1" | head -1) || version="unknown"
    else
        available=false
        path=""
        version=""
    fi

    json_tools+=("$(printf '{"name":"%s","command":"%s","available":%s,"path":"%s","version":"%s"}' \
        "$name" "$cmd" "$available" "$path" "$version")")
}

check_python_pkg() {
    local pkg="$1"
    local import_name="${2:-$1}"

    local available version

    if python3 -c "import ${import_name}" 2>/dev/null; then
        available=true
        version=$(python3 -c "import ${import_name}; print(getattr(${import_name}, '__version__', 'unknown'))" 2>/dev/null) || version="unknown"
    else
        available=false
        version=""
    fi

    json_tools+=("$(printf '{"name":"python-%s","command":"python3 -c \"import %s\"","available":%s,"path":"","version":"%s"}' \
        "$pkg" "$import_name" "$available" "$version")")
}

# System tools
check_tool "python3" "python3" "--version"
check_tool "pandoc" "pandoc" "--version"
check_tool "pdftotext" "pdftotext" "-v"
check_tool "tesseract" "tesseract" "--version"

# Python packages (only if python3 available)
if command -v python3 &>/dev/null; then
    check_python_pkg "PyMuPDF" "fitz"
    check_python_pkg "pdfplumber" "pdfplumber"
    check_python_pkg "python-docx" "docx"
    check_python_pkg "rapidfuzz" "rapidfuzz"
    check_python_pkg "beautifulsoup4" "bs4"
    check_python_pkg "html2text" "html2text"
    check_python_pkg "pydantic" "pydantic"
    check_python_pkg "vsdx" "vsdx"
fi

# Build JSON array
printf '{"tools":['
first=true
for t in "${json_tools[@]}"; do
    if [ "$first" = true ]; then
        first=false
    else
        printf ','
    fi
    printf '%s' "$t"
done
printf ']}\n'
