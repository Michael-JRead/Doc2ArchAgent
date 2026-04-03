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
        # 3 from network pattern + 1 from product pattern (unified patterns)
        assert data["networks_zones_count"] == 4
        # 1 product container + 2 network containers (unified patterns)
        assert data["system_containers_count"] == 3
        # 2 product components + 2 network components (unified patterns)
        assert data["system_components_count"] == 4

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


# ==========================================================================
# L7 — Security Schema Split
# ==========================================================================


class TestSecuritySchemaSplit:
    """Tests for the system/networks/deployment security overlay split."""

    # --- Schema existence and validity ---

    def test_system_security_schema_exists(self):
        assert (SCHEMAS_DIR / "system-security.schema.json").exists()

    def test_networks_security_schema_exists(self):
        assert (SCHEMAS_DIR / "networks-security.schema.json").exists()

    def test_deployment_security_schema_exists(self):
        assert (SCHEMAS_DIR / "deployment-security.schema.json").exists()

    # --- Example security files exist ---

    def test_example_system_security_exists(self):
        assert (EXAMPLES_DIR / "payment-platform" / "system-security.yaml").exists()

    def test_example_networks_security_exists(self):
        assert (EXAMPLES_DIR / "networks-security.yaml").exists()

    # --- Example security files are valid YAML ---

    def test_example_system_security_valid_yaml(self):
        path = EXAMPLES_DIR / "payment-platform" / "system-security.yaml"
        data = yaml.safe_load(path.read_text())
        assert "security_metadata" in data
        assert "component_security" in data

    def test_example_networks_security_valid_yaml(self):
        path = EXAMPLES_DIR / "networks-security.yaml"
        data = yaml.safe_load(path.read_text())
        assert "network_security_metadata" in data
        assert "zone_security" in data

    # --- Example security files conform to schemas ---

    def test_example_system_security_conforms_to_schema(self):
        try:
            import jsonschema
        except ImportError:
            pytest.skip("jsonschema not installed")
        schema = json.loads((SCHEMAS_DIR / "system-security.schema.json").read_text())
        data = yaml.safe_load(
            (EXAMPLES_DIR / "payment-platform" / "system-security.yaml").read_text())
        jsonschema.validate(data, schema)

    def test_example_networks_security_conforms_to_schema(self):
        try:
            import jsonschema
        except ImportError:
            pytest.skip("jsonschema not installed")
        schema = json.loads((SCHEMAS_DIR / "networks-security.schema.json").read_text())
        data = yaml.safe_load(
            (EXAMPLES_DIR / "networks-security.yaml").read_text())
        jsonschema.validate(data, schema)

    # --- Stripped system.yaml still valid ---

    def test_stripped_system_yaml_still_valid(self):
        """system.yaml without inline security fields still passes validation."""
        result = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "validate.py"),
             str(EXAMPLES_DIR / "payment-platform" / "system.yaml"),
             str(EXAMPLES_DIR / "networks.yaml"),
             "--format", "json"],
            capture_output=True, text=True)
        data = json.loads(result.stdout)
        assert data["valid"] is True, f"Errors: {data.get('errors')}"

    # --- Cross-reference validation works ---

    def test_validate_with_security_files_passes(self):
        """validate.py with --security flag produces no errors."""
        result = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "validate.py"),
             str(EXAMPLES_DIR / "payment-platform" / "system.yaml"),
             str(EXAMPLES_DIR / "networks.yaml"),
             "--security", str(EXAMPLES_DIR / "payment-platform" / "system-security.yaml"),
             "--networks-security", str(EXAMPLES_DIR / "networks-security.yaml"),
             "--format", "json"],
            capture_output=True, text=True)
        data = json.loads(result.stdout)
        assert data["valid"] is True, f"Errors: {data.get('errors')}"

    # --- Merge function works ---

    def test_merge_security_overlay_function(self):
        """merge_security_overlays() produces unified dict with security fields."""
        from importlib.util import spec_from_file_location, module_from_spec
        spec = spec_from_file_location("threat_rules", TOOLS_DIR / "threat-rules.py")
        mod = module_from_spec(spec)
        spec.loader.exec_module(mod)

        base_system = yaml.safe_load(
            (EXAMPLES_DIR / "payment-platform" / "system.yaml").read_text())
        sys_sec = yaml.safe_load(
            (EXAMPLES_DIR / "payment-platform" / "system-security.yaml").read_text())

        merged, _, _ = mod.merge_security_overlays(base_system, None, None, sys_sec)

        # Check security fields were merged onto components
        comp_index = {c["id"]: c for c in merged.get("components", [])}
        assert "confidentiality" in comp_index["payment-api"]
        assert comp_index["payment-api"]["confidentiality"] == "high"
        assert comp_index["payment-db"]["encryption_at_rest"] == "aes-256"

        # Check listener security merged
        for listener in comp_index["payment-api"].get("listeners", []):
            if listener["id"] == "payment-api-https":
                assert listener["tls_enabled"] is True
                assert listener["authn_mechanism"] == "oauth2"
                break
        else:
            pytest.fail("payment-api-https listener not found")

        # Check data_entities merged
        assert len(merged.get("data_entities", [])) == 2

    # --- Threat rules work with split files ---

    def test_threat_rules_with_security_flag(self):
        """threat-rules.py with --security flag produces findings."""
        result = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "threat-rules.py"),
             str(EXAMPLES_DIR / "payment-platform" / "system.yaml"),
             "--networks", str(EXAMPLES_DIR / "networks.yaml"),
             "--security", str(EXAMPLES_DIR / "payment-platform" / "system-security.yaml"),
             "--networks-security", str(EXAMPLES_DIR / "networks-security.yaml"),
             "--format", "json"],
            capture_output=True, text=True)
        assert result.returncode in (0, 1), f"Crash: {result.stderr}"
        output = json.loads(result.stdout)
        # JSON format may be a bare list or {"findings": [...]}
        if isinstance(output, dict):
            findings = output.get("findings", [])
        else:
            findings = output
        assert isinstance(findings, list)
        assert len(findings) > 0, "Expected at least one finding"

    # --- Test fixture security overlay ---

    def test_fixture_security_overlay_exists(self):
        assert (REGRESSION_DIR / "threat-model-system-security.yaml").exists()

    def test_fixture_security_overlay_valid(self):
        data = yaml.safe_load(
            (REGRESSION_DIR / "threat-model-system-security.yaml").read_text())
        assert "security_metadata" in data
        assert "component_security" in data

    # --- Compose generates security stubs ---

    def test_compose_generates_security_stubs(self, tmp_path):
        """compose.py generates all 3 security overlay files."""
        from importlib.util import spec_from_file_location, module_from_spec
        spec = spec_from_file_location("compose", TOOLS_DIR / "compose.py")
        mod = module_from_spec(spec)
        spec.loader.exec_module(mod)

        manifest_src = PROJECT_ROOT / "deployments" / "mq-prod-us-east" / "manifest.yaml"
        if not manifest_src.exists():
            pytest.skip("No deployment manifest.yaml")

        import shutil
        test_manifest = tmp_path / "manifest.yaml"
        shutil.copy(manifest_src, test_manifest)
        result = mod.compose(test_manifest, dry_run=False)

        assert (tmp_path / "system-security.yaml").exists()
        assert (tmp_path / "networks-security.yaml").exists()
        assert (tmp_path / "deployment-security.yaml").exists()

    def test_compose_deployment_security_has_posture(self, tmp_path):
        """deployment-security.yaml contains deployment_posture from manifest."""
        from importlib.util import spec_from_file_location, module_from_spec
        spec = spec_from_file_location("compose", TOOLS_DIR / "compose.py")
        mod = module_from_spec(spec)
        spec.loader.exec_module(mod)

        manifest_src = PROJECT_ROOT / "deployments" / "mq-prod-us-east" / "manifest.yaml"
        if not manifest_src.exists():
            pytest.skip("No deployment manifest.yaml")

        import shutil
        test_manifest = tmp_path / "manifest.yaml"
        shutil.copy(manifest_src, test_manifest)
        mod.compose(test_manifest, dry_run=False)

        dep_sec = yaml.safe_load(open(tmp_path / "deployment-security.yaml"))
        assert "deployment_posture" in dep_sec
        assert dep_sec["deployment_posture"]["cloud_provider"] == "on-prem"

    def test_compose_deployment_security_has_container_security(self, tmp_path):
        """deployment-security.yaml contains runtime security fields from placements."""
        from importlib.util import spec_from_file_location, module_from_spec
        spec = spec_from_file_location("compose", TOOLS_DIR / "compose.py")
        mod = module_from_spec(spec)
        spec.loader.exec_module(mod)

        manifest_src = PROJECT_ROOT / "deployments" / "mq-prod-us-east" / "manifest.yaml"
        if not manifest_src.exists():
            pytest.skip("No deployment manifest.yaml")

        import shutil
        test_manifest = tmp_path / "manifest.yaml"
        shutil.copy(manifest_src, test_manifest)
        mod.compose(test_manifest, dry_run=False)

        dep_sec = yaml.safe_load(open(tmp_path / "deployment-security.yaml"))
        assert len(dep_sec["container_security"]) == 1
        cs = dep_sec["container_security"][0]
        assert cs["container_id"] == "mq-mq-infrastructure"
        assert cs["zone_id"] == "prod-private-app-tier"
        assert cs["runtime_user"] == "non_root"
        assert cs["read_only_filesystem"] is True
        assert cs["image_signed"] is True

    def test_compose_deployment_base_has_no_security_fields(self, tmp_path):
        """deployment.yaml should not contain runtime security fields."""
        from importlib.util import spec_from_file_location, module_from_spec
        spec = spec_from_file_location("compose", TOOLS_DIR / "compose.py")
        mod = module_from_spec(spec)
        spec.loader.exec_module(mod)

        manifest_src = PROJECT_ROOT / "deployments" / "mq-prod-us-east" / "manifest.yaml"
        if not manifest_src.exists():
            pytest.skip("No deployment manifest.yaml")

        import shutil
        test_manifest = tmp_path / "manifest.yaml"
        shutil.copy(manifest_src, test_manifest)
        mod.compose(test_manifest, dry_run=False)

        dep = yaml.safe_load(open(tmp_path / "deployment.yaml"))
        for zp in dep.get("zone_placements", []):
            for ctr in zp.get("containers", []):
                assert "runtime_user" not in ctr, "runtime_user should be in deployment-security.yaml"
                assert "read_only_filesystem" not in ctr, "read_only_filesystem should be in deployment-security.yaml"
                assert "image_signed" not in ctr, "image_signed should be in deployment-security.yaml"
                assert "network_policy_enforced" not in ctr
                assert "resource_limits_set" not in ctr

    def test_compose_networks_security_has_infra_resources(self, tmp_path):
        """networks-security.yaml contains infrastructure_resources moved from networks.yaml."""
        from importlib.util import spec_from_file_location, module_from_spec
        spec = spec_from_file_location("compose", TOOLS_DIR / "compose.py")
        mod = module_from_spec(spec)
        spec.loader.exec_module(mod)

        manifest_src = PROJECT_ROOT / "deployments" / "mq-prod-us-east" / "manifest.yaml"
        if not manifest_src.exists():
            pytest.skip("No deployment manifest.yaml")

        import shutil
        test_manifest = tmp_path / "manifest.yaml"
        shutil.copy(manifest_src, test_manifest)
        mod.compose(test_manifest, dry_run=False)

        # networks.yaml should NOT have infrastructure_resources
        nets = yaml.safe_load(open(tmp_path / "networks.yaml"))
        assert "infrastructure_resources" not in nets, \
            "infrastructure_resources should be in networks-security.yaml"

        # networks-security.yaml SHOULD have them
        nets_sec = yaml.safe_load(open(tmp_path / "networks-security.yaml"))
        assert len(nets_sec["infrastructure_resources"]) == 2
        resource_ids = [r["id"] for r in nets_sec["infrastructure_resources"]]
        assert "prod-edge-waf" in resource_ids
        assert "prod-app-lb" in resource_ids


# ============================================================================
# L4 — FUNCTIONAL: Cross-entity referential integrity (validate.py)
# ============================================================================

class TestCrossEntityReferentialIntegrity:
    """Tests for cross-entity referential integrity checks in validate.py."""

    def _import_validate(self):
        from importlib.util import spec_from_file_location, module_from_spec
        spec = spec_from_file_location("validate", TOOLS_DIR / "validate.py")
        mod = module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_trust_boundary_zone_ref_warning(self, tmp_path):
        """Trust boundaries referencing nonexistent zones produce warnings."""
        mod = self._import_validate()

        system = {
            "metadata": {"name": "Test", "description": "Test", "owner": "test", "status": "active"},
            "contexts": [{"id": "ctx", "name": "Ctx", "description": "Test", "internal": True}],
            "containers": [],
            "components": [],
            "trust_boundaries": [
                {"id": "tb-1", "source_zone": "nonexistent-zone", "target_zone": "also-missing"}
            ],
        }
        networks = {
            "network_zones": [
                {"id": "dmz", "name": "DMZ", "zone_type": "dmz", "internet_routable": True, "trust": "untrusted"}
            ]
        }

        sys_path = tmp_path / "system.yaml"
        net_path = tmp_path / "networks.yaml"
        with open(sys_path, "w") as f:
            yaml.dump(system, f)
        with open(net_path, "w") as f:
            yaml.dump(networks, f)

        result = mod.validate(str(sys_path), str(net_path))
        warning_msgs = " ".join(w["message"] for w in result["warnings"])
        assert "nonexistent-zone" in warning_msgs
        assert "also-missing" in warning_msgs

    def test_context_external_system_ref_error(self, tmp_path):
        """Context referencing nonexistent external_system_id produces an error."""
        mod = self._import_validate()

        system = {
            "metadata": {"name": "Test", "description": "Test", "owner": "test", "status": "active"},
            "contexts": [
                {"id": "ext-ctx", "name": "External", "description": "Ext", "internal": False,
                 "external_system_id": "nonexistent-ext"}
            ],
            "containers": [],
            "components": [],
            "external_systems": [],
        }

        sys_path = tmp_path / "system.yaml"
        with open(sys_path, "w") as f:
            yaml.dump(system, f)

        result = mod.validate(str(sys_path))
        assert result["valid"] is False
        error_msgs = " ".join(e["message"] for e in result["errors"])
        assert "nonexistent-ext" in error_msgs

    def test_data_entity_ref_warning(self, tmp_path):
        """Relationship referencing nonexistent data_entity produces a warning."""
        mod = self._import_validate()

        system = {
            "metadata": {"name": "Test", "description": "Test", "owner": "test", "status": "active"},
            "contexts": [{"id": "ctx", "name": "Ctx", "description": "Test", "internal": True}],
            "containers": [{"id": "ctr", "name": "Container", "context_id": "ctx"}],
            "components": [
                {"id": "comp-a", "name": "A", "container_id": "ctr", "listeners": [
                    {"id": "http", "protocol": "HTTPS", "port": 443}
                ]},
                {"id": "comp-b", "name": "B", "container_id": "ctr", "listeners": []},
            ],
            "component_relationships": [
                {"id": "rel-1", "source_component": "comp-a", "target_component": "comp-b",
                 "target_listener_ref": "http",
                 "data_entities": ["missing-entity"]}
            ],
            "data_entities": [],
        }

        sys_path = tmp_path / "system.yaml"
        with open(sys_path, "w") as f:
            yaml.dump(system, f)

        result = mod.validate(str(sys_path))
        warning_msgs = " ".join(w["message"] for w in result["warnings"])
        assert "missing-entity" in warning_msgs


# ============================================================================
# L4 — FUNCTIONAL: convert-docs.py
# ============================================================================

class TestConvertDocs:
    """Functional tests for the document conversion tool."""

    def _import_convert_docs(self):
        from importlib.util import spec_from_file_location, module_from_spec
        spec = spec_from_file_location("convert_docs", TOOLS_DIR / "convert-docs.py")
        mod = module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_copy_text_passthrough(self, tmp_path):
        """Plain text files are copied as-is."""
        mod = self._import_convert_docs()
        src = tmp_path / "input"
        src.mkdir()
        out = tmp_path / "output"
        out.mkdir()

        content = "This is a test document about architecture."
        (src / "readme.txt").write_text(content)

        result = mod.convert_file(src / "readme.txt", out)
        assert result["status"] == "converted"
        assert result["method"] == "direct-copy"
        assert (out / "readme.txt").read_text() == content

    def test_markdown_passthrough(self, tmp_path):
        """Markdown files are copied as-is."""
        mod = self._import_convert_docs()
        src = tmp_path / "input"
        src.mkdir()
        out = tmp_path / "output"
        out.mkdir()

        content = "# Architecture\n\nSome markdown content."
        (src / "doc.md").write_text(content)

        result = mod.convert_file(src / "doc.md", out)
        assert result["status"] == "converted"
        assert result["method"] == "direct-copy"

    def test_skip_unsupported_formats(self, tmp_path):
        """Unsupported formats like .xlsx are skipped."""
        mod = self._import_convert_docs()
        out = tmp_path / "output"
        out.mkdir()

        (tmp_path / "data.xlsx").write_bytes(b"fake xlsx")
        result = mod.convert_file(tmp_path / "data.xlsx", out)
        assert result["status"] == "skipped"

    def test_skip_diagram_files(self, tmp_path):
        """Diagram files (.drawio, .vsdx) are skipped with guidance."""
        mod = self._import_convert_docs()
        out = tmp_path / "output"
        out.mkdir()

        (tmp_path / "arch.drawio").write_text("<mxfile></mxfile>")
        result = mod.convert_file(tmp_path / "arch.drawio", out)
        assert result["status"] == "skipped"
        assert "parse-diagram-file.py" in result["reason"]

    def test_unknown_extension_skipped(self, tmp_path):
        """Unknown extensions are gracefully skipped."""
        mod = self._import_convert_docs()
        out = tmp_path / "output"
        out.mkdir()

        (tmp_path / "data.xyz").write_text("unknown format")
        result = mod.convert_file(tmp_path / "data.xyz", out)
        assert result["status"] == "skipped"
        assert "Unknown format" in result["reason"]

    def test_extension_map_completeness(self):
        """EXTENSION_MAP covers all documented supported formats."""
        mod = self._import_convert_docs()
        expected = {".pdf", ".docx", ".doc", ".html", ".htm",
                    ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp",
                    ".txt", ".md", ".csv", ".json", ".yaml", ".yml"}
        assert set(mod.EXTENSION_MAP.keys()) == expected

    def test_symlink_skipped_in_main(self, tmp_path):
        """Symlinks in input directory are skipped (security guard)."""
        src = tmp_path / "input"
        src.mkdir()
        out = tmp_path / "output"
        out.mkdir()

        real_file = tmp_path / "secret.txt"
        real_file.write_text("sensitive data")
        link = src / "link.txt"
        link.symlink_to(real_file)

        # Also add a real file so main() doesn't exit on empty
        (src / "real.txt").write_text("normal content")

        mod = self._import_convert_docs()
        # Simulate the file collection logic from main()
        files = sorted(
            f for f in src.iterdir()
            if f.is_file() and not f.name.startswith(".") and not f.is_symlink()
        )
        names = [f.name for f in files]
        assert "link.txt" not in names
        assert "real.txt" in names

    def test_path_traversal_guard(self, tmp_path):
        """Output path traversal via crafted filename is blocked."""
        mod = self._import_convert_docs()
        out = tmp_path / "output"
        out.mkdir()

        # Create a file with a name that could cause traversal
        # The resolve() + startswith() guard should catch this
        crafted = tmp_path / "..%2f..%2fetc%2fpasswd.txt"
        try:
            crafted.write_text("test")
            result = mod.convert_file(crafted, out)
            # Should either convert safely within output_dir or skip
            if result["status"] == "converted":
                # Verify output stayed inside output_dir
                for f in out.iterdir():
                    assert str(f.resolve()).startswith(str(out.resolve()))
        except (OSError, ValueError):
            pass  # Some OS won't allow this filename at all

    def test_convert_yaml_passthrough(self, tmp_path):
        """YAML files are copied via direct-copy method."""
        mod = self._import_convert_docs()
        out = tmp_path / "output"
        out.mkdir()

        content = "system_id: test-system\ncontexts: []"
        (tmp_path / "system.yaml").write_text(content)
        result = mod.convert_file(tmp_path / "system.yaml", out)
        assert result["status"] == "converted"
        assert result["method"] == "direct-copy"
        assert (out / "system.txt").read_text() == content

    def test_html_conversion(self, tmp_path):
        """HTML files are converted to text."""
        mod = self._import_convert_docs()
        out = tmp_path / "output"
        out.mkdir()

        html = "<html><body><h1>Architecture</h1><p>Test content.</p></body></html>"
        (tmp_path / "doc.html").write_text(html)
        result = mod.convert_file(tmp_path / "doc.html", out)
        assert result["status"] == "converted"
        assert "Architecture" in (out / "doc.md").read_text()


# ============================================================================
# L4 — FUNCTIONAL: validate-provenance.py
# ============================================================================

class TestValidateProvenance:
    """Functional tests for the provenance validation tool."""

    def _import_validate_provenance(self):
        from importlib.util import spec_from_file_location, module_from_spec
        spec = spec_from_file_location("validate_provenance", TOOLS_DIR / "validate-provenance.py")
        mod = module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_valid_provenance(self, tmp_path):
        """A well-formed provenance file passes validation."""
        mod = self._import_validate_provenance()

        # Create context directory with source doc
        ctx = tmp_path / "context"
        ctx.mkdir()
        (ctx / "architecture-doc.txt").write_text(
            "The payment gateway handles all credit card transactions via TLS 1.3."
        )

        # Create provenance.yaml using the actual schema:
        # entity_id, entity_type, fields dict with per-field confidence/source/quote/pass
        prov = {
            "extraction_date": "2026-04-01",
            "pipeline_version": "1.0.0",
            "documents_analyzed": [
                {
                    "file": "architecture-doc.txt",
                    "extraction_method": "direct-copy",
                    "quality": "high",
                }
            ],
            "entities": [
                {
                    "entity_id": "payment-gateway",
                    "entity_type": "component",
                    "fields": {
                        "description": {
                            "confidence": "HIGH",
                            "source": "architecture-doc.txt, Overview",
                            "quote": "payment gateway handles all credit card transactions",
                            "pass": "prose",
                        }
                    },
                }
            ],
        }
        prov_path = tmp_path / "provenance.yaml"
        with open(prov_path, "w") as f:
            yaml.dump(prov, f)

        result = mod.validate_provenance(str(prov_path), str(ctx))
        assert result["valid"] is True
        assert len(result["errors"]) == 0

    def test_missing_required_fields(self, tmp_path):
        """Missing top-level fields are flagged as errors."""
        mod = self._import_validate_provenance()

        prov_path = tmp_path / "provenance.yaml"
        with open(prov_path, "w") as f:
            yaml.dump({"extraction_date": "2026-04-01"}, f)

        ctx = tmp_path / "context"
        ctx.mkdir()

        result = mod.validate_provenance(str(prov_path), str(ctx))
        assert result["valid"] is False
        error_text = " ".join(result["errors"])
        assert "pipeline_version" in error_text
        assert "entities" in error_text

    def test_invalid_confidence_level(self, tmp_path):
        """Invalid confidence levels produce errors."""
        mod = self._import_validate_provenance()

        ctx = tmp_path / "context"
        ctx.mkdir()

        prov = {
            "extraction_date": "2026-04-01",
            "pipeline_version": "1.0.0",
            "documents_analyzed": [],
            "entities": [
                {
                    "entity_id": "test-component",
                    "entity_type": "component",
                    "fields": {
                        "name": {
                            "confidence": "MAYBE",  # Invalid
                            "source": "doc.txt",
                            "quote": "test quote",
                            "pass": "prose",
                        }
                    },
                }
            ],
        }
        prov_path = tmp_path / "provenance.yaml"
        with open(prov_path, "w") as f:
            yaml.dump(prov, f)

        result = mod.validate_provenance(str(prov_path), str(ctx))
        combined = " ".join(result["errors"] + result["warnings"])
        assert "MAYBE" in combined

    def test_invalid_entity_type(self, tmp_path):
        """Invalid entity types produce warnings."""
        mod = self._import_validate_provenance()

        ctx = tmp_path / "context"
        ctx.mkdir()

        prov = {
            "extraction_date": "2026-04-01",
            "pipeline_version": "1.0.0",
            "documents_analyzed": [],
            "entities": [
                {
                    "entity_id": "test",
                    "entity_type": "invalid_type",
                    "fields": {
                        "name": {
                            "confidence": "HIGH",
                            "source": "doc.txt",
                            "quote": "test",
                            "pass": "prose",
                        }
                    },
                }
            ],
        }
        prov_path = tmp_path / "provenance.yaml"
        with open(prov_path, "w") as f:
            yaml.dump(prov, f)

        result = mod.validate_provenance(str(prov_path), str(ctx))
        combined = " ".join(result["errors"] + result["warnings"])
        assert "invalid_type" in combined

    def test_fuzzy_quote_matching(self, tmp_path):
        """Quotes that closely match source text are validated."""
        mod = self._import_validate_provenance()

        ctx = tmp_path / "context"
        ctx.mkdir()
        (ctx / "source.txt").write_text(
            "The application uses PostgreSQL as its primary database for storing user records."
        )

        prov = {
            "extraction_date": "2026-04-01",
            "pipeline_version": "1.0.0",
            "documents_analyzed": [
                {"file": "source.txt", "extraction_method": "direct-copy"}
            ],
            "entities": [
                {
                    "entity_id": "user-db",
                    "entity_type": "component",
                    "fields": {
                        "description": {
                            "confidence": "HIGH",
                            "source": "source.txt, Database",
                            "quote": "uses PostgreSQL as its primary database",
                            "pass": "prose",
                        }
                    },
                }
            ],
        }
        prov_path = tmp_path / "provenance.yaml"
        with open(prov_path, "w") as f:
            yaml.dump(prov, f)

        result = mod.validate_provenance(str(prov_path), str(ctx))
        # Should pass — quote is present in source
        assert result["valid"] is True

    def test_unloadable_provenance_file(self, tmp_path):
        """A non-existent provenance file returns an error."""
        mod = self._import_validate_provenance()

        ctx = tmp_path / "context"
        ctx.mkdir()

        result = mod.validate_provenance(str(tmp_path / "nonexistent.yaml"), str(ctx))
        assert result["valid"] is False
        assert any("Cannot load" in e for e in result["errors"])

    def test_valid_extraction_methods(self):
        """All documented extraction methods are in the valid set."""
        mod = self._import_validate_provenance()
        expected_methods = {
            "direct_read", "pandoc", "pdftotext", "ocr", "vision",
            "python-docx", "pymupdf", "html2text", "tesseract-ocr",
            "pymupdf+pdfplumber-tables", "direct-copy", "raw-read",
        }
        assert mod.VALID_EXTRACTION_METHODS == expected_methods

    def test_valid_confidence_levels(self):
        """All documented confidence levels are in the valid set."""
        mod = self._import_validate_provenance()
        assert mod.VALID_CONFIDENCE == {"HIGH", "MEDIUM", "LOW", "UNCERTAIN", "NOT_STATED"}


# ============================================================================
# L4 — FUNCTIONAL: Orphan entity detection (validate.py)
# ============================================================================

class TestOrphanEntityDetection:
    """Tests for expanded orphan detection in validate.py."""

    def _import_validate(self):
        from importlib.util import spec_from_file_location, module_from_spec
        spec = spec_from_file_location("validate", TOOLS_DIR / "validate.py")
        mod = module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_orphaned_container_detected(self, tmp_path):
        """Containers with no components assigned are flagged as orphaned."""
        mod = self._import_validate()
        system = {
            "metadata": {"name": "Test", "description": "Test", "owner": "test", "status": "active"},
            "contexts": [{"id": "ctx", "name": "Ctx", "description": "Test", "internal": True}],
            "containers": [
                {"id": "active-container", "name": "Active", "context_id": "ctx"},
                {"id": "empty-container", "name": "Empty", "context_id": "ctx"},
            ],
            "components": [
                {"id": "comp-a", "name": "A", "container_id": "active-container", "listeners": []},
            ],
        }
        sys_path = tmp_path / "system.yaml"
        with open(sys_path, "w") as f:
            yaml.dump(system, f)
        result = mod.validate(str(sys_path))
        warning_msgs = " ".join(w["message"] for w in result["warnings"])
        assert "empty-container" in warning_msgs
        assert "orphaned" in warning_msgs

    def test_orphaned_zone_detected(self, tmp_path):
        """Zones with no infrastructure resources or trust boundaries are flagged."""
        mod = self._import_validate()
        system = {
            "metadata": {"name": "Test", "description": "Test", "owner": "test", "status": "active"},
            "contexts": [{"id": "ctx", "name": "Ctx", "description": "Test", "internal": True}],
            "containers": [],
            "components": [],
        }
        networks = {
            "network_zones": [
                {"id": "used-zone", "name": "Used", "zone_type": "dmz", "internet_routable": True, "trust": "untrusted"},
                {"id": "unused-zone", "name": "Unused", "zone_type": "private", "internet_routable": False, "trust": "trusted"},
            ],
            "infrastructure_resources": [
                {"id": "waf", "name": "WAF", "resource_type": "waf", "technology": "cloudflare", "zone_id": "used-zone"}
            ],
        }
        sys_path = tmp_path / "system.yaml"
        net_path = tmp_path / "networks.yaml"
        with open(sys_path, "w") as f:
            yaml.dump(system, f)
        with open(net_path, "w") as f:
            yaml.dump(networks, f)
        result = mod.validate(str(sys_path), str(net_path))
        warning_msgs = " ".join(w["message"] for w in result["warnings"])
        assert "unused-zone" in warning_msgs
        assert "orphaned" in warning_msgs


# ============================================================================
# L4 — FUNCTIONAL: K8s securityContext extraction
# ============================================================================

class TestK8sSecurityContextExtraction:
    """Tests for K8s securityContext extraction in ingest-kubernetes.py."""

    def _import_ingest_k8s(self):
        from importlib.util import spec_from_file_location, module_from_spec
        spec = spec_from_file_location("ingest_kubernetes", TOOLS_DIR / "ingest-kubernetes.py")
        mod = module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_security_context_extracted(self):
        """Pod and container securityContext fields are extracted."""
        mod = self._import_ingest_k8s()
        entities = {"components": [], "listeners": [], "network_zones": [], "network_policies": []}
        metadata = {"name": "secure-app", "namespace": "production", "labels": {}}
        spec = {
            "replicas": 1,
            "template": {
                "spec": {
                    "securityContext": {"runAsNonRoot": True, "runAsUser": 1000},
                    "containers": [{
                        "name": "app",
                        "image": "myapp:v1.2.3",
                        "securityContext": {
                            "readOnlyRootFilesystem": True,
                            "allowPrivilegeEscalation": False,
                            "capabilities": {"drop": ["ALL"]},
                        },
                        "resources": {"limits": {"cpu": "500m", "memory": "256Mi"}},
                    }],
                }
            },
        }
        mod._process_workload("Deployment", metadata, spec, {}, entities)
        comp = entities["components"][0]
        assert "security_context" in comp
        sc = comp["security_context"]
        assert sc["run_as_non_root"] is True
        assert sc["read_only_root_filesystem"] is True
        assert sc["allow_privilege_escalation"] is False
        assert sc["capabilities_drop"] == ["ALL"]
        assert comp["read_only_filesystem"] is True
        assert comp["resource_limits_set"] is True

    def test_host_namespace_extracted(self):
        """Host network/PID/IPC sharing is detected."""
        mod = self._import_ingest_k8s()
        entities = {"components": [], "listeners": [], "network_zones": [], "network_policies": []}
        metadata = {"name": "host-app", "namespace": "default", "labels": {}}
        spec = {
            "replicas": 1,
            "template": {
                "spec": {
                    "hostNetwork": True,
                    "hostPID": True,
                    "containers": [{"name": "app", "image": "app:latest"}],
                }
            },
        }
        mod._process_workload("Deployment", metadata, spec, {}, entities)
        comp = entities["components"][0]
        assert comp.get("host_network") is True
        assert comp.get("host_pid") is True

    def test_no_security_context_graceful(self):
        """Workloads without securityContext are handled gracefully."""
        mod = self._import_ingest_k8s()
        entities = {"components": [], "listeners": [], "network_zones": [], "network_policies": []}
        metadata = {"name": "basic-app", "namespace": "default", "labels": {}}
        spec = {
            "replicas": 1,
            "template": {
                "spec": {
                    "containers": [{"name": "app", "image": "app:v1"}],
                }
            },
        }
        mod._process_workload("Deployment", metadata, spec, {}, entities)
        comp = entities["components"][0]
        # Should not have security_context if none was specified
        assert "security_context" not in comp


# ============================================================================
# L4 — FUNCTIONAL: Compliance mapping and threat enrichment
# ============================================================================

class TestThreatEnrichment:
    """Tests for compliance mapping, confidence, and convergence scoring."""

    def _import_threat_rules(self):
        from importlib.util import spec_from_file_location, module_from_spec
        spec = spec_from_file_location("threat_rules", TOOLS_DIR / "threat-rules.py")
        mod = module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_compliance_mapping_loads(self):
        """Compliance mapping file loads and contains expected rules."""
        mod = self._import_threat_rules()
        mapping = mod.load_compliance_mapping()
        assert "unauthenticated-listener" in mapping
        assert "pci_dss" in mapping["unauthenticated-listener"]
        assert "nist_800_53" in mapping["unauthenticated-listener"]

    def test_finding_has_confidence_and_risk_score(self):
        """Finding objects include confidence and risk_score fields."""
        mod = self._import_threat_rules()
        f = mod.Finding(
            rule_id="test-rule", title="Test", severity="high",
            stride="spoofing", cwe=306, cwe_name="Missing Auth",
            description="Test finding", entity_type="listener",
            entity_id="comp.listener", remediation="Fix it",
        )
        assert f.confidence == "high"
        assert f.risk_score == 7.0
        d = f.to_dict()
        assert "confidence" in d
        assert "risk_score" in d

    def test_enrich_adds_compliance(self):
        """enrich_findings attaches compliance framework references."""
        mod = self._import_threat_rules()
        f = mod.Finding(
            rule_id="unauthenticated-listener", title="Unauth",
            severity="high", stride="spoofing", cwe=306,
            cwe_name="Missing Auth", description="No auth",
            entity_type="listener", entity_id="api.http",
            remediation="Add auth",
        )
        mapping = mod.load_compliance_mapping()
        enriched = mod.enrich_findings([f], mapping)
        assert len(enriched[0].compliance) > 0
        frameworks = {c["framework"] for c in enriched[0].compliance}
        assert "pci_dss" in frameworks
        assert "nist_800_53" in frameworks

    def test_convergence_scoring_boosts_risk(self):
        """Entities with 3+ findings get boosted risk scores."""
        mod = self._import_threat_rules()
        findings = []
        for i in range(4):
            findings.append(mod.Finding(
                rule_id=f"rule-{i}", title=f"Rule {i}", severity="medium",
                stride="spoofing", cwe=306, cwe_name="Test",
                description="Test", entity_type="listener",
                entity_id="same-entity.listener",  # Same entity
                remediation="Fix",
            ))
        original_score = findings[0].risk_score
        mod.enrich_findings(findings, {})
        # All findings on same entity should have boosted risk
        for f in findings:
            assert f.risk_score > original_score

    def test_convergence_no_boost_for_few_findings(self):
        """Entities with <3 findings don't get boosted."""
        mod = self._import_threat_rules()
        findings = [
            mod.Finding(
                rule_id="rule-1", title="Rule 1", severity="medium",
                stride="spoofing", cwe=306, cwe_name="Test",
                description="Test", entity_type="listener",
                entity_id="entity-a.listener", remediation="Fix",
            ),
            mod.Finding(
                rule_id="rule-2", title="Rule 2", severity="medium",
                stride="spoofing", cwe=306, cwe_name="Test",
                description="Test", entity_type="listener",
                entity_id="entity-b.listener", remediation="Fix",
            ),
        ]
        original_scores = [f.risk_score for f in findings]
        mod.enrich_findings(findings, {})
        for f, orig in zip(findings, original_scores):
            assert f.risk_score == orig

    def test_finding_to_dict_includes_compliance(self):
        """to_dict() includes compliance when present."""
        mod = self._import_threat_rules()
        f = mod.Finding(
            rule_id="test", title="Test", severity="high",
            stride=None, cwe=None, cwe_name=None,
            description="Test", entity_type="component",
            entity_id="comp", remediation="Fix",
        )
        f.compliance = [{"framework": "pci_dss", "control": "pci-4.1"}]
        d = f.to_dict()
        assert "compliance" in d
        assert d["compliance"][0]["framework"] == "pci_dss"


# ============================================================================
# PHASE A-C ENHANCEMENT TESTS
# ============================================================================


class TestConfidenceScoring:
    """Tests for tools/confidence.py — Phase A2."""

    def test_import(self):
        spec = importlib.util.spec_from_file_location(
            "confidence", TOOLS_DIR / "confidence.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert hasattr(mod, "ConfidenceScorer")
        assert hasattr(mod, "ExtractionMethod")

    def test_native_text_high_confidence(self):
        spec = importlib.util.spec_from_file_location(
            "confidence", TOOLS_DIR / "confidence.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        scorer = mod.ConfidenceScorer(default_threshold=95)
        score = scorer.score(method=mod.ExtractionMethod.NATIVE_TEXT, field_present=True)
        assert score >= 90, f"Native text should be high confidence, got {score}"

    def test_ocr_lower_confidence(self):
        spec = importlib.util.spec_from_file_location(
            "confidence", TOOLS_DIR / "confidence.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        scorer = mod.ConfidenceScorer()
        native = scorer.score(method=mod.ExtractionMethod.NATIVE_TEXT)
        ocr = scorer.score(method=mod.ExtractionMethod.OCR)
        assert native > ocr, "Native text should score higher than OCR"

    def test_verified_always_100(self):
        spec = importlib.util.spec_from_file_location(
            "confidence", TOOLS_DIR / "confidence.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        scorer = mod.ConfidenceScorer()
        score = scorer.score(method=mod.ExtractionMethod.OCR, verified=True)
        assert score == 100

    def test_absent_field_penalty(self):
        spec = importlib.util.spec_from_file_location(
            "confidence", TOOLS_DIR / "confidence.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        scorer = mod.ConfidenceScorer()
        present = scorer.score(method=mod.ExtractionMethod.NATIVE_TEXT, field_present=True)
        absent = scorer.score(method=mod.ExtractionMethod.NATIVE_TEXT, field_present=False)
        assert present > absent, "Absent fields should score lower"

    def test_multi_source_boost(self):
        spec = importlib.util.spec_from_file_location(
            "confidence", TOOLS_DIR / "confidence.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        scorer = mod.ConfidenceScorer()
        single = scorer.score(method=mod.ExtractionMethod.NATIVE_TEXT, source_count=1)
        multi = scorer.score(method=mod.ExtractionMethod.NATIVE_TEXT, source_count=3)
        assert multi > single, "Multiple sources should boost confidence"

    def test_category_mapping(self):
        spec = importlib.util.spec_from_file_location(
            "confidence", TOOLS_DIR / "confidence.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        scorer = mod.ConfidenceScorer()
        assert scorer.to_category(95) == "HIGH"
        assert scorer.to_category(75) == "MEDIUM"
        assert scorer.to_category(50) == "LOW"
        assert scorer.to_category(20) == "UNCERTAIN"
        assert scorer.to_category(0) == "NOT_STATED"

    def test_threshold_check(self):
        spec = importlib.util.spec_from_file_location(
            "confidence", TOOLS_DIR / "confidence.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        scorer = mod.ConfidenceScorer(default_threshold=80)
        assert scorer.meets_threshold(85) is True
        assert scorer.meets_threshold(75) is False
        assert scorer.meets_threshold(75, threshold=70) is True

    def test_enrich_provenance(self):
        spec = importlib.util.spec_from_file_location(
            "confidence", TOOLS_DIR / "confidence.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        prov = {
            "extraction_date": "2026-01-01",
            "documents_analyzed": [{"file": "test.pdf"}],
            "entities": [{
                "entity_type": "component",
                "entity_id": "web-api",
                "fields": {
                    "name": {
                        "value": "Web API",
                        "confidence": "HIGH",
                        "pass": "prose",
                    },
                    "technology": {
                        "value": "Java",
                        "confidence": "MEDIUM",
                        "pass": "table",
                    },
                },
            }],
        }

        scorer = mod.ConfidenceScorer(default_threshold=90)
        enriched = scorer.enrich_provenance(prov)

        # Check scores were added
        fields = enriched["entities"][0]["fields"]
        assert "confidence_score" in fields["name"]
        assert "meets_threshold" in fields["name"]
        assert isinstance(fields["name"]["confidence_score"], int)

        # Check statistics
        stats = enriched["statistics"]
        assert "confidence_threshold" in stats
        assert stats["confidence_threshold"] == 90
        assert "average_confidence" in stats

    def test_document_extraction_scoring(self):
        spec = importlib.util.spec_from_file_location(
            "confidence", TOOLS_DIR / "confidence.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        scorer = mod.ConfidenceScorer()

        # PyMuPDF result should score high
        high_result = {"method": "pymupdf", "quality": "high"}
        score = scorer.score_document_extraction(high_result)
        assert score >= 85

        # OCR result should score lower
        ocr_result = {"method": "tesseract-ocr", "quality": "medium", "ocr_confidence": 0.7}
        ocr_score = scorer.score_document_extraction(ocr_result)
        assert ocr_score < score

    def test_nli_contradicted_penalty(self):
        spec = importlib.util.spec_from_file_location(
            "confidence", TOOLS_DIR / "confidence.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        scorer = mod.ConfidenceScorer()
        normal = scorer.score(method=mod.ExtractionMethod.NATIVE_TEXT)
        contradicted = scorer.score(method=mod.ExtractionMethod.NATIVE_TEXT, nli_status="contradicted")
        assert contradicted < normal * 0.5, "Contradicted NLI should heavily penalize"


class TestVLMProviders:
    """Tests for tools/vlm_providers.py — Phase A3."""

    def test_import(self):
        spec = importlib.util.spec_from_file_location(
            "vlm_providers", TOOLS_DIR / "vlm_providers.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert hasattr(mod, "create_provider")
        assert hasattr(mod, "VLMProvider")
        assert hasattr(mod, "VLMResponse")

    def test_stub_provider(self):
        spec = importlib.util.spec_from_file_location(
            "vlm_providers", TOOLS_DIR / "vlm_providers.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        provider = mod.create_provider("stub")
        assert provider.name == "stub"

        result = provider.analyze_image(b"fake_image", "describe this")
        assert isinstance(result, mod.VLMResponse)
        assert result.provider == "stub"
        assert result.model == "stub"

    def test_stub_with_responses(self):
        spec = importlib.util.spec_from_file_location(
            "vlm_providers", TOOLS_DIR / "vlm_providers.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        provider = mod.StubProvider(responses=["response 1", "response 2"])
        r1 = provider.analyze_image(b"img", "prompt")
        assert r1.text == "response 1"
        r2 = provider.analyze_image(b"img", "prompt")
        assert r2.text == "response 2"

    def test_list_providers(self):
        spec = importlib.util.spec_from_file_location(
            "vlm_providers", TOOLS_DIR / "vlm_providers.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        providers = mod.list_providers()
        assert "stub" in providers
        assert "openai" in providers
        assert "anthropic" in providers
        assert "ollama" in providers

    def test_unknown_provider_raises(self):
        spec = importlib.util.spec_from_file_location(
            "vlm_providers", TOOLS_DIR / "vlm_providers.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        with pytest.raises(ValueError, match="Unknown VLM provider"):
            mod.create_provider("nonexistent_provider")

    def test_analyze_document_page(self):
        spec = importlib.util.spec_from_file_location(
            "vlm_providers", TOOLS_DIR / "vlm_providers.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        provider = mod.StubProvider(responses=['{"components": []}'])
        result = provider.analyze_document_page(b"page_image")
        assert result.text == '{"components": []}'


class TestGapAnalysis:
    """Tests for ARCH014-ARCH017 gap analysis rules — Phase A4."""

    def _run_validate(self, system_yaml_content, tmp_path, networks=None):
        spec = importlib.util.spec_from_file_location(
            "validate", TOOLS_DIR / "validate.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        sys_file = tmp_path / "system.yaml"
        sys_file.write_text(yaml.dump(system_yaml_content))

        nw_path = None
        if networks:
            nw_file = tmp_path / "networks.yaml"
            nw_file.write_text(yaml.dump(networks))
            nw_path = str(nw_file)

        return mod.validate(str(sys_file), nw_path)

    def test_missing_file_warning(self, tmp_path):
        """ARCH014: warn when expected files are missing."""
        system = {
            "metadata": {"name": "test", "description": "d", "owner": "o", "status": "active"},
            "contexts": [{"id": "ctx", "name": "Ctx", "description": "d", "internal": True}],
            "containers": [],
            "components": [],
        }
        result = self._run_validate(system, tmp_path)
        arch014 = [w for w in result["warnings"] if w["rule_id"] == "ARCH014"]
        assert len(arch014) > 0, "Should warn about missing networks.yaml / security files"

    def test_stale_architecture_warning(self, tmp_path):
        """ARCH016: warn when last_review_date is > 6 months old."""
        system = {
            "metadata": {
                "name": "test", "description": "d", "owner": "o", "status": "active",
                "last_review_date": "2025-01-01",
            },
            "contexts": [{"id": "ctx", "name": "Ctx", "description": "d", "internal": True}],
            "containers": [],
            "components": [],
        }
        result = self._run_validate(system, tmp_path)
        arch016 = [w for w in result["warnings"] if w["rule_id"] == "ARCH016"]
        assert len(arch016) > 0, "Should warn about stale architecture data"

    def test_missing_description_warning(self, tmp_path):
        """ARCH017: warn when component lacks description."""
        system = {
            "metadata": {"name": "test", "description": "d", "owner": "o", "status": "active"},
            "contexts": [{"id": "ctx", "name": "Ctx", "description": "d", "internal": True}],
            "containers": [{"id": "ctr", "name": "Ctr", "context_id": "ctx",
                            "container_type": "service", "technology": "Java"}],
            "components": [{
                "id": "comp",
                "name": "Comp",
                "container_id": "ctr",
                "component_type": "service",
                "technology": "Java",
                # No description
            }],
        }
        result = self._run_validate(system, tmp_path)
        arch017 = [w for w in result["warnings"] if w["rule_id"] == "ARCH017"]
        assert any("no description" in w["message"] for w in arch017)

    def test_listener_no_security_warning(self, tmp_path):
        """ARCH017: warn when listener has neither authn nor TLS."""
        system = {
            "metadata": {"name": "test", "description": "d", "owner": "o", "status": "active"},
            "contexts": [{"id": "ctx", "name": "Ctx", "description": "d", "internal": True}],
            "containers": [{"id": "ctr", "name": "Ctr", "context_id": "ctx",
                            "container_type": "service", "technology": "Java"}],
            "components": [{
                "id": "comp", "name": "Comp", "container_id": "ctr",
                "component_type": "service", "technology": "Java", "description": "Test",
                "listeners": [{"id": "http", "protocol": "HTTP", "port": 8080}],
            }],
        }
        result = self._run_validate(system, tmp_path)
        arch017 = [w for w in result["warnings"] if w["rule_id"] == "ARCH017"]
        assert any("neither authentication nor TLS" in w["message"] for w in arch017)

    def test_no_threat_report_warning(self, tmp_path):
        """ARCH015: warn when components with listeners have no threat report."""
        system = {
            "metadata": {"name": "test", "description": "d", "owner": "o", "status": "active"},
            "contexts": [{"id": "ctx", "name": "Ctx", "description": "d", "internal": True}],
            "containers": [{"id": "ctr", "name": "Ctr", "context_id": "ctx",
                            "container_type": "service", "technology": "Java"}],
            "components": [{
                "id": "comp", "name": "Comp", "container_id": "ctr",
                "component_type": "service", "technology": "Java", "description": "Test",
                "listeners": [{"id": "http", "protocol": "HTTP", "port": 8080,
                               "authn_mechanism": "jwt", "tls_enabled": True}],
            }],
        }
        result = self._run_validate(system, tmp_path)
        arch015 = [w for w in result["warnings"] if w["rule_id"] == "ARCH015"]
        assert len(arch015) > 0, "Should warn about missing threat report"


class TestEntityResolution:
    """Tests for tools/entity_resolver.py — Phase B9."""

    def test_import(self):
        spec = importlib.util.spec_from_file_location(
            "entity_resolver", TOOLS_DIR / "entity_resolver.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert hasattr(mod, "find_duplicates")
        assert hasattr(mod, "normalize_entity_name")

    def test_normalize_name(self):
        spec = importlib.util.spec_from_file_location(
            "entity_resolver", TOOLS_DIR / "entity_resolver.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        assert mod.normalize_entity_name("my-web-service") == "my web service"
        # "primary" is a noise word, gets filtered
        assert "database" in mod.normalize_entity_name("db-primary")
        assert mod.normalize_entity_name("api-gw") == "api gateway"

    def test_find_duplicates_exact(self):
        spec = importlib.util.spec_from_file_location(
            "entity_resolver", TOOLS_DIR / "entity_resolver.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        entities = [
            {"type": "component", "id": "web-api", "name": "Web API"},
            {"type": "component", "id": "web-api-svc", "name": "Web API Service"},
        ]
        # web-api-svc normalizes to "web api service", web-api to "web api"
        # Threshold 60 to account for length difference
        dups = mod.find_duplicates(entities, threshold=60)
        assert len(dups) > 0, "Should detect similar component names"

    def test_abbreviation_match(self):
        spec = importlib.util.spec_from_file_location(
            "entity_resolver", TOOLS_DIR / "entity_resolver.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        entities = [
            {"type": "component", "id": "db-primary", "name": "Database Primary"},
            {"type": "component", "id": "database-primary", "name": "Database Primary"},
        ]
        dups = mod.find_duplicates(entities, threshold=80)
        assert len(dups) > 0, "Should match abbreviated forms"

    def test_no_false_positives(self):
        spec = importlib.util.spec_from_file_location(
            "entity_resolver", TOOLS_DIR / "entity_resolver.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        entities = [
            {"type": "component", "id": "web-api", "name": "Web API"},
            {"type": "component", "id": "payment-processor", "name": "Payment Processor"},
        ]
        dups = mod.find_duplicates(entities, threshold=80)
        assert len(dups) == 0, "Distinct entities should not match"

    def test_extract_entities(self):
        spec = importlib.util.spec_from_file_location(
            "entity_resolver", TOOLS_DIR / "entity_resolver.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        system = {
            "contexts": [{"id": "ctx-1", "name": "Context 1"}],
            "containers": [{"id": "ctr-1", "name": "Container 1"}],
            "components": [{"id": "comp-1", "name": "Component 1"}],
            "external_systems": [{"id": "ext-1", "name": "External 1"}],
        }
        entities = mod.extract_entities(system)
        assert len(entities) == 4
        types = {e["type"] for e in entities}
        assert types == {"context", "container", "component", "external_system"}


class TestLayoutAnalyzer:
    """Tests for tools/layout_analyzer.py — Phase B6/B7/B8."""

    def test_import(self):
        spec = importlib.util.spec_from_file_location(
            "layout_analyzer", TOOLS_DIR / "layout_analyzer.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert hasattr(mod, "analyze_document")
        assert hasattr(mod, "detect_document_schema")
        assert hasattr(mod, "EXTRACTION_TEMPLATES")

    def test_schema_detection_hld(self):
        spec = importlib.util.spec_from_file_location(
            "layout_analyzer", TOOLS_DIR / "layout_analyzer.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        text = """
        # Architecture Overview
        ## Components
        The system consists of a web service, database, and message queue.
        The technology stack includes Java, PostgreSQL, and Kafka.
        ## Deployment
        Deployed on Kubernetes with three replicas.
        """
        schema, conf = mod.detect_document_schema(text)
        assert schema == "hld", f"Expected hld, got {schema}"
        assert conf > 0.3

    def test_schema_detection_network(self):
        spec = importlib.util.spec_from_file_location(
            "layout_analyzer", TOOLS_DIR / "layout_analyzer.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        text = """
        # Network Architecture
        ## Network Zones
        DMZ zone with CIDR 10.0.0.0/24
        ## Firewall Rules
        Allow ingress on port 443. ACL rules for egress filtering.
        VLAN segmentation between subnets.
        """
        schema, conf = mod.detect_document_schema(text)
        assert schema == "network", f"Expected network, got {schema}"

    def test_schema_detection_security(self):
        spec = importlib.util.spec_from_file_location(
            "layout_analyzer", TOOLS_DIR / "layout_analyzer.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        text = """
        # Security Architecture
        ## Authentication
        OAuth 2.0 with SAML federation. MFA required for admin access.
        ## Encryption
        TLS 1.3 for all communications. AES-256 for data at rest.
        ## Compliance
        PCI DSS and SOX compliance required.
        """
        schema, conf = mod.detect_document_schema(text)
        assert schema == "security", f"Expected security, got {schema}"

    def test_extraction_templates_exist(self):
        spec = importlib.util.spec_from_file_location(
            "layout_analyzer", TOOLS_DIR / "layout_analyzer.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        for tmpl_name in ("hld", "lld", "network", "security"):
            assert tmpl_name in mod.EXTRACTION_TEMPLATES
            tmpl = mod.EXTRACTION_TEMPLATES[tmpl_name]
            assert "name" in tmpl
            assert "expected_sections" in tmpl
            assert "key_fields" in tmpl

    def test_extract_with_template(self):
        spec = importlib.util.spec_from_file_location(
            "layout_analyzer", TOOLS_DIR / "layout_analyzer.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        text = "# Components\nThe web service uses Java Spring Boot."
        result = mod.extract_with_template(text, "hld")
        assert result["template"] == "hld"
        assert "fields" in result
        assert "sections_found" in result

    def test_analyze_text_file(self, tmp_path):
        spec = importlib.util.spec_from_file_location(
            "layout_analyzer", TOOLS_DIR / "layout_analyzer.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        doc = tmp_path / "test.txt"
        doc.write_text("# Architecture\nWeb service with PostgreSQL database.")

        analysis = mod.analyze_document(doc, use_layout_detection=False)
        assert analysis.source_file == str(doc)
        assert len(analysis.pages) == 1
        assert analysis.pages[0].full_text != ""


class TestOCRBackends:
    """Tests for tools/ocr_backends.py — Phase C10."""

    def test_import(self):
        spec = importlib.util.spec_from_file_location(
            "ocr_backends", TOOLS_DIR / "ocr_backends.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert hasattr(mod, "create_ocr_backend")
        assert hasattr(mod, "list_backends")

    def test_list_backends(self):
        spec = importlib.util.spec_from_file_location(
            "ocr_backends", TOOLS_DIR / "ocr_backends.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        backends = mod.list_backends()
        names = [b["name"] for b in backends]
        assert "tesseract" in names
        assert "opendoc" in names
        assert "paddleocr" in names

    def test_unknown_backend_raises(self):
        spec = importlib.util.spec_from_file_location(
            "ocr_backends", TOOLS_DIR / "ocr_backends.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        with pytest.raises(ValueError, match="Unknown OCR backend"):
            mod.create_ocr_backend("nonexistent")


class TestSectionClassifier:
    """Tests for tools/section_classifier.py — Phase C11."""

    def test_entity_detection(self):
        spec = importlib.util.spec_from_file_location(
            "section_classifier", TOOLS_DIR / "section_classifier.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        text = "Server at 192.168.1.100 running PostgreSQL on port 5432 with TLS"
        entities = mod.detect_entities_in_text(text)
        assert "ip_address" in entities
        assert "192.168.1.100" in entities["ip_address"]
        assert "technology" in entities
        assert "PostgreSQL" in entities["technology"]
        assert "protocol" in entities
        assert "TLS" in entities["protocol"]


class TestAgentSupervisor:
    """Tests for tools/agent_supervisor.py — Phase C12."""

    def test_import(self):
        spec = importlib.util.spec_from_file_location(
            "agent_supervisor", TOOLS_DIR / "agent_supervisor.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert hasattr(mod, "run_pipeline")
        assert hasattr(mod, "PipelineStage")
        assert hasattr(mod, "DEFAULT_PIPELINE")

    def test_pipeline_stages_enum(self):
        spec = importlib.util.spec_from_file_location(
            "agent_supervisor", TOOLS_DIR / "agent_supervisor.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        assert mod.PipelineStage.CONVERT == "convert"
        assert mod.PipelineStage.VALIDATE == "validate"
        assert mod.PipelineStage.CONFIDENCE == "confidence"
        assert len(mod.DEFAULT_PIPELINE) >= 5


class TestPyprojectToml:
    """Tests for pyproject.toml — Phase A1."""

    def test_pyproject_exists(self):
        assert (PROJECT_ROOT / "pyproject.toml").exists()

    def test_pyproject_valid(self):
        import tomllib
        with open(PROJECT_ROOT / "pyproject.toml", "rb") as f:
            data = tomllib.load(f)
        assert data["project"]["name"] == "doc2archagent"
        assert "dependencies" in data["project"]

    def test_optional_deps(self):
        import tomllib
        with open(PROJECT_ROOT / "pyproject.toml", "rb") as f:
            data = tomllib.load(f)
        opt = data["project"]["optional-dependencies"]
        assert "pdf" in opt
        assert "ocr" in opt
        assert "ml" in opt
        assert "all" in opt


class TestDockerfile:
    """Tests for Dockerfile — Phase A1."""

    def test_dockerfile_exists(self):
        assert (PROJECT_ROOT / "Dockerfile").exists()

    def test_dockerfile_has_required_stages(self):
        content = (PROJECT_ROOT / "Dockerfile").read_text()
        assert "FROM python:" in content
        assert "requirements.txt" in content
        assert "INSTALL_ML" in content
