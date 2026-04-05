<!-- Copyright (c) 2026 Michael J. Read. All rights reserved. -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->

# Confluence Storage Format

Generate documentation in Confluence storage format (XHTML with Atlassian macros).

## Format Structure

```html
<ac:structured-macro ac:name="toc">
  <ac:parameter ac:name="maxLevel">3</ac:parameter>
</ac:structured-macro>

<h1>System Overview</h1>
<p>Content here...</p>

<ac:structured-macro ac:name="code">
  <ac:parameter ac:name="language">yaml</ac:parameter>
  <ac:plain-text-body><![CDATA[
    yaml content here
  ]]></ac:plain-text-body>
</ac:structured-macro>
```

## Key Macros

| Macro | Usage |
|-------|-------|
| `ac:toc` | Table of contents |
| `ac:code` | Code blocks with language highlighting |
| `ac:expand` | Collapsible sections for detailed YAML |
| `ac:status` | Status badges (GREEN/YELLOW/RED) |
| `ac:panel` | Info/warning/note panels |

## Rules

- Use `<ac:structured-macro>` syntax (not wiki markup)
- Escape YAML in CDATA blocks
- Use status macros for confidence levels: GREEN=HIGH, YELLOW=MEDIUM, RED=LOW
- Include diagram images as attachments (reference with `ac:image`)
- File extension: `.confluence.html`
