# Contributing to Doc2ArchAgent

Thank you for your interest in contributing to Doc2ArchAgent! We welcome contributions from the community.

## Contributor License Agreement (CLA)

**Before we can accept your contribution, you must sign the Contributor License Agreement.**

By submitting a pull request, you agree that:

1. **You grant Michael J. Read a perpetual, worldwide, non-exclusive, royalty-free, irrevocable license** to use, reproduce, modify, distribute, sublicense, and otherwise exploit your contribution in any form, including under licenses other than the BSL 1.1 (dual licensing).

2. **You represent that you have the right** to grant this license — i.e., the contribution is your original work, or you have permission from the copyright holder.

3. **You understand that your contribution will be licensed** under the Business Source License 1.1 as part of the Licensed Work, and may also be offered under commercial licenses by the Licensor.

4. **You are not expected to provide support** for your contribution, but you may do so voluntarily.

This CLA is necessary because Doc2ArchAgent uses dual licensing (BSL 1.1 for open use + commercial licenses for production use). Without a CLA, the Licensor cannot include community contributions in commercially licensed distributions.

### How to Sign

By opening a pull request, you implicitly agree to the CLA terms above. Your pull request description should include:

```
I have read and agree to the Doc2ArchAgent Contributor License Agreement.
```

## How to Contribute

### Reporting Bugs

- Use [GitHub Issues](https://github.com/michael-jread/doc2archagent/issues) to report bugs
- Include steps to reproduce, expected behavior, and actual behavior
- Include your environment details (OS, Python version, tool versions)

### Suggesting Features

- Open a GitHub Issue with the `enhancement` label
- Describe the use case and expected behavior
- Explain how it fits into the existing agent workflow

### Submitting Code

1. **Fork** the repository
2. **Create a branch** from `main` for your changes
3. **Follow existing code conventions** — match the style of surrounding code
4. **Test your changes** — run `python tools/validate.py` on any modified YAML
5. **Submit a pull request** with a clear description of the changes

### Agent Contributions

If modifying or creating `.agent.md` files:

- Keep instruction body under **30,000 characters** (GitHub Copilot hard limit)
- Follow the existing UX conventions (status indicators, progress tracking, micro-confirmations)
- Maintain the zero-hallucination invariant for extraction agents
- Update handoff references in other agents if changing agent names
- Test the agent in VS Code with GitHub Copilot Chat

### Tool Script Contributions

If modifying or creating `tools/` scripts:

- Use lazy imports for optional dependencies
- Provide JSON output for agent consumption
- Degrade gracefully when optional packages are missing
- Update `tools/requirements.txt` if adding dependencies

## Code of Conduct

- Be respectful and constructive in all interactions
- Focus on the technical merits of contributions
- Welcome newcomers and help them understand the codebase

## Questions?

Open an issue on GitHub or reach out via the repository's discussion channels.
