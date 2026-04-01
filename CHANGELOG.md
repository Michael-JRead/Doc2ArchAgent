# Changelog

All notable changes to Doc2ArchAgent will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- JSON Schema files for system.yaml, networks.yaml, and deployment.yaml validation
- `--format` flag for validate.py (json, table, sarif)
- `--strict` mode for validate.py (treat warnings as errors)
- SARIF output support for GitHub Security tab integration
- GitHub Actions workflow for automated architecture validation on PRs
- Complete example output set in `examples/` directory
- pytest test suite for validation tools
- CWE mappings for security findings (`context/cwe-mappings.yaml`)
- STRIDE-to-CAPEC-to-ATT&CK mapping file (`context/stride-to-attack.yaml`)
- Compliance control mapping (`context/compliance-mappings.yaml`)
- Risk scoring methodology with severity, likelihood, and impact dimensions
- Structurizr DSL renderer agent (`@diagram-structurizr`)
- D2 renderer agent (`@diagram-d2`)
- Architecture diff agent (`@diagram-diff`)
- Blast radius lateral movement analysis in security reviewer
- Terraform/CloudFormation ingestion support
- OpenAPI/Swagger ingestion support
- Kubernetes manifest ingestion support
- Structurizr DSL import support
- `.gitignore` for Python, IDE, and OS artifacts

### Fixed
- Clone URL in README (was `Arch2DocAgent`, corrected to `Doc2ArchAgent`)

## [0.1.0] - 2026-03-30

### Added
- Initial release of Doc2ArchAgent
- 12 GitHub Copilot custom agents for architecture modeling
  - `@architect` — C4 architecture modeling through focused questions
  - `@deployer` — Deployment mapping to network zones
  - `@security-reviewer` — STRIDE analysis and threat modeling
  - `@validator` — Deterministic YAML schema validation
  - `@diagram-generator` — Diagram orchestration with persona views
  - `@diagram-mermaid` — Mermaid diagram rendering
  - `@diagram-plantuml` — PlantUML diagram rendering
  - `@diagram-drawio` — Draw.io XML diagram rendering
  - `@doc-collector` — Document collection and format conversion
  - `@doc-extractor` — Entity extraction with provenance tracking
  - `@doc-writer` — HLDD and Confluence documentation generation
  - `@pattern-manager` — Reusable network and product pattern management
- YAML schema for system architecture (system.yaml, networks.yaml, deployments)
- Deterministic validation tool (`tools/validate.py`)
- Pattern validation tool (`tools/validate-patterns.py`)
- Provenance validation tool (`tools/validate-provenance.py`)
- Document conversion tool (`tools/convert-docs.py`)
- Diagram file parser (`tools/parse-diagram-file.py`)
- Tool detection script (`tools/detect-tools.sh`)
- Architecture templates (`templates/`)
- Pattern catalog system with network and product patterns
- Zero-hallucination pipeline with 4-factor confidence scoring
- Business Source License 1.1 with Apache 2.0 change license (2030-04-01)
- Contributor License Agreement (CLA) with automated enforcement

[Unreleased]: https://github.com/Michael-JRead/Doc2ArchAgent/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Michael-JRead/Doc2ArchAgent/releases/tag/v0.1.0
