# Doc2ArchAgent

Multi-agent architecture modeling system for VS Code, powered by GitHub Copilot custom agents.

## Prerequisites

- **VS Code** (1.100+)
- **GitHub Copilot** extension (with active subscription)
- **GitHub Copilot Chat** extension

## Quick Start

1. Open this folder in VS Code
2. Open Copilot Chat (Ctrl+Shift+I / Cmd+Shift+I)
3. Select **@architect** from the agents dropdown
4. Type: `Model a payment processing platform`
5. Follow the agent's guided questions

## Agents

| Agent | Purpose | Invoke |
|-------|---------|--------|
| **architect** | Main orchestrator. Walks through Contexts, Containers, Components | `@architect` |
| **deployer** | Places containers into network zones for specific environments | `@deployer` |
| **security-reviewer** | Analyzes YAML for vulnerabilities and trust boundary issues | `@security-reviewer` |
| **diagram-generator** | Generates C4 diagrams (Mermaid + PlantUML) | `@diagram-generator` |
| **validator** | Checks structural correctness and referential integrity | `@validator` |

## Workflow

```
@architect → Layers 1-3 (Contexts, Containers, Components)
    ↓ handoff
@deployer → Layer 4 (Deployments into network zones)
    ↓ handoff
@security-reviewer → Security findings, blast radius, network crossings
    ↓ handoff
@diagram-generator → C4 diagrams at all levels
    ↓ handoff
@validator → Structural validation and integrity checks
```

Each agent can hand off to any other agent. Use the handoff buttons in the chat or ask directly.

## File Structure

```
architecture/
    networks.yaml                          — Shared network zones + infrastructure
    <system-id>/
        system.yaml                        — System model (contexts, containers, components)
        deployments/
            <deployment-id>.yaml           — Deployment placements
        diagrams/
            *-context.md / .puml           — C4 Context diagrams
            *-container.md / .puml         — C4 Container diagrams
            *-component.md / .puml         — C4 Component diagrams
            *-deployment-*.md / .puml      — C4 Deployment diagrams
            *-network-crossings.md         — Network crossing reports
            security-findings.md           — Security analysis
```

## Commands

These commands work with any agent:

- `Show YAML` — Display all current YAML files
- `Validate` — Run structural validation
- `Generate diagrams` — Produce all C4 diagrams
- `Show security findings` — Run security analysis
- `Show blast radius for <container-id>` — Impact analysis
- `Show network crossings for <deployment-id>` — Zone crossing report

## Templates

See `templates/` for annotated example YAML files:
- `system.yaml.example` — Full system model with all entity types
- `networks.yaml.example` — Network zones and infrastructure resources
