<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->

# YAML Formatting Standards

## Indentation
- 2-space indentation, no tabs
- Consistent nesting depth across all files

## Quoting
- Quote strings that could be misinterpreted: `"true"`, `"false"`, `"null"`, `"yes"`, `"no"`, `"on"`, `"off"`
- Quote version-like strings: `"3.0"`, `"1.2.3"`
- Use double quotes for strings containing special characters

## Multi-line Strings
- Use block scalar `|` for multi-line descriptions
- Use `>` for folded (wrapped) strings only when line breaks don't matter

## File Structure
- Every YAML file starts with the top-level key (no document separator `---` needed unless multi-document)
- Trailing newline at end of file
- No trailing whitespace on any line

## Key Ordering
- Follow the order defined in the corresponding JSON Schema
- Metadata fields first, then structural fields, then relationship fields

## Comments
- Use comments sparingly — YAML should be self-documenting via descriptive field names
- `# GENERATED — do not edit manually` at the top of composed/generated files
