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
