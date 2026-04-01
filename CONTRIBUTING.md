# Contributing to Doc2ArchAgent

Thank you for your interest in contributing to Doc2ArchAgent! We welcome bug reports, feature suggestions, and code contributions from the community.

## Important: Licensing and CLA

Doc2ArchAgent is licensed under the [Business Source License 1.1](LICENSE) (BSL 1.1). This is a **source-available license, not an open source license**. The project uses a dual-licensing model: BSL 1.1 for public use, and separate commercial licenses for production/enterprise use.

### Contributor License Agreement (Required)

**All contributors must sign the [Contributor License Agreement (CLA)](CLA.md) before contributions can be merged.**

The CLA grants the Licensor rights to sublicense your contribution under both the BSL 1.1 and commercial license terms. This is necessary because, without a CLA, community contributions cannot be included in commercially licensed distributions.

**How it works:**
1. Open a pull request
2. The CLA Assistant bot will comment asking you to sign
3. Read the [CLA](CLA.md) and post this comment on the PR:
   > I have read the CLA Document and I hereby sign the CLA
4. Your signature is recorded — you only sign once

PRs from unsigned contributors **cannot be merged** until the CLA is signed.

**Key points of the CLA:**
- You retain copyright ownership of your contributions
- You grant a broad, irrevocable license (including sublicensing rights) to the Licensor
- You grant a patent license covering your contributions
- You acknowledge the dual-licensing model
- See the full [CLA text](CLA.md) for details

---

## How to Contribute

### Reporting Bugs

- Use [GitHub Issues](https://github.com/michael-jread/doc2archagent/issues) to report bugs
- Include: steps to reproduce, expected behavior, actual behavior
- Include: OS, Python version, relevant tool versions (`bash tools/detect-tools.sh`)

### Suggesting Features

- Open a GitHub Issue with the `enhancement` label
- Describe the use case, expected behavior, and how it fits the existing agent workflow

### Submitting Code

1. **Fork** the repository and create a branch from `main`
2. **Sign the CLA** on your first pull request (automated via CLA Assistant)
3. **Follow existing code style** — match the conventions of surrounding code
4. **Test your changes:**
   - Run `python tools/validate.py` on any modified YAML
   - Run `python tools/validate-provenance.py` for provenance changes
5. **Submit a pull request** with a clear description of your changes

### Third-Party Code

If your contribution includes code from external sources (libraries, Stack Overflow, other projects), you **must** disclose this in your pull request description, including:
- The source of the code
- Its license terms
- Any restrictions that may apply

Contributions containing undisclosed third-party code will be rejected.

---

## Contribution Guidelines

### Agent Files (`.agent.md`)

- Keep instruction body under **30,000 characters** (GitHub Copilot hard limit)
- Follow existing UX conventions (status indicators, progress tracking, micro-confirmations)
- Maintain the zero-hallucination invariant for extraction agents
- Update handoff references in other agents if changing agent names

### Tool Scripts (`tools/`)

- Include the SPDX copyright header at the top of new files:
  ```
  # Copyright (c) 2026 Michael J. Read. All rights reserved.
  # SPDX-License-Identifier: BUSL-1.1
  ```
- Use lazy imports for optional dependencies
- Provide JSON output for agent consumption
- Degrade gracefully when optional packages are missing
- Update `tools/requirements.txt` if adding dependencies

### YAML Schema

- Follow the schema defined in `templates/system.yaml.example`
- Use kebab-case for all `id` fields
- Validate with `python tools/validate.py` before submitting

---

## Review Process

1. **CLA check** — automated, must pass before review
2. **Code review** — a maintainer will review your changes
3. **Testing** — validation scripts must pass
4. **Merge** — maintainer merges after approval

---

## Code of Conduct

- Be respectful and constructive in all interactions
- Focus on the technical merits of contributions
- Welcome newcomers and help them understand the codebase

---

## Questions?

Open an issue on GitHub or reach out via the repository's discussion channels.
