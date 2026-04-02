#!/usr/bin/env python3
# Copyright (c) 2026 Michael J. Read. All rights reserved.
# SPDX-License-Identifier: BUSL-1.1
"""Tests for tools/validate.py — architecture YAML validation."""

import json
from pathlib import Path

import pytest

from validate import validate, format_json, format_table, format_sarif

FIXTURES = Path(__file__).parent / "fixtures"


# --- Valid file tests ---

class TestValidFiles:
    """Valid YAML files should pass validation with zero errors."""

    def test_minimal_system(self):
        result = validate(str(FIXTURES / "valid" / "minimal-system.yaml"))
        assert result["valid"] is True
        assert result["errors"] == []

    def test_full_system(self):
        result = validate(str(FIXTURES / "valid" / "full-system.yaml"))
        assert result["valid"] is True
        assert result["errors"] == []

    def test_full_system_with_networks(self):
        result = validate(
            str(FIXTURES / "valid" / "full-system.yaml"),
            str(FIXTURES / "valid" / "minimal-networks.yaml"),
        )
        assert result["valid"] is True
        assert result["errors"] == []

    def test_example_system(self):
        """Validate the examples/ reference files."""
        examples = Path(__file__).parent.parent / "examples"
        system = examples / "payment-platform" / "system.yaml"
        networks = examples / "networks.yaml"
        if system.exists():
            result = validate(str(system), str(networks) if networks.exists() else None)
            assert result["valid"] is True
            assert result["errors"] == []


# --- Invalid file tests ---

class TestMissingFields:
    """Missing required fields should produce errors."""

    def test_missing_metadata_fields(self):
        result = validate(str(FIXTURES / "invalid" / "missing-metadata-fields.yaml"))
        assert result["valid"] is False
        messages = [e["message"] for e in result["errors"]]
        assert any("metadata.owner" in m for m in messages)
        assert any("metadata.status" in m for m in messages)


class TestReferentialIntegrity:
    """Broken references should produce errors."""

    def test_broken_references(self):
        result = validate(str(FIXTURES / "invalid" / "broken-reference.yaml"))
        assert result["valid"] is False
        messages = [e["message"] for e in result["errors"]]
        assert any("nonexistent-context" in m for m in messages)
        assert any("nonexistent-container" in m for m in messages)
        assert any("nonexistent-source" in m for m in messages)

    def test_broken_ref_rule_ids(self):
        result = validate(str(FIXTURES / "invalid" / "broken-reference.yaml"))
        rule_ids = {e["rule_id"] for e in result["errors"]}
        assert "ARCH002" in rule_ids


class TestEnumValidation:
    """Invalid enum values should produce errors."""

    def test_invalid_status(self):
        result = validate(str(FIXTURES / "invalid" / "invalid-enum-values.yaml"))
        assert result["valid"] is False
        messages = [e["message"] for e in result["errors"]]
        assert any("banana" in m for m in messages)

    def test_invalid_enum_rule_id(self):
        result = validate(str(FIXTURES / "invalid" / "invalid-enum-values.yaml"))
        rule_ids = {e["rule_id"] for e in result["errors"]}
        assert "ARCH004" in rule_ids


class TestDuplicateIds:
    """Duplicate IDs should produce errors."""

    def test_duplicate_context_ids(self):
        result = validate(str(FIXTURES / "invalid" / "duplicate-ids.yaml"))
        assert result["valid"] is False
        messages = [e["message"] for e in result["errors"]]
        assert any("Duplicate" in m and "my-context" in m for m in messages)

    def test_duplicate_id_rule_id(self):
        result = validate(str(FIXTURES / "invalid" / "duplicate-ids.yaml"))
        rule_ids = {e["rule_id"] for e in result["errors"]}
        assert "ARCH003" in rule_ids


class TestPortValidation:
    """Invalid ports should produce errors."""

    def test_port_out_of_range(self):
        result = validate(str(FIXTURES / "invalid" / "bad-port.yaml"))
        assert result["valid"] is False
        messages = [e["message"] for e in result["errors"]]
        assert any("70000" in m for m in messages)
        assert any("0" in m or "outside valid range" in m for m in messages)

    def test_port_error_rule_id(self):
        result = validate(str(FIXTURES / "invalid" / "bad-port.yaml"))
        rule_ids = {e["rule_id"] for e in result["errors"]}
        assert "ARCH009" in rule_ids


class TestNamingConventions:
    """Non-kebab-case IDs should produce warnings."""

    def test_non_kebab_case_warnings(self):
        result = validate(str(FIXTURES / "invalid" / "non-kebab-case.yaml"))
        # Non-kebab-case is a warning, not an error
        assert result["valid"] is True
        messages = [w["message"] for w in result["warnings"]]
        assert any("MyContext" in m for m in messages)
        assert any("my_context" in m for m in messages)

    def test_kebab_case_rule_id(self):
        result = validate(str(FIXTURES / "invalid" / "non-kebab-case.yaml"))
        rule_ids = {w["rule_id"] for w in result["warnings"]}
        assert "ARCH005" in rule_ids


# --- Output format tests ---

class TestSecurityOverlayValidation:
    """Tests for system-security.yaml cross-reference validation."""

    def test_valid_security_cross_references(self):
        """Valid security file should produce no ARCH012 errors."""
        examples = Path(__file__).parent.parent / "examples"
        result = validate(
            str(examples / "payment-platform" / "system.yaml"),
            str(examples / "networks.yaml"),
            security_path=str(examples / "payment-platform" / "system-security.yaml"),
            networks_security_path=str(examples / "networks-security.yaml"),
        )
        arch012_errors = [e for e in result["errors"] if e.get("rule_id") == "ARCH012"]
        assert arch012_errors == [], f"Unexpected ARCH012 errors: {arch012_errors}"

    def test_invalid_component_id_detected(self, tmp_path):
        """Security file with non-existent component_id should produce ARCH012."""
        system = tmp_path / "system.yaml"
        system.write_text("metadata:\n  name: test\n  description: t\n  owner: t\n  status: active\n"
                          "components:\n  - id: real-comp\n    name: Real\n    container_id: c\n"
                          "    component_type: api\n    technology: X\n")
        sec = tmp_path / "system-security.yaml"
        sec.write_text("security_metadata:\n  system_ref: test\n"
                       "component_security:\n  - component_id: fake-comp\n    confidentiality: high\n")
        result = validate(str(system), security_path=str(sec))
        arch012 = [e for e in result["errors"] if e.get("rule_id") == "ARCH012"]
        assert len(arch012) == 1
        assert "fake-comp" in arch012[0]["message"]

    def test_missing_security_annotation_warning(self, tmp_path):
        """Components without security annotation should produce ARCH013 warning."""
        system = tmp_path / "system.yaml"
        system.write_text("metadata:\n  name: test\n  description: t\n  owner: t\n  status: active\n"
                          "components:\n  - id: comp-a\n    name: A\n    container_id: c\n"
                          "    component_type: api\n    technology: X\n"
                          "  - id: comp-b\n    name: B\n    container_id: c\n"
                          "    component_type: api\n    technology: X\n")
        sec = tmp_path / "system-security.yaml"
        sec.write_text("security_metadata:\n  system_ref: test\n"
                       "component_security:\n  - component_id: comp-a\n    confidentiality: high\n")
        result = validate(str(system), security_path=str(sec))
        arch013 = [w for w in result["warnings"] if w.get("rule_id") == "ARCH013"]
        assert len(arch013) == 1
        assert "comp-b" in arch013[0]["message"]

    def test_invalid_zone_id_in_networks_security(self, tmp_path):
        """Networks security with non-existent zone_id should produce ARCH012."""
        system = tmp_path / "system.yaml"
        system.write_text("metadata:\n  name: test\n  description: t\n  owner: t\n  status: active\n")
        networks = tmp_path / "networks.yaml"
        networks.write_text("network_zones:\n  - id: real-zone\n    name: Real\n    zone_type: private\n"
                            "    internet_routable: false\n    trust: trusted\n")
        net_sec = tmp_path / "networks-security.yaml"
        net_sec.write_text("network_security_metadata:\n  networks_ref: test\n"
                           "zone_security:\n  - zone_id: fake-zone\n    segmentation_type: vpc\n")
        result = validate(str(system), str(networks),
                          networks_security_path=str(net_sec))
        arch012 = [e for e in result["errors"] if e.get("rule_id") == "ARCH012"]
        assert len(arch012) == 1
        assert "fake-zone" in arch012[0]["message"]


class TestOutputFormats:
    """Test all three output formatters."""

    def test_json_format(self):
        result = validate(str(FIXTURES / "valid" / "minimal-system.yaml"))
        output = format_json(result)
        parsed = json.loads(output)
        assert parsed["valid"] is True
        assert isinstance(parsed["errors"], list)
        assert isinstance(parsed["warnings"], list)

    def test_json_backward_compatible(self):
        """JSON output should have string messages, not dicts (backward compat)."""
        result = validate(str(FIXTURES / "invalid" / "missing-metadata-fields.yaml"))
        output = format_json(result)
        parsed = json.loads(output)
        for err in parsed["errors"]:
            assert isinstance(err, str)

    def test_table_format(self):
        result = validate(str(FIXTURES / "invalid" / "missing-metadata-fields.yaml"))
        output = format_table(result)
        assert "FAIL" in output
        assert "ARCH001" in output

    def test_table_pass(self):
        result = validate(str(FIXTURES / "valid" / "minimal-system.yaml"))
        output = format_table(result)
        assert "PASS" in output

    def test_sarif_format(self):
        result = validate(str(FIXTURES / "invalid" / "broken-reference.yaml"))
        output = format_sarif(result)
        parsed = json.loads(output)
        assert parsed["version"] == "2.1.0"
        assert len(parsed["runs"]) == 1
        assert parsed["runs"][0]["tool"]["driver"]["name"] == "Doc2ArchAgent-Validate"
        assert len(parsed["runs"][0]["results"]) > 0

    def test_sarif_empty(self):
        result = validate(str(FIXTURES / "valid" / "minimal-system.yaml"))
        output = format_sarif(result)
        parsed = json.loads(output)
        assert parsed["version"] == "2.1.0"
        assert len(parsed["runs"][0]["results"]) == 0
