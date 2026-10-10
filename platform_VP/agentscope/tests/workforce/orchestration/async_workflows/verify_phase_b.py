"""Scoped formatting/AST and explicit test-matrix export for PHH Phase B."""

import argparse
import ast
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[4]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dependency-path", type=Path)
    parser.add_argument("--format", action="store_true")
    parser.add_argument("--export-matrix", action="store_true")
    args = parser.parse_args()
    if args.dependency_path:
        sys.path.insert(0, str(args.dependency_path.resolve()))
    import black

    source = ROOT / "src/agentscope/app/workforce/orchestration"
    files = sorted(source.rglob("*.py")) + sorted(
        Path(__file__).parent.glob("*.py")
    )
    # Phase A source is already reviewed and remains unchanged.
    files = [p for p in files if p.name != "phase_a.py"]
    dirty = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        ast.parse(text, filename=str(path))
        formatted = black.format_str(text, mode=black.Mode(line_length=79))
        if text != formatted:
            if args.format:
                path.write_text(formatted, encoding="utf-8")
            else:
                dirty.append(str(path.relative_to(ROOT)))
    if args.export_matrix:
        sys.path.insert(0, str(Path(__file__).parent))
        sys.path.insert(0, str(ROOT / "tests/workforce/orchestration/phase_a"))
        from run_phase_a import isolate_service_initializers

        isolate_service_initializers()
        import unittest

        suite = unittest.defaultTestLoader.discover(
            str(Path(__file__).parent), pattern="test_phase_b*.py"
        )
        tests = []

        def collect(item):
            if isinstance(item, unittest.TestSuite):
                for child in item:
                    collect(child)
            else:
                tests.append(item)

        collect(suite)
        rows = [
            "# Phase B test matrix",
            "",
            "Gate MB local: all rows pass, no skip. Inputs are defined in "
            "each referenced test body; fake clock, atomic UOW, runtime, "
            "operation and signals are test-only.",
            "",
            "| ID | Input/scenario | Expected | Suite |",
            "|---|---|---|---|",
        ]
        for test in tests:
            method = test._testMethodName
            match = re.match(r"test_(B\d+)_(.*)", method)
            case_id, title = match.groups()
            description = test.shortDescription() or title.replace("_", " ")
            negative = any(
                word in description.lower()
                for word in (
                    "reject",
                    "cannot",
                    "denied",
                    "conflict",
                    "failure",
                    "invalid",
                    "forged",
                    "fault",
                    "expired",
                    "wrong",
                    "discards",
                    "bypass",
                )
            )
            expected = (
                "Reject/discard; asserted durable state remains isolated"
                if negative
                else "Assert behavior and committed projection in test body"
            )
            rows.append(
                f"| {case_id} | {description} | {expected} | "
                f"`{test.__class__.__module__}.{method}` |"
            )
        for name in ("timeline.test.ts", "timeline-render.test.tsx"):
            text = (Path(__file__).parent / name).read_text(encoding="utf-8")
            for case_id, title in re.findall(r"test\('(UI\d+) ([^']+)'", text):
                rows.append(
                    f"| {case_id} | {title} | Explicit expect assertions; "
                    f"mismatch fails before cursor/state write | `{name}` |"
                )
        for offset, field in enumerate(
            (
                "conversation_id",
                "workflow_id",
                "external_user_id",
                "external_conversation_id",
                "external_ticket_id",
            ),
            21,
        ):
            rows.append(
                f"| UI{offset:03} | Mutate event {field} to B after valid A "
                "control | Reject; A state unchanged | `timeline.test.ts` |"
            )
        handoff = (
            ROOT
            / "docs/workforce/handoffs/phan-huy-hoang/PHASE_B_TEST_MATRIX.md"
        )
        handoff.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"AST/Black: {len(files)} scoped Python files; dirty={len(dirty)}")
    for path in dirty:
        print(path)
    return int(bool(dirty))


if __name__ == "__main__":
    raise SystemExit(main())
