#!/usr/bin/env python3
# Copyright (c) 2026 Michael J. Read. All rights reserved.
# SPDX-License-Identifier: BUSL-1.1
"""Comprehensive regression test suite for Doc2ArchAgent.

Tests are organized in layers:
  L1 — Smoke: Python syntax, imports, CLI help
  L2 — Schema: YAML validity, JSON schema validity, schema conformance
  L3 — Referential: Cross-file references, catalog consistency
  L4 — Functional: Core tool functions produce expected output
  L5 — Integration: End-to-end validation pipelines
  L6 — Contract: Schema-code synchronization
"""

import importlib
import json
import os
import py_compile
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent
TOOLS_DIR = PROJECT_ROOT / "tools"
SCHEMAS_DIR = PROJECT_ROOT / "schemas"
CONTEXT_DIR = PROJECT_ROOT / "context"
PATTERNS_DIR = PROJECT_ROOT / "patterns"
EXAMPLES_DIR = PROJECT_ROOT / "examples"
AGENTS_DIR = PROJECT_ROOT / ".github" / "agents"
WORKFLOWS_DIR = PROJECT_ROOT / ".github" / "workflows"
FIXTURES_DIR = Path(__file__).parent / "fixtures"
REGRESSION_DIR = FIXTURES_DIR / "regression"

sys.path.insert(0, str(TOOLS_DIR))

# All Python tool scripts in the repo
ALL_TOOL_SCRIPTS = sorted(TOOLS_DIR.glob("*.py"))

# Hyphenated module names need special import handling
def _module_name(path: Path) -> str:
    return path.stem.replace("-", "_")


# ============================================================================
# L1 — SMOKE TESTS: Python syntax, imports, CLI --help
# ============================================================================

class TestPythonSyntax:
    """Every .py file must compile without syntax errors."""

    @pytest.mark.parametrize("script", ALL_TOOL_SCRIPTS, ids=lambda p: p.name)
    def test_compiles(self, script):
        py_compile.compile(str(script), doraise=True)

    @pytest.mark.parametrize("script", sorted((PROJECT_ROOT / "tests").glob("*.py")),
                             ids=lambda p: p.name)
    def test_test_files_compile(self, script):
        py_compile.compile(str(script), doraise=True)


class TestPythonImports:
    """Core tool modules must import without error (given pyyaml is installed)."""

    # These modules only need pyyaml to import
    IMPORTABLE = [
        "validate.py",
        "validate-patterns.py",
        "validate-provenance.py",
        "verify-claims.py",
        "threat-rules.py",
        "ingest-kubernetes.py",
        "ingest-openapi.py",
        "ingest-terraform.py",
        "ingest-structurizr.py",
        "parse-diagram-file.py",
    ]

    @pytest.mark.parametrize("script_name", IMPORTABLE)
    def test_import_succeeds(self, script_name):
        script = TOOLS_DIR / script_name
        mod_name = _module_name(script)
        # Use importlib to import the module by file path
        spec = importlib.util.spec_from_file_location(mod_name, str(script))
        assert spec is not None, f"Cannot create import spec for {script_name}"
        mod = importlib.util.module_from_spec(spec)
        # Some modules call sys.exit on missing deps — catch that
        try:
            spec.loader.exec_module(mod)
        except SystemExit:
            pytest.skip(f"{script_name} exited (likely missing optional dep)")


class TestCLIHelp:
    """Every tool with argparse must respond to --help without error."""

    # Only tools that use argparse (validate-patterns.py and validate-provenance.py
    # use custom CLI parsing without --help support)
    CLI_TOOLS = [
        "validate.py",
        "verify-claims.py",
        "threat-rules.py",
        "convert-docs.py",
        "ingest-kubernetes.py",
        "ingest-openapi.py",
        "ingest-terraform.py",
        "ingest-structurizr.py",
        "parse-diagram-file.py",
        "sync-attack-data.py",
    ]

    @pytest.mark.parametrize("script_name", CLI_TOOLS)
    def test_help_exits_zero(self, script_name):
        result = subprocess.run(
            [sys.executable, str(TOOLS_DIR / script_name), "--help"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"--help failed for {script_name}: {result.stderr}"
        assert len(result.stdout) > 20, f"--help output too short for {script_name}"


# ============================================================================
# L2 — SCHEMA TESTS: YAML validity, JSON schema validity, conformance
# ============================================================================

class TestYamlFileValidity:
    """Every YAML file in the repo must parse cleanly."""

    @staticmethod
    def _all_yaml_files():
        for pattern in ("**/*.yaml", "**/*.yml"):
            for path in PROJECT_ROOT.glob(pattern):
                # Skip node_modules, .git, etc.
                parts = path.relative_to(PROJECT_ROOT).parts
                if any(p.startswith(".") and p != ".github" for p in parts):
                    continue
                yield path

    @pytest.mark.parametrize("yaml_file", list(_all_yaml_files.__func__()),
                             ids=lambda p: str(p.relative_to(PROJECT_ROOT)))
    def test_yaml_parses(self, yaml_file):
        with open(yaml_file) as f:
            content = f.read()
        # Some YAML files are multi-document (K8s manifests)
        try:
            docs = list(yaml.safe_load_all(content))
        except yaml.YAMLError as e:
            pytest.fail(f"YAML parse error in {yaml_file}: {e}")
        assert docs is not None


class TestJsonSchemaValidity:
    """All JSON schema files must be valid JSON Schema draft 2020-12."""

    SCHEMA_FILES = sorted(SCHEMAS_DIR.glob("*.json"))

    @pytest.mark.parametrize("schema_file", SCHEMA_FILES, ids=lambda p: p.name)
    def test_schema_is_valid_json(self, schema_file):
        with open(schema_file) as f:
            data = json.load(f)
        assert isinstance(data, dict)
        assert "$schema" in data or "type" in data

    @pytest.mark.parametrize("schema_file", SCHEMA_FILES, ids=lambda p: p.name)
    def test_schema_validates_with_jsonschema(self, schema_file):
        from jsonschema import Draft202012Validator
        with open(schema_file) as f:
            schema = json.load(f)
        # This checks the schema itself is valid meta-schema
        Draft202012Validator.check_schema(schema)


class TestExampleSchemaConformance:
    """Example YAML files must conform to their JSON schemas."""

    def _load_schema(self, name):
        with open(SCHEMAS_DIR / name) as f:
            return json.load(f)

    def _load_yaml(self, path):
        with open(path) as f:
            return yaml.safe_load(f)

    def test_example_system_conforms_to_schema(self):
        from jsonschema import validate, Draft202012Validator
        schema = self._load_schema("system.schema.json")
        data = self._load_yaml(EXAMPLES_DIR / "payment-platform" / "system.yaml")
        validate(instance=data, schema=schema, cls=Draft202012Validator)

    def test_example_networks_conforms_to_schema(self):
        from jsonschema import validate, Draft202012Validator
        schema = self._load_schema("networks.schema.json")
        data = self._load_yaml(EXAMPLES_DIR / "networks.yaml")
        validate(instance=data, schema=schema, cls=Draft202012Validator)

    def test_example_deployment_conforms_to_schema(self):
        from jsonschema import validate, Draft202012Validator
        deploy_file = EXAMPLES_DIR / "payment-platform" / "deployments" / "prod-us-east.yaml"
        if not deploy_file.exists():
            pytest.skip("No deployment example found")
        schema = self._load_schema("deployment.schema.json")
        data = self._load_yaml(deploy_file)
        validate(instance=data, schema=schema, cls=Draft202012Validator)

    def test_example_provenance_conforms_to_schema(self):
        from jsonschema import validate, Draft202012Validator
        prov_file = EXAMPLES_DIR / "payment-platform" / "provenance.yaml"
        if not prov_file.exists():
            pytest.skip("No provenance example found")
        schema = self._load_schema("provenance.schema.json")
        data = self._load_yaml(prov_file)
        validate(instance=data, schema=schema, cls=Draft202012Validator)


# ============================================================================
# L3 — REFERENTIAL INTEGRITY: Cross-file references
# ============================================================================

class TestContextFileIntegrity:
    """Context YAML files must have expected structure and valid cross-refs."""

    def test_threat_rules_structure(self):
        with open(CONTEXT_DIR / "threat-rules.yaml") as f:
            data = yaml.safe_load(f)
        assert "rules" in data, "threat-rules.yaml must have 'rules' key"
        rules = data["rules"]
        assert isinstance(rules, list) and len(rules) > 0

        for rule in rules:
            assert "id" in rule, f"Rule missing 'id': {rule.get('title', 'unknown')}"
            assert "title" in rule, f"Rule {rule['id']} missing 'title'"
            assert "stride" in rule, f"Rule {rule['id']} missing 'stride'"
            assert "severity" in rule, f"Rule {rule['id']} missing 'severity'"
            assert "iterate_over" in rule, f"Rule {rule['id']} missing 'iterate_over'"
            assert "conditions" in rule, f"Rule {rule['id']} missing 'conditions'"

    def test_threat_rules_valid_iterate_over(self):
        valid_targets = {"listeners", "components", "relationships", "zones", "containers",
                         "trust_boundaries", "external_systems"}
        with open(CONTEXT_DIR / "threat-rules.yaml") as f:
            data = yaml.safe_load(f)
        for rule in data["rules"]:
            assert rule["iterate_over"] in valid_targets, (
                f"Rule {rule['id']} has invalid iterate_over: {rule['iterate_over']}"
            )

    def test_threat_rules_valid_stride(self):
        valid_stride = {"spoofing", "tampering", "repudiation",
                        "information_disclosure", "denial_of_service",
                        "elevation_of_privilege"}
        with open(CONTEXT_DIR / "threat-rules.yaml") as f:
            data = yaml.safe_load(f)
        for rule in data["rules"]:
            # Some rules (e.g., model quality checks) may have stride=None
            if rule["stride"] is not None:
                assert rule["stride"] in valid_stride, (
                    f"Rule {rule['id']} has invalid STRIDE: {rule['stride']}"
                )

    def test_threat_rules_unique_ids(self):
        with open(CONTEXT_DIR / "threat-rules.yaml") as f:
            data = yaml.safe_load(f)
        ids = [r["id"] for r in data["rules"]]
        assert len(ids) == len(set(ids)), f"Duplicate rule IDs: {[x for x in ids if ids.count(x) > 1]}"

    def test_threat_applicability_structure(self):
        with open(CONTEXT_DIR / "threat-applicability.yaml") as f:
            data = yaml.safe_load(f)
        assert "global_suppressions" in data
        assert "environment_thresholds" in data

    def test_stride_to_attack_categories(self):
        with open(CONTEXT_DIR / "stride-to-attack.yaml") as f:
            data = yaml.safe_load(f)
        assert "stride_categories" in data
        categories = data["stride_categories"]
        stride_ids = {c["id"] for c in categories}
        expected = {"spoofing", "tampering", "repudiation",
                    "information_disclosure", "denial_of_service",
                    "elevation_of_privilege"}
        assert stride_ids == expected, f"STRIDE categories mismatch: {stride_ids ^ expected}"

    def test_compliance_mappings_structure(self):
        with open(CONTEXT_DIR / "compliance-mappings.yaml") as f:
            data = yaml.safe_load(f)
        assert "frameworks" in data
        for fw in data["frameworks"]:
            assert "id" in fw, f"Framework missing 'id'"
            assert "name" in fw, f"Framework {fw.get('id', '?')} missing 'name'"
            assert "controls" in fw, f"Framework {fw['id']} missing 'controls'"

    def test_cwe_mappings_structure(self):
        path = CONTEXT_DIR / "cwe-mappings.yaml"
        if not path.exists():
            pytest.skip("cwe-mappings.yaml not found")
        with open(path) as f:
            data = yaml.safe_load(f)
        assert data is not None

    def test_risk_scoring_structure(self):
        with open(CONTEXT_DIR / "risk-scoring.yaml") as f:
            data = yaml.safe_load(f)
        assert "severity_levels" in data
        assert "methodology" in data
        levels = data["severity_levels"]
        level_names = {l["level"] for l in levels}
        assert {"critical", "high", "medium", "low"}.issubset(level_names)


class TestPatternIntegrity:
    """Pattern files and catalogs must be consistent."""

    def test_network_patterns_validate(self):
        from importlib.util import spec_from_file_location, module_from_spec
        spec = spec_from_file_location("validate_patterns",
                                       str(TOOLS_DIR / "validate-patterns.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        for pattern_file in PATTERNS_DIR.rglob("*.pattern.yaml"):
            result = mod.validate_pattern_file(pattern_file)
            assert result["valid"] is True, (
                f"{pattern_file.name} validation failed: {result['errors']}"
            )

    def test_network_catalog_references_exist(self):
        catalog_path = PATTERNS_DIR / "networks" / "_catalog.yaml"
        with open(catalog_path) as f:
            catalog = yaml.safe_load(f)

        self._check_catalog_files(catalog["catalog"]["tree"],
                                  PATTERNS_DIR / "networks")

    def test_product_catalog_references_exist(self):
        catalog_path = PATTERNS_DIR / "products" / "_catalog.yaml"
        with open(catalog_path) as f:
            catalog = yaml.safe_load(f)

        self._check_catalog_files(catalog["catalog"]["tree"],
                                  PATTERNS_DIR / "products")

    def _check_catalog_files(self, tree_nodes, base_dir):
        for node in tree_nodes:
            for pattern in node.get("patterns", []):
                if "file" in pattern:
                    pattern_path = base_dir / pattern["file"]
                    assert pattern_path.exists(), (
                        f"Catalog references missing file: {pattern['file']}"
                    )
            for child in node.get("children", []):
                self._check_catalog_files([child], base_dir)


class TestAgentFileIntegrity:
    """Agent .md files must reference tools that exist."""

    AGENT_FILES = sorted(AGENTS_DIR.glob("*.agent.md")) if AGENTS_DIR.exists() else []

    @pytest.mark.parametrize("agent_file", AGENT_FILES, ids=lambda p: p.name)
    def test_agent_tool_references(self, agent_file):
        content = agent_file.read_text()
        # Look for tool references like: tools/validate.py, tools/threat-rules.py
        tool_refs = re.findall(r'tools/([a-z0-9_-]+\.py)', content)
        for ref in tool_refs:
            tool_path = TOOLS_DIR / ref
            assert tool_path.exists(), (
                f"Agent {agent_file.name} references missing tool: tools/{ref}"
            )

    @pytest.mark.parametrize("agent_file", AGENT_FILES, ids=lambda p: p.name)
    def test_agent_schema_references(self, agent_file):
        content = agent_file.read_text()
        schema_refs = re.findall(r'schemas/([a-z0-9_-]+\.(?:json|yaml))', content)
        for ref in schema_refs:
            schema_path = SCHEMAS_DIR / ref
            assert schema_path.exists(), (
                f"Agent {agent_file.name} references missing schema: schemas/{ref}"
            )


class TestWorkflowIntegrity:
    """GitHub workflow YAML files must be valid and reference existing scripts."""

    WORKFLOW_FILES = sorted(WORKFLOWS_DIR.glob("*.yml")) if WORKFLOWS_DIR.exists() else []

    @pytest.mark.parametrize("wf_file", WORKFLOW_FILES, ids=lambda p: p.name)
    def test_workflow_parses(self, wf_file):
        with open(wf_file) as f:
            data = yaml.safe_load(f)
        assert isinstance(data, dict)
        assert "name" in data or "on" in data, f"Workflow {wf_file.name} missing 'name' or 'on'"

    @pytest.mark.parametrize("wf_file", WORKFLOW_FILES, ids=lambda p: p.name)
    def test_workflow_script_references(self, wf_file):
        content = wf_file.read_text()
        script_refs = re.findall(r'(?:python|python3)\s+tools/([a-z0-9_-]+\.py)', content)
        for ref in script_refs:
            tool_path = TOOLS_DIR / ref
            assert tool_path.exists(), (
                f"Workflow {wf_file.name} references missing tool: tools/{ref}"
            )


# ============================================================================
# L4 — FUNCTIONAL TESTS: Core tool functions produce expected output
# ============================================================================

class TestValidateFunctional:
    """validate.py produces correct results for known inputs."""

    def test_example_system_passes(self):
        from validate import validate
        system = EXAMPLES_DIR / "payment-platform" / "system.yaml"
        networks = EXAMPLES_DIR / "networks.yaml"
        result = validate(str(system), str(networks))
        assert result["valid"] is True, f"Example system failed: {result['errors']}"

    def test_regression_threat_model_system_passes(self):
        from validate import validate
        result = validate(str(REGRESSION_DIR / "threat-model-system.yaml"))
        assert result["valid"] is True, f"Threat model fixture failed: {result['errors']}"


class TestValidatePatternsFunctional:
    """validate-patterns.py produces correct results for known inputs."""

    def test_standard_3tier_passes(self):
        from importlib.util import spec_from_file_location, module_from_spec
        spec = spec_from_file_location("validate_patterns",
                                       str(TOOLS_DIR / "validate-patterns.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        result = mod.validate_pattern_file(
            PATTERNS_DIR / "networks" / "usa" / "standard-3tier.pattern.yaml"
        )
        assert result["valid"] is True, f"3-tier pattern failed: {result['errors']}"

    def test_ibm_mq_passes(self):
        from importlib.util import spec_from_file_location, module_from_spec
        spec = spec_from_file_location("validate_patterns",
                                       str(TOOLS_DIR / "validate-patterns.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        result = mod.validate_pattern_file(
            PATTERNS_DIR / "products" / "messaging" / "ibm-mq.pattern.yaml"
        )
        assert result["valid"] is True, f"IBM MQ pattern failed: {result['errors']}"


class TestIngestKubernetes:
    """ingest-kubernetes.py correctly parses K8s manifests."""

    @pytest.fixture(autouse=True)
    def _load_module(self):
        spec = importlib.util.spec_from_file_location(
            "ingest_kubernetes", str(TOOLS_DIR / "ingest-kubernetes.py"))
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)

    def test_parses_deployment(self):
        content = (REGRESSION_DIR / "minimal-k8s.yaml").read_text()
        result = self.mod.parse_kubernetes_manifests(content)
        assert result["metadata"]["source_format"] == "kubernetes"
        assert len(result["components"]) >= 1, "Should extract at least one component"

    def test_parses_namespace(self):
        content = (REGRESSION_DIR / "minimal-k8s.yaml").read_text()
        result = self.mod.parse_kubernetes_manifests(content)
        zone_ids = [z["id"] for z in result["network_zones"]]
        assert "production" in zone_ids, f"Should extract namespace as zone, got: {zone_ids}"

    def test_parses_service_listeners(self):
        content = (REGRESSION_DIR / "minimal-k8s.yaml").read_text()
        result = self.mod.parse_kubernetes_manifests(content)
        assert len(result["listeners"]) >= 1, "Should extract at least one listener from Service"


class TestIngestOpenAPI:
    """ingest-openapi.py correctly parses OpenAPI specs."""

    @pytest.fixture(autouse=True)
    def _load_module(self):
        spec = importlib.util.spec_from_file_location(
            "ingest_openapi", str(TOOLS_DIR / "ingest-openapi.py"))
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)

    def test_parses_openapi3(self):
        content = (REGRESSION_DIR / "minimal-openapi.yaml").read_text()
        result = self.mod.parse_openapi(content)
        assert "error" not in result
        assert result["metadata"]["openapi_version"] == "3.0.3"
        assert result["metadata"]["api_title"] == "Pet Store API"

    def test_extracts_security_schemes(self):
        content = (REGRESSION_DIR / "minimal-openapi.yaml").read_text()
        result = self.mod.parse_openapi(content)
        assert len(result["security_schemes"]) >= 1, "Should extract bearerAuth scheme"

    def test_extracts_listeners(self):
        content = (REGRESSION_DIR / "minimal-openapi.yaml").read_text()
        result = self.mod.parse_openapi(content)
        assert len(result["listeners"]) >= 1 or len(result["components"]) >= 1, (
            "Should extract listeners or components from paths"
        )


class TestIngestTerraform:
    """ingest-terraform.py correctly parses Terraform HCL."""

    @pytest.fixture(autouse=True)
    def _load_module(self):
        spec = importlib.util.spec_from_file_location(
            "ingest_terraform", str(TOOLS_DIR / "ingest-terraform.py"))
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)

    def test_parses_vpc(self):
        content = (REGRESSION_DIR / "minimal-terraform.tf").read_text()
        result = self.mod.parse_terraform_hcl(content)
        zone_ids = [z["id"] for z in result["network_zones"]]
        assert "main" in zone_ids, f"Should extract VPC as zone, got: {zone_ids}"

    def test_parses_subnet(self):
        content = (REGRESSION_DIR / "minimal-terraform.tf").read_text()
        result = self.mod.parse_terraform_hcl(content)
        zone_ids = [z["id"] for z in result["network_zones"]]
        assert "public" in zone_ids, f"Should extract subnet as zone, got: {zone_ids}"

    def test_parses_lambda(self):
        content = (REGRESSION_DIR / "minimal-terraform.tf").read_text()
        result = self.mod.parse_terraform_hcl(content)
        container_ids = [c["id"] for c in result["containers"]]
        assert len(container_ids) >= 1, "Should extract Lambda as container"

    def test_parses_security_group(self):
        content = (REGRESSION_DIR / "minimal-terraform.tf").read_text()
        result = self.mod.parse_terraform_hcl(content)
        infra_ids = [r["id"] for r in result["infrastructure_resources"]]
        assert "web" in infra_ids, f"Should extract SG as infra resource, got: {infra_ids}"


class TestIngestStructurizr:
    """ingest-structurizr.py correctly parses Structurizr DSL."""

    @pytest.fixture(autouse=True)
    def _load_module(self):
        spec = importlib.util.spec_from_file_location(
            "ingest_structurizr", str(TOOLS_DIR / "ingest-structurizr.py"))
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)

    def test_parses_workspace(self):
        content = (REGRESSION_DIR / "minimal-structurizr.dsl").read_text()
        result = self.mod.parse_structurizr_dsl(content)
        assert result["metadata"]["workspace_name"] == "Test System"

    def test_extracts_persons(self):
        content = (REGRESSION_DIR / "minimal-structurizr.dsl").read_text()
        result = self.mod.parse_structurizr_dsl(content)
        assert len(result["persons"]) >= 1, "Should extract person 'User'"

    def test_extracts_containers(self):
        content = (REGRESSION_DIR / "minimal-structurizr.dsl").read_text()
        result = self.mod.parse_structurizr_dsl(content)
        assert len(result["containers"]) >= 1, "Should extract containers"

    def test_extracts_relationships(self):
        content = (REGRESSION_DIR / "minimal-structurizr.dsl").read_text()
        result = self.mod.parse_structurizr_dsl(content)
        assert len(result["relationships"]) >= 1, "Should extract relationships"


class TestParseDiagramFile:
    """parse-diagram-file.py correctly parses Draw.io XML."""

    @pytest.fixture(autouse=True)
    def _load_module(self):
        spec = importlib.util.spec_from_file_location(
            "parse_diagram_file", str(TOOLS_DIR / "parse-diagram-file.py"))
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)

    def test_parses_drawio(self):
        result = self.mod.parse_drawio(REGRESSION_DIR / "minimal-drawio.drawio")
        assert "components" in result
        assert "relationships" in result

    def test_extracts_components(self):
        result = self.mod.parse_drawio(REGRESSION_DIR / "minimal-drawio.drawio")
        labels = [c["label"] for c in result["components"]]
        assert "Web Server" in labels or "Database" in labels, (
            f"Should extract labeled vertices, got: {labels}"
        )

    def test_extracts_relationships(self):
        result = self.mod.parse_drawio(REGRESSION_DIR / "minimal-drawio.drawio")
        assert len(result["relationships"]) >= 1, "Should extract edge as relationship"


class TestThreatRulesEngine:
    """threat-rules.py evaluates rules against architecture models."""

    @pytest.fixture(autouse=True)
    def _load_module(self):
        spec = importlib.util.spec_from_file_location(
            "threat_rules", str(TOOLS_DIR / "threat-rules.py"))
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)

    def test_load_rules(self):
        rules = self.mod.load_rules()
        assert isinstance(rules, list)
        assert len(rules) > 0, "Should load at least one threat rule"

    def test_load_applicability(self):
        applicability = self.mod.load_applicability()
        assert isinstance(applicability, dict)

    def test_arch_model_creation(self):
        with open(REGRESSION_DIR / "threat-model-system.yaml") as f:
            system = yaml.safe_load(f)
        model = self.mod.ArchModel(system)
        assert len(model.components) == 2
        assert "public-api" in model.components
        assert "admin-panel" in model.components

    def test_evaluate_finds_unauthenticated_listener(self):
        with open(REGRESSION_DIR / "threat-model-system.yaml") as f:
            system = yaml.safe_load(f)
        model = self.mod.ArchModel(system)
        rules = self.mod.load_rules()
        applicability = self.mod.load_applicability()
        findings = self.mod.evaluate_rules(model, rules, applicability)
        rule_ids = [f.rule_id for f in findings]
        assert "unauthenticated-listener" in rule_ids, (
            f"Should detect unauthenticated listener, got rules: {rule_ids}"
        )

    def test_evaluate_finds_unencrypted_listener(self):
        with open(REGRESSION_DIR / "threat-model-system.yaml") as f:
            system = yaml.safe_load(f)
        model = self.mod.ArchModel(system)
        rules = self.mod.load_rules()
        applicability = self.mod.load_applicability()
        findings = self.mod.evaluate_rules(model, rules, applicability)
        rule_ids = [f.rule_id for f in findings]
        assert "unencrypted-listener" in rule_ids, (
            f"Should detect unencrypted listener, got rules: {rule_ids}"
        )


# ============================================================================
# L5 — INTEGRATION TESTS: End-to-end pipelines
# ============================================================================

class TestEndToEndValidationPipeline:
    """Full pipeline: YAML -> validate -> output formats."""

    def test_validate_then_json(self):
        from validate import validate, format_json
        result = validate(str(EXAMPLES_DIR / "payment-platform" / "system.yaml"),
                          str(EXAMPLES_DIR / "networks.yaml"))
        output = format_json(result)
        parsed = json.loads(output)
        assert parsed["valid"] is True

    def test_validate_then_sarif(self):
        from validate import validate, format_sarif
        result = validate(str(EXAMPLES_DIR / "payment-platform" / "system.yaml"),
                          str(EXAMPLES_DIR / "networks.yaml"))
        sarif = json.loads(format_sarif(result))
        assert sarif["version"] == "2.1.0"
        assert sarif["runs"][0]["tool"]["driver"]["name"] == "Doc2ArchAgent-Validate"

    def test_validate_then_table(self):
        from validate import validate, format_table
        result = validate(str(EXAMPLES_DIR / "payment-platform" / "system.yaml"),
                          str(EXAMPLES_DIR / "networks.yaml"))
        table = format_table(result)
        assert "PASS" in table

    def test_validate_cli_exit_code(self):
        result = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "validate.py"),
             str(EXAMPLES_DIR / "payment-platform" / "system.yaml"),
             str(EXAMPLES_DIR / "networks.yaml"),
             "--format", "json"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"CLI validation failed: {result.stderr}"
        parsed = json.loads(result.stdout)
        assert parsed["valid"] is True


class TestEndToEndThreatPipeline:
    """Full pipeline: YAML -> threat-rules -> findings."""

    def test_threat_cli_runs(self):
        result = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "threat-rules.py"),
             str(EXAMPLES_DIR / "payment-platform" / "system.yaml"),
             "--networks", str(EXAMPLES_DIR / "networks.yaml"),
             "--format", "json"],
            capture_output=True, text=True, timeout=30,
        )
        # Exit code 0 = no findings, 1 = findings found — both are valid
        assert result.returncode in (0, 1), f"Threat CLI crashed: {result.stderr}"
        parsed = json.loads(result.stdout)
        assert "findings" in parsed or isinstance(parsed, list)


# ============================================================================
# L6 — CONTRACT TESTS: Schema-code synchronization
# ============================================================================

class TestSchemaCodeSync:
    """JSON schema definitions must match Python validation constants."""

    def test_metadata_required_fields_match(self):
        with open(SCHEMAS_DIR / "system.schema.json") as f:
            schema = json.load(f)
        schema_required = set(schema["properties"]["metadata"]["required"])
        # The Python code checks these fields
        expected = {"name", "description", "owner", "status"}
        assert schema_required == expected, (
            f"Schema metadata required {schema_required} != code expected {expected}"
        )

    def test_status_enum_matches(self):
        with open(SCHEMAS_DIR / "system.schema.json") as f:
            schema = json.load(f)
        schema_statuses = set(
            schema["properties"]["metadata"]["properties"]["status"]["enum"]
        )
        from validate import VALID_STATUSES
        assert schema_statuses == VALID_STATUSES, (
            f"Schema statuses {schema_statuses} != code {VALID_STATUSES}"
        )

    def test_trust_levels_match(self):
        with open(SCHEMAS_DIR / "networks.schema.json") as f:
            schema = json.load(f)
        zone_props = schema["properties"]["network_zones"]["items"]["properties"]
        schema_trust = set(zone_props["trust"]["enum"])
        from validate import VALID_TRUST_LEVELS
        assert schema_trust == VALID_TRUST_LEVELS, (
            f"Schema trust levels {schema_trust} != code {VALID_TRUST_LEVELS}"
        )

    def test_sarif_rules_have_test_coverage(self):
        """Every SARIF rule ID should have at least one test fixture exercising it."""
        from validate import SARIF_RULES
        # Collect all ARCH* rule IDs mentioned in test fixture filenames and test code
        test_code = (Path(__file__).parent / "test_validate.py").read_text()
        tested_rules = set(re.findall(r'ARCH\d+', test_code))
        for rule_id in SARIF_RULES:
            if SARIF_RULES[rule_id]["defaultConfiguration"]["level"] == "error":
                assert rule_id in tested_rules, (
                    f"SARIF rule {rule_id} has no test coverage in test_validate.py"
                )

    def test_threat_rules_stride_matches_stride_yaml(self):
        """STRIDE values in threat-rules.yaml must match stride-to-attack.yaml categories."""
        with open(CONTEXT_DIR / "threat-rules.yaml") as f:
            rules_data = yaml.safe_load(f)
        with open(CONTEXT_DIR / "stride-to-attack.yaml") as f:
            stride_data = yaml.safe_load(f)

        valid_stride = {c["id"] for c in stride_data["stride_categories"]}
        for rule in rules_data["rules"]:
            # Some rules (model quality checks) have stride=None — skip those
            if rule["stride"] is not None:
                assert rule["stride"] in valid_stride, (
                    f"Rule {rule['id']} uses STRIDE '{rule['stride']}' "
                    f"not in stride-to-attack.yaml: {valid_stride}"
                )

    def test_pattern_zone_types_subset_of_schema(self):
        """Zone types in pattern validation must be a subset of network schema enums."""
        with open(SCHEMAS_DIR / "networks.schema.json") as f:
            schema = json.load(f)
        zone_props = schema["properties"]["network_zones"]["items"]["properties"]
        schema_zone_types = set(zone_props["zone_type"]["enum"])

        from importlib.util import spec_from_file_location, module_from_spec
        spec = spec_from_file_location("validate_patterns",
                                       str(TOOLS_DIR / "validate-patterns.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        assert mod.VALID_ZONE_TYPES == schema_zone_types, (
            f"Pattern zone types {mod.VALID_ZONE_TYPES} != schema {schema_zone_types}"
        )

    def test_pattern_trust_levels_match_schema(self):
        """Trust levels in pattern validation must match network schema."""
        with open(SCHEMAS_DIR / "networks.schema.json") as f:
            schema = json.load(f)
        zone_props = schema["properties"]["network_zones"]["items"]["properties"]
        schema_trust = set(zone_props["trust"]["enum"])

        from importlib.util import spec_from_file_location, module_from_spec
        spec = spec_from_file_location("validate_patterns",
                                       str(TOOLS_DIR / "validate-patterns.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        assert mod.VALID_TRUST_LEVELS == schema_trust, (
            f"Pattern trust {mod.VALID_TRUST_LEVELS} != schema {schema_trust}"
        )


# ============================================================================
# L7 — SHELL CONFIGURATION: Cross-platform shell support
# ============================================================================

SHELL_CONFIG_PATH = PROJECT_ROOT / ".github" / "shell-config.yaml"
COPILOT_INSTRUCTIONS_PATH = PROJECT_ROOT / ".github" / "copilot-instructions.md"
VALID_SHELL_TYPES = {"linux", "mac", "windows", "cmd", "other"}


class TestShellConfiguration:
    """Shell configuration for cross-platform agent support."""

    def test_shell_config_is_valid_yaml(self):
        assert SHELL_CONFIG_PATH.exists(), ".github/shell-config.yaml must exist"
        with open(SHELL_CONFIG_PATH) as f:
            data = yaml.safe_load(f)
        assert isinstance(data, dict), "shell-config.yaml must be a YAML mapping"

    def test_shell_config_has_required_fields(self):
        with open(SHELL_CONFIG_PATH) as f:
            data = yaml.safe_load(f)
        assert "shell_type" in data, "shell-config.yaml must have 'shell_type' key"

    def test_shell_config_valid_shell_types(self):
        with open(SHELL_CONFIG_PATH) as f:
            data = yaml.safe_load(f)
        assert data["shell_type"] in VALID_SHELL_TYPES, (
            f"shell_type must be one of {VALID_SHELL_TYPES}, got: {data['shell_type']}"
        )

    def test_detect_tools_py_exists(self):
        assert (TOOLS_DIR / "detect-tools.py").exists(), "tools/detect-tools.py must exist"

    def test_detect_tools_py_runs(self):
        result = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "detect-tools.py")],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"detect-tools.py failed: {result.stderr}"
        data = json.loads(result.stdout)
        assert "tools" in data, "Output must have 'tools' key"
        assert isinstance(data["tools"], list), "'tools' must be a list"
        assert len(data["tools"]) > 0, "'tools' list must not be empty"

    def test_detect_tools_output_matches_format(self):
        """JSON keys must match detect-tools.sh format."""
        result = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "detect-tools.py")],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(result.stdout)
        required_keys = {"name", "command", "available", "path", "version"}
        for tool in data["tools"]:
            assert required_keys.issubset(tool.keys()), (
                f"Tool {tool.get('name', '?')} missing keys: "
                f"{required_keys - tool.keys()}"
            )

    def test_agents_use_detect_tools_py_not_sh(self):
        """Agent files should reference detect-tools.py, not detect-tools.sh."""
        for agent_file in AGENTS_DIR.glob("*.agent.md"):
            content = agent_file.read_text()
            # Should not contain active bash invocations of detect-tools.sh
            assert "bash tools/detect-tools.sh" not in content, (
                f"{agent_file.name} still references 'bash tools/detect-tools.sh' — "
                "use 'python tools/detect-tools.py' instead"
            )

    def test_copilot_instructions_has_shell_section(self):
        content = COPILOT_INSTRUCTIONS_PATH.read_text()
        assert "## Shell Configuration" in content, (
            "copilot-instructions.md must contain a '## Shell Configuration' section"
        )


# ============================================================================
# L8 — PATTERN HIERARCHY: Separate network/product pattern architecture
# ============================================================================

DEPLOYMENTS_DIR = PROJECT_ROOT / "deployments"


class TestPatternDirectoryFormat:
    """New directory-format patterns with pattern.meta.yaml + system/networks YAML."""

    # --- Network pattern directory tests ---

    def test_network_pattern_dir_exists(self):
        pattern_dir = PATTERNS_DIR / "networks" / "usa" / "standard-3tier"
        assert pattern_dir.exists(), "Network pattern directory must exist"
        assert (pattern_dir / "pattern.meta.yaml").exists(), "Missing pattern.meta.yaml"
        assert (pattern_dir / "networks.yaml").exists(), "Missing networks.yaml"

    def test_network_pattern_meta_valid(self):
        meta_path = PATTERNS_DIR / "networks" / "usa" / "standard-3tier" / "pattern.meta.yaml"
        with open(meta_path) as f:
            data = yaml.safe_load(f)
        pattern = data["pattern"]
        assert pattern["id"] == "standard-3tier"
        assert pattern["type"] == "network"
        assert pattern["version"] == "1.0.0"
        assert "provides" in pattern
        assert "binding_points" in pattern

    def test_network_pattern_networks_yaml_valid(self):
        networks_path = PATTERNS_DIR / "networks" / "usa" / "standard-3tier" / "networks.yaml"
        with open(networks_path) as f:
            data = yaml.safe_load(f)
        assert "network_zones" in data
        assert len(data["network_zones"]) >= 1
        zone_ids = {z["id"] for z in data["network_zones"]}
        assert "dmz" in zone_ids

    def test_network_pattern_standalone_validation(self):
        """Network pattern validates independently via validate-patterns.py."""
        pattern_dir = PATTERNS_DIR / "networks" / "usa" / "standard-3tier"
        result = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "validate-patterns.py"), str(pattern_dir)],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"Validation failed: {result.stdout}"
        data = json.loads(result.stdout)
        assert data["valid"] is True, f"Pattern invalid: {data['errors']}"

    # --- Product pattern directory tests ---

    def test_product_pattern_dir_exists(self):
        pattern_dir = PATTERNS_DIR / "products" / "messaging" / "ibm-mq"
        assert pattern_dir.exists(), "Product pattern directory must exist"
        assert (pattern_dir / "pattern.meta.yaml").exists(), "Missing pattern.meta.yaml"
        assert (pattern_dir / "system.yaml").exists(), "Missing system.yaml"

    def test_product_pattern_meta_valid(self):
        meta_path = PATTERNS_DIR / "products" / "messaging" / "ibm-mq" / "pattern.meta.yaml"
        with open(meta_path) as f:
            data = yaml.safe_load(f)
        pattern = data["pattern"]
        assert pattern["id"] == "ibm-mq"
        assert pattern["type"] == "product"
        assert pattern["version"] == "1.0.0"
        assert "provides" in pattern
        assert "requires" in pattern
        assert "binding_points" in pattern

    def test_product_pattern_system_yaml_valid(self):
        system_path = PATTERNS_DIR / "products" / "messaging" / "ibm-mq" / "system.yaml"
        with open(system_path) as f:
            data = yaml.safe_load(f)
        assert "metadata" in data
        assert "contexts" in data
        assert "containers" in data
        assert "components" in data
        assert "component_relationships" in data

    def test_product_pattern_standalone_validation(self):
        """Product pattern validates independently via validate-patterns.py."""
        pattern_dir = PATTERNS_DIR / "products" / "messaging" / "ibm-mq"
        result = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "validate-patterns.py"), str(pattern_dir)],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"Validation failed: {result.stdout}"
        data = json.loads(result.stdout)
        assert data["valid"] is True, f"Pattern invalid: {data['errors']}"

    def test_product_pattern_system_validates_with_validate_py(self):
        """Product system.yaml validates with the main validate.py tool."""
        from validate import validate
        system_path = str(PATTERNS_DIR / "products" / "messaging" / "ibm-mq" / "system.yaml")
        result = validate(system_path)
        assert result["valid"] is True, f"system.yaml validation failed: {result['errors']}"


class TestPatternSchemas:
    """New schemas for pattern metadata and deployment manifests."""

    def test_pattern_meta_schema_exists(self):
        assert (SCHEMAS_DIR / "pattern-meta.schema.json").exists()

    def test_pattern_meta_schema_valid_json(self):
        with open(SCHEMAS_DIR / "pattern-meta.schema.json") as f:
            data = json.load(f)
        assert "$schema" in data
        assert data["properties"]["pattern"]["required"] == ["id", "type", "name", "version", "description"]

    def test_manifest_schema_exists(self):
        assert (SCHEMAS_DIR / "manifest.schema.json").exists()

    def test_manifest_schema_valid_json(self):
        with open(SCHEMAS_DIR / "manifest.schema.json") as f:
            data = json.load(f)
        assert "$schema" in data
        assert "manifest" in data["properties"]

    def test_pattern_meta_validates_with_jsonschema(self):
        from jsonschema import Draft202012Validator
        with open(SCHEMAS_DIR / "pattern-meta.schema.json") as f:
            schema = json.load(f)
        Draft202012Validator.check_schema(schema)

    def test_manifest_validates_with_jsonschema(self):
        from jsonschema import Draft202012Validator
        with open(SCHEMAS_DIR / "manifest.schema.json") as f:
            schema = json.load(f)
        Draft202012Validator.check_schema(schema)


class TestComposeTool:
    """tools/compose.py produces correct composed output."""

    @pytest.fixture(autouse=True)
    def _setup_manifest(self, tmp_path):
        """Create a temporary manifest for testing."""
        self.manifest_dir = tmp_path / "test-deployment"
        self.manifest_dir.mkdir()
        manifest = {
            "manifest": {
                "id": "test-deployment",
                "name": "Test Deployment",
                "description": "Test deployment for regression testing",
                "environment": "development",
                "region": "us-east-1",
                "status": "proposed",
                "network": {
                    "pattern_ref": "standard-3tier",
                    "id_prefix": "test",
                },
                "products": [
                    {
                        "pattern_ref": "ibm-mq",
                        "id_prefix": "mq",
                    },
                ],
                "placements": [
                    {
                        "container_ref": "mq-mq-infrastructure",
                        "zone_ref": "test-private-app-tier",
                        "replicas": 2,
                        "runtime_user": "non_root",
                    },
                ],
            }
        }
        self.manifest_path = self.manifest_dir / "manifest.yaml"
        with open(self.manifest_path, "w") as f:
            yaml.dump(manifest, f)

    def test_compose_dry_run(self):
        result = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "compose.py"),
             str(self.manifest_path), "--dry-run"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"compose.py --dry-run failed: {result.stderr}"
        data = json.loads(result.stdout)
        assert data["dry_run"] is True
        assert data["networks_zones_count"] == 3
        assert data["system_containers_count"] == 1
        assert data["system_components_count"] == 2

    def test_compose_writes_files(self):
        result = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "compose.py"),
             str(self.manifest_path)],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"compose.py failed: {result.stderr}"
        # Check files were written
        assert (self.manifest_dir / "networks.yaml").exists()
        assert (self.manifest_dir / "system.yaml").exists()
        assert (self.manifest_dir / "deployment.yaml").exists()

    def test_composed_networks_has_prefixed_ids(self):
        subprocess.run(
            [sys.executable, str(TOOLS_DIR / "compose.py"),
             str(self.manifest_path)],
            capture_output=True, text=True, timeout=30,
        )
        with open(self.manifest_dir / "networks.yaml") as f:
            content = f.read()
        # Skip the header comment lines
        data = yaml.safe_load(content)
        zone_ids = {z["id"] for z in data["network_zones"]}
        assert "test-dmz" in zone_ids, f"Expected prefixed zone ID 'test-dmz', got: {zone_ids}"
        assert "test-private-app-tier" in zone_ids

    def test_composed_system_has_prefixed_ids(self):
        subprocess.run(
            [sys.executable, str(TOOLS_DIR / "compose.py"),
             str(self.manifest_path)],
            capture_output=True, text=True, timeout=30,
        )
        with open(self.manifest_dir / "system.yaml") as f:
            content = f.read()
        data = yaml.safe_load(content)
        container_ids = {c["id"] for c in data["containers"]}
        assert "mq-mq-infrastructure" in container_ids

    def test_composed_system_validates(self):
        subprocess.run(
            [sys.executable, str(TOOLS_DIR / "compose.py"),
             str(self.manifest_path)],
            capture_output=True, text=True, timeout=30,
        )
        from validate import validate
        result = validate(
            str(self.manifest_dir / "system.yaml"),
            str(self.manifest_dir / "networks.yaml"),
        )
        assert result["valid"] is True, f"Composed output failed validation: {result['errors']}"

    def test_composed_deployment_has_placements(self):
        subprocess.run(
            [sys.executable, str(TOOLS_DIR / "compose.py"),
             str(self.manifest_path)],
            capture_output=True, text=True, timeout=30,
        )
        with open(self.manifest_dir / "deployment.yaml") as f:
            content = f.read()
        data = yaml.safe_load(content)
        assert "deployment_metadata" in data
        assert data["deployment_metadata"]["id"] == "test-deployment"
        assert "zone_placements" in data
        assert len(data["zone_placements"]) >= 1

    def test_generated_files_have_header(self):
        subprocess.run(
            [sys.executable, str(TOOLS_DIR / "compose.py"),
             str(self.manifest_path)],
            capture_output=True, text=True, timeout=30,
        )
        with open(self.manifest_dir / "system.yaml") as f:
            first_line = f.readline()
        assert first_line.startswith("# GENERATED by compose.py"), \
            "Generated files must have compose.py header"


class TestMigratePatternTool:
    """tools/migrate-pattern.py correctly converts legacy patterns."""

    def test_migrate_product_pattern(self, tmp_path):
        """Migrating a product .pattern.yaml creates directory format."""
        # Copy legacy pattern to temp
        import shutil
        src = PATTERNS_DIR / "products" / "messaging" / "ibm-mq.pattern.yaml"
        dst = tmp_path / "ibm-mq.pattern.yaml"
        shutil.copy2(src, dst)

        result = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "migrate-pattern.py"), str(dst)],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"migrate-pattern.py failed: {result.stderr}"
        data = json.loads(result.stdout)
        assert data["valid"] is True

        # Check output
        out_dir = tmp_path / "ibm-mq"
        assert out_dir.exists()
        assert (out_dir / "pattern.meta.yaml").exists()
        assert (out_dir / "system.yaml").exists()

    def test_migrate_network_pattern(self, tmp_path):
        """Migrating a network .pattern.yaml creates directory format."""
        import shutil
        src = PATTERNS_DIR / "networks" / "usa" / "standard-3tier.pattern.yaml"
        dst = tmp_path / "standard-3tier.pattern.yaml"
        shutil.copy2(src, dst)

        result = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "migrate-pattern.py"), str(dst)],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"migrate-pattern.py failed: {result.stderr}"
        data = json.loads(result.stdout)
        assert data["valid"] is True

        out_dir = tmp_path / "standard-3tier"
        assert out_dir.exists()
        assert (out_dir / "pattern.meta.yaml").exists()
        assert (out_dir / "networks.yaml").exists()


class TestCatalogDirectoryReferences:
    """Catalog files reference both legacy files and new directory patterns."""

    def test_networks_catalog_references_dir(self):
        with open(PATTERNS_DIR / "networks" / "_catalog.yaml") as f:
            data = yaml.safe_load(f)
        # Walk tree to find standard-3tier
        found = False
        def walk(nodes):
            nonlocal found
            for node in nodes:
                for pat in node.get("patterns", []):
                    if pat.get("id") == "standard-3tier":
                        assert "dir" in pat, "standard-3tier should have 'dir' reference"
                        found = True
                walk(node.get("children", []))
        walk(data["catalog"]["tree"])
        assert found, "standard-3tier not found in networks catalog"

    def test_products_catalog_references_dir(self):
        with open(PATTERNS_DIR / "products" / "_catalog.yaml") as f:
            data = yaml.safe_load(f)
        found = False
        for node in data["catalog"]["tree"]:
            for pat in node.get("patterns", []):
                if pat.get("id") == "ibm-mq":
                    assert "dir" in pat, "ibm-mq should have 'dir' reference"
                    found = True
        assert found, "ibm-mq not found in products catalog"

    def test_deployments_catalog_exists(self):
        assert DEPLOYMENTS_DIR.exists(), "deployments/ directory must exist"
        assert (DEPLOYMENTS_DIR / "_catalog.yaml").exists(), "deployments/_catalog.yaml must exist"


class TestCopilotInstructionsPatternDocs:
    """Copilot instructions document the new pattern system."""

    def test_has_pattern_system_section(self):
        content = COPILOT_INSTRUCTIONS_PATH.read_text()
        assert "## Pattern System" in content

    def test_has_manifest_reference(self):
        content = COPILOT_INSTRUCTIONS_PATH.read_text()
        assert "manifest.yaml" in content

    def test_has_compose_command(self):
        content = COPILOT_INSTRUCTIONS_PATH.read_text()
        assert "tools/compose.py" in content

    def test_has_new_schemas_listed(self):
        content = COPILOT_INSTRUCTIONS_PATH.read_text()
        assert "pattern-meta.schema.json" in content
        assert "manifest.schema.json" in content


# ============================================================================
# L9 — PATTERN CONTEXT HIERARCHY
# ============================================================================

class TestContextSchema:
    """Context schema exists and is valid JSON Schema."""

    def test_context_schema_exists(self):
        assert (SCHEMAS_DIR / "context.schema.json").exists()

    def test_context_schema_valid_json(self):
        with open(SCHEMAS_DIR / "context.schema.json") as f:
            schema = json.load(f)
        assert schema["title"] == "Doc2ArchAgent Pattern Context Schema"
        assert "contexts" in schema["properties"]

    def test_context_schema_validates_with_jsonschema(self):
        jsonschema = pytest.importorskip("jsonschema")
        with open(SCHEMAS_DIR / "context.schema.json") as f:
            schema = json.load(f)
        jsonschema.Draft202012Validator.check_schema(schema)

    def test_doc_inventory_schema_exists(self):
        assert (SCHEMAS_DIR / "doc-inventory.schema.json").exists()

    def test_doc_inventory_schema_valid_json(self):
        with open(SCHEMAS_DIR / "doc-inventory.schema.json") as f:
            schema = json.load(f)
        assert "documents" in schema["properties"]
        assert "pattern_ref" in schema["properties"]

    def test_doc_inventory_schema_validates_with_jsonschema(self):
        jsonschema = pytest.importorskip("jsonschema")
        with open(SCHEMAS_DIR / "doc-inventory.schema.json") as f:
            schema = json.load(f)
        jsonschema.Draft202012Validator.check_schema(schema)


class TestPatternContextHierarchy:
    """Each pattern has a contexts/ subdirectory with _context.yaml, sources/, and provenance."""

    # --- Product pattern ---

    def test_product_contexts_dir_exists(self):
        ctx_dir = PATTERNS_DIR / "products" / "messaging" / "ibm-mq" / "contexts"
        assert ctx_dir.is_dir(), "ibm-mq/contexts/ must exist"

    def test_product_context_yaml_exists(self):
        path = PATTERNS_DIR / "products" / "messaging" / "ibm-mq" / "contexts" / "_context.yaml"
        assert path.exists(), "ibm-mq/contexts/_context.yaml must exist"

    def test_product_context_yaml_valid(self):
        path = PATTERNS_DIR / "products" / "messaging" / "ibm-mq" / "contexts" / "_context.yaml"
        with open(path) as f:
            data = yaml.safe_load(f)
        assert "contexts" in data
        assert len(data["contexts"]) >= 1
        for ctx in data["contexts"]:
            assert "id" in ctx
            assert "name" in ctx
            assert "description" in ctx
            assert "internal" in ctx

    def test_product_context_ids_kebab_case(self):
        path = PATTERNS_DIR / "products" / "messaging" / "ibm-mq" / "contexts" / "_context.yaml"
        with open(path) as f:
            data = yaml.safe_load(f)
        kebab = re.compile(r'^[a-z][a-z0-9]*(-[a-z0-9]+)*$')
        for ctx in data["contexts"]:
            assert kebab.match(ctx["id"]), f"Context id '{ctx['id']}' is not kebab-case"

    def test_product_sources_dir_exists(self):
        path = PATTERNS_DIR / "products" / "messaging" / "ibm-mq" / "contexts" / "sources"
        assert path.is_dir(), "ibm-mq/contexts/sources/ must exist"

    def test_product_doc_inventory_exists(self):
        path = PATTERNS_DIR / "products" / "messaging" / "ibm-mq" / "contexts" / "sources" / "doc-inventory.yaml"
        assert path.exists()

    def test_product_doc_inventory_valid(self):
        path = PATTERNS_DIR / "products" / "messaging" / "ibm-mq" / "contexts" / "sources" / "doc-inventory.yaml"
        with open(path) as f:
            data = yaml.safe_load(f)
        assert data["pattern_ref"] == "ibm-mq"
        assert data["pattern_type"] == "product"

    def test_product_provenance_exists(self):
        path = PATTERNS_DIR / "products" / "messaging" / "ibm-mq" / "contexts" / "provenance.yaml"
        assert path.exists()

    def test_product_provenance_valid(self):
        path = PATTERNS_DIR / "products" / "messaging" / "ibm-mq" / "contexts" / "provenance.yaml"
        with open(path) as f:
            data = yaml.safe_load(f)
        assert "extraction_date" in data
        assert "entities" in data

    def test_product_meta_has_contexts_flag(self):
        path = PATTERNS_DIR / "products" / "messaging" / "ibm-mq" / "pattern.meta.yaml"
        with open(path) as f:
            data = yaml.safe_load(f)
        assert data["pattern"]["has_contexts"] is True

    # --- Network pattern ---

    def test_network_contexts_dir_exists(self):
        ctx_dir = PATTERNS_DIR / "networks" / "usa" / "standard-3tier" / "contexts"
        assert ctx_dir.is_dir(), "standard-3tier/contexts/ must exist"

    def test_network_context_yaml_exists(self):
        path = PATTERNS_DIR / "networks" / "usa" / "standard-3tier" / "contexts" / "_context.yaml"
        assert path.exists()

    def test_network_context_yaml_valid(self):
        path = PATTERNS_DIR / "networks" / "usa" / "standard-3tier" / "contexts" / "_context.yaml"
        with open(path) as f:
            data = yaml.safe_load(f)
        assert "contexts" in data
        assert len(data["contexts"]) >= 1
        for ctx in data["contexts"]:
            assert "id" in ctx
            assert "name" in ctx
            assert "internal" in ctx

    def test_network_sources_dir_exists(self):
        path = PATTERNS_DIR / "networks" / "usa" / "standard-3tier" / "contexts" / "sources"
        assert path.is_dir()

    def test_network_doc_inventory_exists(self):
        path = PATTERNS_DIR / "networks" / "usa" / "standard-3tier" / "contexts" / "sources" / "doc-inventory.yaml"
        assert path.exists()

    def test_network_doc_inventory_valid(self):
        path = PATTERNS_DIR / "networks" / "usa" / "standard-3tier" / "contexts" / "sources" / "doc-inventory.yaml"
        with open(path) as f:
            data = yaml.safe_load(f)
        assert data["pattern_ref"] == "standard-3tier"
        assert data["pattern_type"] == "network"

    def test_network_provenance_exists(self):
        path = PATTERNS_DIR / "networks" / "usa" / "standard-3tier" / "contexts" / "provenance.yaml"
        assert path.exists()

    def test_network_meta_has_contexts_flag(self):
        path = PATTERNS_DIR / "networks" / "usa" / "standard-3tier" / "pattern.meta.yaml"
        with open(path) as f:
            data = yaml.safe_load(f)
        assert data["pattern"]["has_contexts"] is True


class TestValidatePatternsContextHierarchy:
    """validate-patterns.py validates context hierarchy within patterns."""

    def test_product_pattern_validates_with_contexts(self):
        result = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "validate-patterns.py"),
             str(PATTERNS_DIR / "products" / "messaging" / "ibm-mq")],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(result.stdout)
        assert data["valid"] is True, f"Validation errors: {data['errors']}"

    def test_network_pattern_validates_with_contexts(self):
        result = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "validate-patterns.py"),
             str(PATTERNS_DIR / "networks" / "usa" / "standard-3tier")],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(result.stdout)
        assert data["valid"] is True, f"Validation errors: {data['errors']}"


class TestComposeWithContexts:
    """compose.py merges _context.yaml from patterns into composed output."""

    def test_composed_system_has_both_inline_and_dir_contexts(self, tmp_path):
        """Composed system should include contexts from both inline and _context.yaml."""
        import shutil

        # Create a temporary manifest
        deploy_dir = tmp_path / "test-deployment"
        deploy_dir.mkdir()

        manifest_data = {
            "manifest": {
                "id": "ctx-test",
                "name": "Context Test Deployment",
                "environment": "dev",
                "network": {
                    "pattern_ref": "standard-3tier",
                    "id_prefix": "net",
                },
                "products": [
                    {
                        "pattern_ref": "ibm-mq",
                        "id_prefix": "mq",
                    }
                ],
                "placements": [
                    {
                        "container_ref": "mq-mq-infrastructure",
                        "zone_ref": "net-private-app-tier",
                    }
                ],
            }
        }

        manifest_path = deploy_dir / "manifest.yaml"
        with open(manifest_path, "w") as f:
            yaml.dump(manifest_data, f)

        # Run compose
        sys.path.insert(0, str(TOOLS_DIR))
        from compose import compose
        result = compose(manifest_path)

        system = result["system"]
        context_ids = [c["id"] for c in system.get("contexts", [])]

        # Should have inline context (mq-mq-context from system.yaml)
        assert "mq-mq-context" in context_ids, f"Missing inline context. Got: {context_ids}"

        # Should also have _context.yaml contexts (prefixed)
        # mq-messaging from ibm-mq _context.yaml → mq-mq-messaging
        assert "mq-mq-messaging" in context_ids, f"Missing dir context. Got: {context_ids}"

        # Should have network context (net-datacenter-network from standard-3tier _context.yaml)
        assert "net-datacenter-network" in context_ids, f"Missing network context. Got: {context_ids}"


class TestClassifySectionsTool:
    """classify-sections.py classifies document sections by concern."""

    def test_classify_sections_compiles(self):
        py_compile.compile(str(TOOLS_DIR / "classify-sections.py"), doraise=True)

    def test_classify_network_document(self, tmp_path):
        doc = tmp_path / "network-design.md"
        doc.write_text("""# Network Topology Overview

This document describes the data center network design with VLAN segmentation.

## DMZ Zone Configuration

The DMZ zone uses VLAN 100 with subnet 10.0.1.0/24. Firewall rules allow
HTTPS ingress from the internet. The WAF inspects all incoming traffic.

## Application Tier

The private application tier uses VLAN 200 with subnet 10.0.2.0/24.
No internet routing. Egress filtered.

## Data Tier

The data tier uses VLAN 300 for database servers and persistent storage.
""")
        result = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "classify-sections.py"), str(doc)],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["total_sections"] >= 3
        # Most sections should be classified as network
        network_count = sum(1 for s in data["sections"] if s["classification"] == "network")
        assert network_count >= 2, f"Expected >= 2 network sections, got {network_count}"

    def test_classify_product_document(self, tmp_path):
        doc = tmp_path / "mq-deployment.md"
        doc.write_text("""# IBM MQ Deployment Guide

## Queue Manager Configuration

Install the queue manager on the application server. Configure the
listener on port 1414 with TLS 1.2 encryption.

## Web Console Setup

Deploy the MQ web console on port 9443. Configure LDAP authentication
for administrator access.

## Channel Configuration

Create server-connection channels for client applications. Each channel
uses certificate-based authentication.
""")
        result = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "classify-sections.py"), str(doc)],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["total_sections"] >= 3
        product_count = sum(1 for s in data["sections"] if s["classification"] == "product")
        assert product_count >= 2, f"Expected >= 2 product sections, got {product_count}"

    def test_classify_mixed_document(self, tmp_path):
        doc = tmp_path / "mixed-guide.md"
        doc.write_text("""# Vendor Deployment Guide

## Network Requirements

Configure the DMZ zone with a WAF and load balancer. The firewall must
allow traffic on VLAN 100 from the internet. Subnet 10.0.1.0/24.

## Application Installation

Install the queue manager component on the application server.
Configure the listener endpoint on port 1414.

## Security Configuration

Enable TLS 1.2 on all listeners. Configure certificate authentication
using the organization's PKI infrastructure.
""")
        result = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "classify-sections.py"), str(doc)],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        classifications = {s["classification"] for s in data["sections"]}
        # Mixed doc should have at least 2 different classifications
        assert len(classifications) >= 2, \
            f"Mixed doc should have multiple classifications, got: {classifications}"

    def test_classify_split_output(self, tmp_path):
        doc = tmp_path / "vendor-guide.md"
        doc.write_text("""# Vendor Guide

## Network Design

The DMZ zone with VLAN and subnet configuration for firewall rules.

## Product Setup

Install the application server component and configure the queue manager.
""")
        output_dir = tmp_path / "split"
        result = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "classify-sections.py"),
             str(doc), "--output-dir", str(output_dir)],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "files_written" in data
        assert len(data["files_written"]) >= 1


class TestMigratePatternWithContexts:
    """migrate-pattern.py creates contexts/ hierarchy during migration."""

    def test_migrate_product_creates_contexts(self, tmp_path):
        import shutil
        src = PATTERNS_DIR / "products" / "messaging" / "ibm-mq.pattern.yaml"
        dst = tmp_path / "ibm-mq.pattern.yaml"
        shutil.copy2(src, dst)

        result = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "migrate-pattern.py"), str(dst)],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["valid"] is True

        out_dir = tmp_path / "ibm-mq"
        assert (out_dir / "contexts" / "_context.yaml").exists()
        assert (out_dir / "contexts" / "sources" / "doc-inventory.yaml").exists()
        assert (out_dir / "contexts" / "provenance.yaml").exists()

        # Validate _context.yaml content
        with open(out_dir / "contexts" / "_context.yaml") as f:
            ctx_data = yaml.safe_load(f)
        assert "contexts" in ctx_data
        assert len(ctx_data["contexts"]) >= 1

    def test_migrate_network_creates_contexts(self, tmp_path):
        import shutil
        src = PATTERNS_DIR / "networks" / "usa" / "standard-3tier.pattern.yaml"
        dst = tmp_path / "standard-3tier.pattern.yaml"
        shutil.copy2(src, dst)

        result = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "migrate-pattern.py"), str(dst)],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["valid"] is True

        out_dir = tmp_path / "standard-3tier"
        assert (out_dir / "contexts" / "_context.yaml").exists()
        assert (out_dir / "contexts" / "sources" / "doc-inventory.yaml").exists()
        assert (out_dir / "contexts" / "provenance.yaml").exists()

        with open(out_dir / "contexts" / "_context.yaml") as f:
            ctx_data = yaml.safe_load(f)
        assert ctx_data["contexts"][0]["id"] == "standard-3tier-network"


class TestDocAgentPatternAwareness:
    """Doc agents include pattern-type selection and context routing."""

    def test_doc_collector_has_pattern_type_selection(self):
        content = (AGENTS_DIR / "doc-collector.agent.md").read_text()
        assert "PATTERN-TYPE SELECTION" in content
        assert "Network pattern" in content
        assert "Product pattern" in content
        assert "Mixed" in content

    def test_doc_collector_references_classify_tool(self):
        content = (AGENTS_DIR / "doc-collector.agent.md").read_text()
        assert "classify-sections.py" in content

    def test_doc_collector_references_pattern_sources(self):
        content = (AGENTS_DIR / "doc-collector.agent.md").read_text()
        assert "contexts/sources" in content

    def test_doc_collector_references_doc_inventory_yaml(self):
        content = (AGENTS_DIR / "doc-collector.agent.md").read_text()
        assert "doc-inventory.yaml" in content

    def test_doc_extractor_has_pattern_aware_extraction(self):
        content = (AGENTS_DIR / "doc-extractor.agent.md").read_text()
        assert "PATTERN-AWARE EXTRACTION" in content

    def test_doc_extractor_references_context_yaml(self):
        content = (AGENTS_DIR / "doc-extractor.agent.md").read_text()
        assert "_context.yaml" in content

    def test_doc_extractor_references_provenance_yaml(self):
        content = (AGENTS_DIR / "doc-extractor.agent.md").read_text()
        assert "provenance.yaml" in content

    def test_doc_extractor_context_separation_rule(self):
        content = (AGENTS_DIR / "doc-extractor.agent.md").read_text()
        assert "Context Separation Rule" in content


# ============================================================================
# L10 — DIAGRAM HIERARCHY: Deployment-scoped diagram storage
# ============================================================================

class TestDiagramIndexSchema:
    """Diagram index schema exists and is valid."""

    def test_diagram_index_schema_exists(self):
        assert (SCHEMAS_DIR / "diagram-index.schema.json").exists()

    def test_diagram_index_schema_valid_json(self):
        with open(SCHEMAS_DIR / "diagram-index.schema.json") as f:
            schema = json.load(f)
        assert schema["title"] == "Doc2ArchAgent Diagram Index Schema"
        assert "scope_type" in schema["properties"]
        assert "scope_id" in schema["properties"]
        assert "diagrams" in schema["properties"]
        assert "custom_diagrams" in schema["properties"]

    def test_diagram_index_schema_validates_with_jsonschema(self):
        jsonschema = pytest.importorskip("jsonschema")
        with open(SCHEMAS_DIR / "diagram-index.schema.json") as f:
            schema = json.load(f)
        jsonschema.Draft202012Validator.check_schema(schema)

    def test_diagram_index_schema_scope_type_enum(self):
        with open(SCHEMAS_DIR / "diagram-index.schema.json") as f:
            schema = json.load(f)
        assert set(schema["properties"]["scope_type"]["enum"]) == {"deployment", "pattern"}

    def test_diagram_index_schema_level_enum(self):
        with open(SCHEMAS_DIR / "diagram-index.schema.json") as f:
            schema = json.load(f)
        level_enum = schema["properties"]["diagrams"]["items"]["properties"]["level"]["enum"]
        assert "context" in level_enum
        assert "containers" in level_enum
        assert "deployment" in level_enum

    def test_diagram_index_schema_format_keys(self):
        with open(SCHEMAS_DIR / "diagram-index.schema.json") as f:
            schema = json.load(f)
        fmt_props = schema["properties"]["diagrams"]["items"]["properties"]["formats"]["properties"]
        assert "mermaid" in fmt_props
        assert "plantuml" in fmt_props
        assert "drawio" in fmt_props
        assert "structurizr" in fmt_props
        assert "d2" in fmt_props


class TestPatternDiagramDirectories:
    """Pattern directories have diagrams/ with _index.yaml stubs."""

    def test_product_pattern_diagrams_dir_exists(self):
        path = PATTERNS_DIR / "products" / "messaging" / "ibm-mq" / "diagrams"
        assert path.is_dir(), "ibm-mq/diagrams/ must exist"

    def test_product_pattern_index_exists(self):
        path = PATTERNS_DIR / "products" / "messaging" / "ibm-mq" / "diagrams" / "_index.yaml"
        assert path.exists(), "ibm-mq/diagrams/_index.yaml must exist"

    def test_product_pattern_index_valid(self):
        path = PATTERNS_DIR / "products" / "messaging" / "ibm-mq" / "diagrams" / "_index.yaml"
        with open(path) as f:
            data = yaml.safe_load(f)
        assert data["scope_type"] == "pattern"
        assert data["scope_id"] == "ibm-mq"
        assert isinstance(data["diagrams"], list)

    def test_product_pattern_index_conforms_to_schema(self):
        jsonschema = pytest.importorskip("jsonschema")
        with open(SCHEMAS_DIR / "diagram-index.schema.json") as f:
            schema = json.load(f)
        path = PATTERNS_DIR / "products" / "messaging" / "ibm-mq" / "diagrams" / "_index.yaml"
        with open(path) as f:
            data = yaml.safe_load(f)
        jsonschema.validate(instance=data, schema=schema,
                            cls=jsonschema.Draft202012Validator)

    def test_network_pattern_diagrams_dir_exists(self):
        path = PATTERNS_DIR / "networks" / "usa" / "standard-3tier" / "diagrams"
        assert path.is_dir(), "standard-3tier/diagrams/ must exist"

    def test_network_pattern_index_exists(self):
        path = PATTERNS_DIR / "networks" / "usa" / "standard-3tier" / "diagrams" / "_index.yaml"
        assert path.exists()

    def test_network_pattern_index_valid(self):
        path = PATTERNS_DIR / "networks" / "usa" / "standard-3tier" / "diagrams" / "_index.yaml"
        with open(path) as f:
            data = yaml.safe_load(f)
        assert data["scope_type"] == "pattern"
        assert data["scope_id"] == "standard-3tier"
        assert isinstance(data["diagrams"], list)

    def test_network_pattern_index_conforms_to_schema(self):
        jsonschema = pytest.importorskip("jsonschema")
        with open(SCHEMAS_DIR / "diagram-index.schema.json") as f:
            schema = json.load(f)
        path = PATTERNS_DIR / "networks" / "usa" / "standard-3tier" / "diagrams" / "_index.yaml"
        with open(path) as f:
            data = yaml.safe_load(f)
        jsonschema.validate(instance=data, schema=schema,
                            cls=jsonschema.Draft202012Validator)


class TestComposeDiagramsDirectory:
    """compose.py creates diagrams/ directory with _index.yaml stub."""

    @pytest.fixture(autouse=True)
    def _setup_manifest(self, tmp_path):
        self.manifest_dir = tmp_path / "test-deployment"
        self.manifest_dir.mkdir()
        manifest = {
            "manifest": {
                "id": "test-deployment",
                "name": "Test Deployment",
                "description": "Test deployment for diagram hierarchy testing",
                "environment": "development",
                "region": "us-east-1",
                "status": "proposed",
                "network": {
                    "pattern_ref": "standard-3tier",
                    "id_prefix": "test",
                },
                "products": [
                    {
                        "pattern_ref": "ibm-mq",
                        "id_prefix": "mq",
                    },
                ],
                "placements": [
                    {
                        "container_ref": "mq-mq-infrastructure",
                        "zone_ref": "test-private-app-tier",
                        "replicas": 2,
                        "runtime_user": "non_root",
                    },
                ],
            }
        }
        self.manifest_path = self.manifest_dir / "manifest.yaml"
        with open(self.manifest_path, "w") as f:
            yaml.dump(manifest, f)

    def test_compose_creates_diagrams_dir(self):
        subprocess.run(
            [sys.executable, str(TOOLS_DIR / "compose.py"),
             str(self.manifest_path)],
            capture_output=True, text=True, timeout=30,
        )
        assert (self.manifest_dir / "diagrams").is_dir(), \
            "compose.py must create diagrams/ directory"

    def test_compose_creates_custom_dir(self):
        subprocess.run(
            [sys.executable, str(TOOLS_DIR / "compose.py"),
             str(self.manifest_path)],
            capture_output=True, text=True, timeout=30,
        )
        assert (self.manifest_dir / "diagrams" / "custom").is_dir(), \
            "compose.py must create diagrams/custom/ directory"

    def test_compose_creates_index_yaml(self):
        subprocess.run(
            [sys.executable, str(TOOLS_DIR / "compose.py"),
             str(self.manifest_path)],
            capture_output=True, text=True, timeout=30,
        )
        index_path = self.manifest_dir / "diagrams" / "_index.yaml"
        assert index_path.exists(), "compose.py must create diagrams/_index.yaml"

    def test_compose_index_yaml_valid(self):
        subprocess.run(
            [sys.executable, str(TOOLS_DIR / "compose.py"),
             str(self.manifest_path)],
            capture_output=True, text=True, timeout=30,
        )
        index_path = self.manifest_dir / "diagrams" / "_index.yaml"
        with open(index_path) as f:
            data = yaml.safe_load(f)
        assert data["scope_type"] == "deployment"
        assert data["scope_id"] == "test-deployment"
        assert isinstance(data["diagrams"], list)

    def test_compose_index_conforms_to_schema(self):
        jsonschema = pytest.importorskip("jsonschema")
        subprocess.run(
            [sys.executable, str(TOOLS_DIR / "compose.py"),
             str(self.manifest_path)],
            capture_output=True, text=True, timeout=30,
        )
        with open(SCHEMAS_DIR / "diagram-index.schema.json") as f:
            schema = json.load(f)
        index_path = self.manifest_dir / "diagrams" / "_index.yaml"
        with open(index_path) as f:
            data = yaml.safe_load(f)
        jsonschema.validate(instance=data, schema=schema,
                            cls=jsonschema.Draft202012Validator)


class TestValidatePatternsHandlesDiagrams:
    """validate-patterns.py validates diagrams/ structure within patterns."""

    def test_product_pattern_validates_with_diagrams(self):
        result = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "validate-patterns.py"),
             str(PATTERNS_DIR / "products" / "messaging" / "ibm-mq")],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(result.stdout)
        assert data["valid"] is True, f"Validation errors: {data['errors']}"

    def test_network_pattern_validates_with_diagrams(self):
        result = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "validate-patterns.py"),
             str(PATTERNS_DIR / "networks" / "usa" / "standard-3tier")],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(result.stdout)
        assert data["valid"] is True, f"Validation errors: {data['errors']}"


class TestDiagramAgentDeploymentPaths:
    """Diagram agent files reference deployment-scoped paths."""

    def test_diagram_generator_has_output_modes(self):
        content = (AGENTS_DIR / "diagram-generator.agent.md").read_text()
        assert "DIAGRAM OUTPUT MODES" in content
        assert "deployments/" in content
        assert "patterns/" in content
        assert "_index.yaml" in content

    def test_mermaid_agent_references_deployment_paths(self):
        content = (AGENTS_DIR / "diagram-mermaid.agent.md").read_text()
        assert "deployments/" in content
        assert "layout-plan.yaml" in content

    def test_plantuml_agent_references_deployment_paths(self):
        content = (AGENTS_DIR / "diagram-plantuml.agent.md").read_text()
        assert "deployments/" in content

    def test_drawio_agent_references_deployment_paths(self):
        content = (AGENTS_DIR / "diagram-drawio.agent.md").read_text()
        assert "deployments/" in content

    def test_structurizr_agent_references_deployment_paths(self):
        content = (AGENTS_DIR / "diagram-structurizr.agent.md").read_text()
        assert "deployments/" in content

    def test_d2_agent_references_deployment_paths(self):
        content = (AGENTS_DIR / "diagram-d2.agent.md").read_text()
        assert "deployments/" in content

    def test_deployer_has_diagram_generation_section(self):
        content = (AGENTS_DIR / "deployer.agent.md").read_text()
        assert "DIAGRAM GENERATION" in content
        assert "@diagram-generator" in content

    def test_doc_writer_has_diagram_discovery(self):
        content = (AGENTS_DIR / "doc-writer.agent.md").read_text()
        assert "DIAGRAM DISCOVERY" in content
        assert "_index.yaml" in content


class TestDiagramNamingConvention:
    """Diagram naming convention documented in copilot-instructions."""

    def test_copilot_instructions_has_diagram_section(self):
        content = COPILOT_INSTRUCTIONS_PATH.read_text()
        assert "diagram" in content.lower()

    def test_copilot_instructions_lists_diagram_index_schema(self):
        content = COPILOT_INSTRUCTIONS_PATH.read_text()
        assert "diagram-index.schema.json" in content
