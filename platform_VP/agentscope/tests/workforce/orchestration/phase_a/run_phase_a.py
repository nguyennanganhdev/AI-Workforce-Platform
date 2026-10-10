# -*- coding: utf-8 -*-
"""Explicit, dependency-light contract runner; no application bootstrap proof.

Normal mode uses installed agentscope. --isolated-imports loads real workforce
packages but skips service initializers in this process only.
"""

import argparse
import importlib.machinery
import json
from pathlib import Path
import sys
import types
import unittest


ROOT = Path(__file__).resolve().parents[4]
HANDOFF = ROOT / "docs/workforce/handoffs/phan-huy-hoang/phase_a"


def isolate_service_initializers() -> None:
    for name, path in (
        ("agentscope", ROOT / "src/agentscope"),
        ("agentscope.app", ROOT / "src/agentscope/app"),
    ):
        module = types.ModuleType(name)
        module.__path__ = [str(path)]
        module.__package__ = name
        module.__spec__ = importlib.machinery.ModuleSpec(
            name, loader=None, is_package=True
        )
        module.__spec__.submodule_search_locations = module.__path__
        sys.modules[name] = module
    print(
        "CONTRACT-ONLY: service initializers skipped; "
        "real workforce modules loaded."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--isolated-imports", action="store_true")
    parser.add_argument("--dependency-path", type=Path)
    parser.add_argument("--mutation-check", action="store_true")
    parser.add_argument("--shared-audit", action="store_true")
    parser.add_argument(
        "--export",
        action="store_true",
        help="explicitly regenerate review artifacts",
    )
    args = parser.parse_args()
    if args.dependency_path:
        sys.path.insert(0, str(args.dependency_path.resolve()))
    if args.isolated_imports:
        isolate_service_initializers()
    from jsonschema import FormatChecker

    checker = FormatChecker()
    if checker.conforms("2026-10-10T09:00:00", "date-time"):
        parser.error(
            "RFC3339 checker unavailable: install rfc3339-validator; "
            "refusing to silently skip date-time validation"
        )
    if args.shared_audit:
        from shared_boundary_audit import audit_shared_boundaries

        report = audit_shared_boundaries()
        (HANDOFF / "shared-boundary-audit.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(report, indent=2))
        return int(any(item["status"] == "OPEN" for item in report))
    if args.mutation_check:
        from mutation_checks import run_mutation_checks

        report = run_mutation_checks()
        (HANDOFF / "mutation-results.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(report, indent=2))
        return int(bool(report["survivors"]))
    if args.export:
        from agentscope.app.workforce.orchestration.phase_a import (
            phase_a_schema_bundle,
        )
        from fixtures import phase_a_samples
        from test_phase_a import NEGATIVE_CASES

        HANDOFF.mkdir(parents=True, exist_ok=True)
        for name, data in (
            ("schemas.json", phase_a_schema_bundle()),
            ("samples.json", phase_a_samples()),
        ):
            (HANDOFF / name).write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        rows = [
            "# Phase A negative test matrix",
            "",
            "Each row runs independently against the named real model. "
            "Expected: validation rejects the input.",
            "JSON Schema checks structure separately; "
            "cross-field invariants require Pydantic validation.",
            "",
            "| ID | Model | Mutation | Expected |",
            "|---|---|---|---|",
        ]
        for case in NEGATIVE_CASES:
            rows.append(
                f"| {case['id']} | {case['model']} | "
                f"{case['description']} | ValidationError |"
            )
        (HANDOFF / "TEST_MATRIX.md").write_text(
            "\n".join(rows) + "\n", encoding="utf-8"
        )
        print(f"Exported review artifacts to {HANDOFF}")
        return 0
    suite = unittest.defaultTestLoader.discover(
        str(Path(__file__).parent), pattern="test_phase_a*.py"
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.testsRun > 0 and result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
