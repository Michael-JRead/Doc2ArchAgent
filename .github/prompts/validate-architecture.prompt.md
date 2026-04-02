---
description: Validate architecture YAML files for correctness and security posture
---

Run the following validation steps in order:

1. **Schema validation**: Run `python tools/validate.py` on the system.yaml and networks.yaml files. Use `--format table` for readable output. Report any ARCH001–ARCH011 errors.

2. **Threat analysis**: Run `python tools/threat-rules.py` on the same files with `--format table`. Include `--networks` and `--deployment` flags if those files exist. Report findings grouped by severity.

3. **Summary**: Provide a brief summary of:
   - Total validation errors and warnings
   - Total threat findings by severity (critical/high/medium/low/info)
   - Top 3 highest-priority items to fix

If all checks pass, confirm the architecture is clean.
