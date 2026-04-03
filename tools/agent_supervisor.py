#!/usr/bin/env python3
# Copyright (c) 2026 Michael J. Read. All rights reserved.
# SPDX-License-Identifier: BUSL-1.1
"""Multi-agent supervisor pattern for Doc2ArchAgent.

Orchestrates the document-to-architecture pipeline by routing tasks to
specialized agents (document classifier, schema mapper, diagram analyzer,
security analyst, validator).

This module provides the programmatic supervisor that mirrors the
GitHub Copilot agent workflow but can run standalone in CI/CD pipelines.

Usage:
    python tools/agent_supervisor.py architecture/docs/ --output architecture/
    python tools/agent_supervisor.py input.pdf --stages classify,extract,validate
"""

import argparse
import json
import sys
from enum import Enum
from pathlib import Path


class PipelineStage(str, Enum):
    """Pipeline processing stages."""
    CONVERT = "convert"           # Document format conversion
    LAYOUT = "layout"             # Layout detection and region classification
    CLASSIFY = "classify"         # Section classification by concern
    EXTRACT = "extract"           # Schema-driven entity extraction
    RESOLVE = "resolve"           # Cross-document entity resolution
    VALIDATE = "validate"         # Schema + gap analysis validation
    THREAT = "threat"             # Threat rule evaluation
    DIAGRAM = "diagram"           # Diagram generation
    CONFIDENCE = "confidence"     # Confidence scoring enrichment


# Default pipeline order
DEFAULT_PIPELINE = [
    PipelineStage.CONVERT,
    PipelineStage.LAYOUT,
    PipelineStage.CLASSIFY,
    PipelineStage.EXTRACT,
    PipelineStage.RESOLVE,
    PipelineStage.VALIDATE,
    PipelineStage.THREAT,
    PipelineStage.CONFIDENCE,
]


class StageResult:
    """Result from a single pipeline stage."""

    def __init__(self, stage: str, status: str, duration_ms: int = 0,
                 artifacts: list | None = None, summary: dict | None = None,
                 errors: list | None = None):
        self.stage = stage
        self.status = status
        self.duration_ms = duration_ms
        self.artifacts = artifacts or []
        self.summary = summary or {}
        self.errors = errors or []


class PipelineResult:
    """Result from the full pipeline run."""

    def __init__(self, stages: list, overall_status: str = "success",
                 total_duration_ms: int = 0, artifacts: list | None = None):
        self.stages = stages
        self.overall_status = overall_status
        self.total_duration_ms = total_duration_ms
        self.artifacts = artifacts or []


# ---------------------------------------------------------------------------
# Stage runners
# ---------------------------------------------------------------------------

def _run_convert(input_path: Path, output_dir: Path, **kwargs) -> StageResult:
    """Run document conversion stage."""
    import time
    start = time.monotonic()

    try:
        # Import and run convert-docs
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "convert_docs", Path(__file__).parent / "convert-docs.py"
        )
        mod = importlib.util.module_from_spec(spec)

        # Simulate CLI args
        converted_dir = output_dir / "converted"
        converted_dir.mkdir(parents=True, exist_ok=True)

        if input_path.is_dir():
            sys.argv = ["convert-docs.py", str(input_path), str(converted_dir)]
        else:
            # Single file: create temp input dir
            import shutil
            tmp_input = output_dir / "_tmp_input"
            tmp_input.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(input_path), str(tmp_input / input_path.name))
            sys.argv = ["convert-docs.py", str(tmp_input), str(converted_dir)]

        spec.loader.exec_module(mod)

        elapsed = int((time.monotonic() - start) * 1000)

        report_path = converted_dir / "conversion-report.json"
        summary = {}
        if report_path.exists():
            report = json.loads(report_path.read_text())
            summary = report.get("summary", {})

        return StageResult(
            stage=PipelineStage.CONVERT,
            status="success",
            duration_ms=elapsed,
            artifacts=[str(converted_dir)],
            summary=summary,
        )
    except SystemExit:
        elapsed = int((time.monotonic() - start) * 1000)
        return StageResult(
            stage=PipelineStage.CONVERT,
            status="success",
            duration_ms=elapsed,
            artifacts=[str(output_dir / "converted")],
        )
    except Exception as e:
        elapsed = int((time.monotonic() - start) * 1000)
        return StageResult(
            stage=PipelineStage.CONVERT,
            status="error",
            duration_ms=elapsed,
            errors=[str(e)],
        )


def _run_layout(input_path: Path, output_dir: Path, **kwargs) -> StageResult:
    """Run layout detection stage."""
    import time
    start = time.monotonic()

    try:
        from tools.layout_analyzer import analyze_document
        analysis = analyze_document(input_path)

        elapsed = int((time.monotonic() - start) * 1000)
        return StageResult(
            stage=PipelineStage.LAYOUT,
            status="success",
            duration_ms=elapsed,
            summary={
                "method": analysis.extraction_method,
                "pages": analysis.metadata.get("total_pages", 0),
                "regions": analysis.metadata.get("total_regions", 0),
                "tables": analysis.metadata.get("total_tables", 0),
            },
        )
    except Exception as e:
        elapsed = int((time.monotonic() - start) * 1000)
        return StageResult(
            stage=PipelineStage.LAYOUT,
            status="skipped",
            duration_ms=elapsed,
            errors=[f"Layout detection unavailable: {e}"],
        )


def _run_classify(input_path: Path, output_dir: Path, **kwargs) -> StageResult:
    """Run section classification stage."""
    import time
    start = time.monotonic()

    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "classify_sections", Path(__file__).parent / "classify-sections.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # Find converted text files
        converted_dir = output_dir / "converted"
        if converted_dir.is_dir():
            files = list(converted_dir.glob("*.txt")) + list(converted_dir.glob("*.md"))
        elif input_path.is_file():
            files = [input_path]
        else:
            files = []

        all_results = []
        for f in files:
            if f.name == "conversion-report.json":
                continue
            result = mod.classify_document(f)
            all_results.append(result)

        elapsed = int((time.monotonic() - start) * 1000)

        # Write classification report
        report_path = output_dir / "classification-report.json"
        report_path.write_text(json.dumps(all_results, indent=2))

        return StageResult(
            stage=PipelineStage.CLASSIFY,
            status="success",
            duration_ms=elapsed,
            artifacts=[str(report_path)],
            summary={
                "files_classified": len(all_results),
                "total_sections": sum(r.get("total_sections", 0) for r in all_results),
            },
        )
    except Exception as e:
        elapsed = int((time.monotonic() - start) * 1000)
        return StageResult(
            stage=PipelineStage.CLASSIFY,
            status="error",
            duration_ms=elapsed,
            errors=[str(e)],
        )


def _run_validate(input_path: Path, output_dir: Path, **kwargs) -> StageResult:
    """Run validation stage."""
    import time
    start = time.monotonic()

    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "validate", Path(__file__).parent / "validate.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # Find system.yaml
        system_yaml = None
        for candidate in [
            output_dir / "system.yaml",
            output_dir.parent / "system.yaml",
            input_path if input_path.suffix in (".yaml", ".yml") else None,
        ]:
            if candidate and candidate.exists():
                system_yaml = candidate
                break

        if not system_yaml:
            return StageResult(
                stage=PipelineStage.VALIDATE,
                status="skipped",
                duration_ms=int((time.monotonic() - start) * 1000),
                errors=["No system.yaml found to validate"],
            )

        result = mod.validate(str(system_yaml))
        elapsed = int((time.monotonic() - start) * 1000)

        return StageResult(
            stage=PipelineStage.VALIDATE,
            status="success" if result["valid"] else "error",
            duration_ms=elapsed,
            summary={
                "valid": result["valid"],
                "errors": len(result["errors"]),
                "warnings": len(result["warnings"]),
            },
            errors=[e["message"] for e in result["errors"]],
        )
    except Exception as e:
        return StageResult(
            stage=PipelineStage.VALIDATE,
            status="error",
            duration_ms=int((time.monotonic() - start) * 1000),
            errors=[str(e)],
        )


def _run_confidence(input_path: Path, output_dir: Path, **kwargs) -> StageResult:
    """Run confidence scoring enrichment."""
    import time
    start = time.monotonic()

    try:
        from tools.confidence import ConfidenceScorer
        scorer = ConfidenceScorer(default_threshold=kwargs.get("threshold", 95))

        # Find provenance.yaml
        prov_path = None
        for candidate in [
            output_dir / "provenance.yaml",
            output_dir.parent / "provenance.yaml",
        ]:
            if candidate.exists():
                prov_path = candidate
                break

        if not prov_path:
            return StageResult(
                stage=PipelineStage.CONFIDENCE,
                status="skipped",
                duration_ms=int((time.monotonic() - start) * 1000),
                errors=["No provenance.yaml found"],
            )

        import yaml
        with open(prov_path) as f:
            prov = yaml.safe_load(f) or {}

        enriched = scorer.enrich_provenance(prov)
        with open(prov_path, "w") as f:
            yaml.dump(enriched, f, default_flow_style=False, sort_keys=False)

        elapsed = int((time.monotonic() - start) * 1000)
        stats = enriched.get("statistics", {})

        return StageResult(
            stage=PipelineStage.CONFIDENCE,
            status="success",
            duration_ms=elapsed,
            artifacts=[str(prov_path)],
            summary={
                "average_confidence": stats.get("average_confidence", 0),
                "above_threshold": stats.get("fields_above_threshold", 0),
                "below_threshold": stats.get("fields_below_threshold", 0),
            },
        )
    except Exception as e:
        return StageResult(
            stage=PipelineStage.CONFIDENCE,
            status="error",
            duration_ms=int((time.monotonic() - start) * 1000),
            errors=[str(e)],
        )


def _run_threat(input_path: Path, output_dir: Path, **kwargs) -> StageResult:
    """Run threat rule evaluation stage."""
    import time
    start = time.monotonic()

    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "threat_rules", Path(__file__).parent / "threat-rules.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # Find system.yaml
        system_yaml = None
        for candidate in [
            output_dir / "system.yaml",
            output_dir.parent / "system.yaml",
            input_path if input_path.suffix in (".yaml", ".yml") else None,
        ]:
            if candidate and candidate.exists():
                system_yaml = candidate
                break

        if not system_yaml:
            return StageResult(
                stage=PipelineStage.THREAT,
                status="skipped",
                duration_ms=int((time.monotonic() - start) * 1000),
                errors=["No system.yaml found for threat analysis"],
            )

        # Find networks.yaml
        networks_yaml = None
        for candidate in [
            output_dir / "networks.yaml",
            output_dir.parent / "networks.yaml",
        ]:
            if candidate.exists():
                networks_yaml = candidate
                break

        result = mod.evaluate_threats(
            str(system_yaml),
            networks_path=str(networks_yaml) if networks_yaml else None,
            environment=kwargs.get("environment", "production"),
        )
        elapsed = int((time.monotonic() - start) * 1000)

        findings = result.get("findings", [])
        by_severity = {}
        for f in findings:
            sev = f.get("severity", "info")
            by_severity[sev] = by_severity.get(sev, 0) + 1

        return StageResult(
            stage=PipelineStage.THREAT,
            status="success" if not findings else "warning",
            duration_ms=elapsed,
            summary={
                "total_findings": len(findings),
                **by_severity,
            },
        )
    except Exception as e:
        return StageResult(
            stage=PipelineStage.THREAT,
            status="error",
            duration_ms=int((time.monotonic() - start) * 1000),
            errors=[str(e)],
        )


def _run_resolve(input_path: Path, output_dir: Path, **kwargs) -> StageResult:
    """Run cross-document entity resolution stage."""
    import time
    start = time.monotonic()

    try:
        from tools.entity_resolver import resolve_entities

        # Find provenance.yaml
        prov_path = None
        for candidate in [
            output_dir / "provenance.yaml",
            output_dir.parent / "provenance.yaml",
        ]:
            if candidate.exists():
                prov_path = candidate
                break

        if not prov_path:
            return StageResult(
                stage=PipelineStage.RESOLVE,
                status="skipped",
                duration_ms=int((time.monotonic() - start) * 1000),
                errors=["No provenance.yaml found for entity resolution"],
            )

        result = resolve_entities(prov_path)
        elapsed = int((time.monotonic() - start) * 1000)

        return StageResult(
            stage=PipelineStage.RESOLVE,
            status="success",
            duration_ms=elapsed,
            summary={
                "entities_resolved": result.get("resolved", 0),
                "conflicts": result.get("conflicts", 0),
                "merges": result.get("merges", 0),
            },
        )
    except Exception as e:
        return StageResult(
            stage=PipelineStage.RESOLVE,
            status="error",
            duration_ms=int((time.monotonic() - start) * 1000),
            errors=[str(e)],
        )


# Stage runner registry
STAGE_RUNNERS = {
    PipelineStage.CONVERT: _run_convert,
    PipelineStage.LAYOUT: _run_layout,
    PipelineStage.CLASSIFY: _run_classify,
    PipelineStage.VALIDATE: _run_validate,
    PipelineStage.CONFIDENCE: _run_confidence,
    PipelineStage.THREAT: _run_threat,
    PipelineStage.RESOLVE: _run_resolve,
    # EXTRACT, DIAGRAM — require LLM interaction, run via Copilot agents
}


# ---------------------------------------------------------------------------
# Pipeline orchestrator
# ---------------------------------------------------------------------------

def run_pipeline(
    input_path: Path,
    output_dir: Path,
    *,
    stages: list[PipelineStage] | None = None,
    stop_on_error: bool = False,
    **kwargs,
) -> PipelineResult:
    """Run the document-to-architecture pipeline.

    Args:
        input_path: Source document or directory.
        output_dir: Output directory for all artifacts.
        stages: Specific stages to run (default: all).
        stop_on_error: Stop pipeline on first error.
        **kwargs: Passed to individual stage runners.

    Returns:
        PipelineResult with per-stage results.
    """
    if stages is None:
        stages = DEFAULT_PIPELINE

    output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    total_ms = 0

    for stage in stages:
        runner = STAGE_RUNNERS.get(stage)
        if runner is None:
            results.append(StageResult(
                stage=stage,
                status="skipped",
                errors=[f"No runner registered for stage '{stage}'"],
            ))
            continue

        result = runner(input_path, output_dir, **kwargs)
        results.append(result)
        total_ms += result.duration_ms

        if result.status == "error" and stop_on_error:
            break

    # Determine overall status
    has_errors = any(r.status == "error" for r in results)
    all_skipped = all(r.status == "skipped" for r in results)

    overall = "error" if has_errors else ("skipped" if all_skipped else "success")

    # Collect all artifacts
    all_artifacts = []
    for r in results:
        all_artifacts.extend(r.artifacts)

    return PipelineResult(
        stages=results,
        overall_status=overall,
        total_duration_ms=total_ms,
        artifacts=all_artifacts,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Multi-agent pipeline supervisor for Doc2ArchAgent.",
    )
    parser.add_argument("input", type=Path,
                        help="Source document or directory")
    parser.add_argument("--output", type=Path, default=Path("./output"),
                        help="Output directory (default: ./output)")
    parser.add_argument("--stages", default=None,
                        help="Comma-separated stages to run (default: all)")
    parser.add_argument("--stop-on-error", action="store_true",
                        help="Stop pipeline on first error")
    parser.add_argument("--threshold", type=int, default=95,
                        help="Confidence threshold (0-100, default: 95)")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    parser.add_argument("--output-json", type=Path, default=None,
                        help="Write JSON results to file (for agent consumption)")
    parser.add_argument("--report", type=Path, default=None,
                        help="Write markdown summary report to file")

    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: {args.input} not found", file=sys.stderr)
        sys.exit(1)

    stages = None
    if args.stages:
        stages = [PipelineStage(s.strip()) for s in args.stages.split(",")]

    result = run_pipeline(
        args.input,
        args.output,
        stages=stages,
        stop_on_error=args.stop_on_error,
        threshold=args.threshold,
    )

    if args.format == "json":
        output = {
            "overall_status": result.overall_status,
            "total_duration_ms": result.total_duration_ms,
            "artifacts": result.artifacts,
            "stages": [
                {
                    "stage": s.stage,
                    "status": s.status,
                    "duration_ms": s.duration_ms,
                    "summary": s.summary,
                    "errors": s.errors,
                    "artifacts": s.artifacts,
                }
                for s in result.stages
            ],
        }
        print(json.dumps(output, indent=2))
    else:
        status_icon = {"success": "✓", "error": "✗", "skipped": "—"}.get(
            result.overall_status, "?"
        )
        print(f"{status_icon} PIPELINE {result.overall_status.upper()} "
              f"({result.total_duration_ms}ms)")
        print(f"{'=' * 50}")

        for s in result.stages:
            icon = {"success": "✓", "error": "✗", "skipped": "—"}.get(s.status, "?")
            print(f"  {icon} {s.stage:15s} {s.status:8s} ({s.duration_ms}ms)")
            if s.summary:
                for k, v in s.summary.items():
                    print(f"    {k}: {v}")
            if s.errors:
                for e in s.errors[:3]:
                    print(f"    ⚠ {e}")

        if result.artifacts:
            print(f"\nArtifacts:")
            for a in result.artifacts:
                print(f"  → {a}")

    # Write JSON output for agent consumption
    if args.output_json:
        json_output = {
            "overall_status": result.overall_status,
            "total_duration_ms": result.total_duration_ms,
            "artifacts": result.artifacts,
            "stages": [
                {
                    "stage": s.stage,
                    "status": s.status,
                    "duration_ms": s.duration_ms,
                    "summary": s.summary,
                    "errors": s.errors,
                    "artifacts": s.artifacts,
                }
                for s in result.stages
            ],
        }
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(json_output, indent=2))

    # Write markdown report
    if args.report:
        lines = [
            f"# Pipeline Report",
            f"",
            f"**Status:** {result.overall_status.upper()}  ",
            f"**Duration:** {result.total_duration_ms}ms  ",
            f"",
            f"## Stages",
            f"",
            f"| Stage | Status | Duration | Details |",
            f"|-------|--------|----------|---------|",
        ]
        for s in result.stages:
            icon = {"success": "pass", "error": "FAIL", "skipped": "skip",
                    "warning": "warn"}.get(s.status, s.status)
            details = ", ".join(f"{k}={v}" for k, v in s.summary.items()) if s.summary else ""
            if s.errors:
                details += (" | " if details else "") + "; ".join(s.errors[:2])
            lines.append(f"| {s.stage} | {icon} | {s.duration_ms}ms | {details} |")

        if result.artifacts:
            lines.extend(["", "## Artifacts", ""])
            for a in result.artifacts:
                lines.append(f"- `{a}`")

        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text("\n".join(lines) + "\n")

    sys.exit(0 if result.overall_status == "success" else 1)


if __name__ == "__main__":
    main()
