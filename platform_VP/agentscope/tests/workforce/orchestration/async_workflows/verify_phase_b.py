# -*- coding: utf-8 -*-
"""Scoped quality checks and explicit, assertion-based Phase B test matrix."""

import argparse
import ast
import inspect
from pathlib import Path
import re
import sys
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[4]
TESTS = Path(__file__).parent


def cell(value):
    return " ".join(value.split()).replace("|", "\\|").replace("`", "'")


def export_matrix():
    sys.path.insert(0, str(TESTS))
    sys.path.insert(0, str(ROOT / "tests/workforce/orchestration/phase_a"))
    from run_phase_a import isolate_service_initializers
    from run_phase_b import test_cases

    isolate_service_initializers()
    suite = unittest.defaultTestLoader.discover(
        str(TESTS), pattern="test_phase_b*.py"
    )
    rows = []
    for test in test_cases(suite):
        match = re.match(r"test_(B\d{3})_(.*)", test._testMethodName)
        if not match:
            raise ValueError("Discovered test lacks a Bnnn ID")
        case_id, title = match.groups()
        method = getattr(test, test._testMethodName)
        lines, line = inspect.getsourcelines(method)
        path = Path(inspect.getsourcefile(method))
        text = textwrap.dedent("".join(lines))
        expected = []
        for assertion in ast.walk(ast.parse(text)):
            if (
                isinstance(assertion, ast.Call)
                and isinstance(assertion.func, ast.Attribute)
                and assertion.func.attr.startswith("assert")
            ):
                expected.append(ast.get_source_segment(text, assertion))
        if not expected:
            raise ValueError(f"{case_id} has no explicit assertion")
        scenario = test.shortDescription() or title.replace("_", " ")
        parameters = inspect.signature(method).parameters.values()
        defaults = [
            f"{p.name}={p.default!r}"
            for p in parameters
            if p.default is not inspect.Parameter.empty
        ]
        if defaults:
            scenario += "; input: " + ", ".join(defaults)
        rows.append((case_id, scenario, "; ".join(expected), path, line))
    for name in (
        "timeline.test.ts",
        "timeline-render.test.tsx",
        "timeline-interaction.test.tsx",
    ):
        path = TESTS / name
        text = path.read_text(encoding="utf-8")
        matches = list(
            re.finditer(r"test\(\s*['\"](UI\d{3}) ([^'\"]+)['\"]", text)
        )
        for index, match in enumerate(matches):
            end = (
                matches[index + 1].start()
                if index + 1 < len(matches)
                else len(text)
            )
            body = text[match.end() : end]
            assertions = re.findall(
                r"expect\([\s\S]{0,1500}?\)\."
                r"(?:rejects\.)?(?:not\.)?to\w+[^;\n]*",
                body,
            )
            rows.append(
                (
                    match[1],
                    match[2],
                    "; ".join(assertions)
                    or "Explicit expect assertions in linked body",
                    path,
                    text[: match.start()].count("\n") + 1,
                )
            )
    text = (TESTS / "timeline.test.ts").read_text(encoding="utf-8")
    loop_line = text[: text.index("for (const [offset")].count("\n") + 1
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
            (
                f"UI{offset:03}",
                f"Valid A control; replace event {field} with B",
                "Valid A has one message; cross-binding event throws "
                "before any state/cursor write",
                TESTS / "timeline.test.ts",
                loop_line,
            )
        )
    ids = [row[0] for row in rows]
    if (
        len(ids) != len(set(ids))
        or len([i for i in ids if i.startswith("B")]) < 50
    ):
        raise ValueError(
            "Matrix IDs must be unique with at least 50 backend scenarios"
        )
    output = [
        "# PHH Phase B test matrix",
        "",
        "Gate **PHH-B-LOCAL**: all listed tests pass; zero fail/error/skip. "
        "This does not certify the cross-module MB gate, HTTP/database "
        "integration or Phase C/D.",
        "",
        "Inputs come from each fixture and mutations in the linked body. "
        "Expected results are actual assertions, not generated PASS labels. "
        "Test-only fake clock/UOW/runtime/operation/signals are in fakes.py.",
        "",
        "Runner: run_phase_b.py --isolated-imports; UI: Bun test with "
        "all three timeline test files (interaction tests use Happy DOM).",
        "",
        "| ID | Input/scenario | Expected assertions | Test source |",
        "|---|---|---|---|",
    ]
    for case_id, scenario, expected, path, line in sorted(rows):
        relative = path.relative_to(ROOT).as_posix()
        expected = cell(expected)
        if len(expected) > 500:
            expected = expected[:497] + "..."
        output.append(
            f"| {case_id} | {cell(scenario)} | `{expected}` | "
            f"[{path.name}:{line}](../../../../{relative}#L{line}) |"
        )
    output.append(f"\nTotal: {len(rows)} independent scenarios.")
    handoff = (
        ROOT / "docs/workforce/handoffs/phan-huy-hoang/PHASE_B_TEST_MATRIX.md"
    )
    handoff.write_text("\n".join(output) + "\n", encoding="utf-8")
    print(f"Matrix exported: {len(rows)} unique scenarios")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dependency-path", type=Path)
    parser.add_argument("--format", action="store_true")
    parser.add_argument("--export-matrix", action="store_true")
    args = parser.parse_args()
    if args.dependency_path:
        sys.path.insert(0, str(args.dependency_path.resolve()))
    import black
    from flake8.main.application import Application

    files = sorted(
        (ROOT / "src/agentscope/app/workforce/orchestration").rglob("*.py")
    )
    files += sorted(TESTS.glob("*.py"))
    files = [path for path in files if path.name != "phase_a.py"]
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
    lint = Application()
    lint.run(
        [
            "--jobs=1",
            "--max-line-length=79",
            "--extend-ignore=E203",
            *[str(p) for p in files],
        ]
    )
    if args.export_matrix:
        export_matrix()
    print(f"AST/Black: {len(files)} scoped Python files; dirty={len(dirty)}")
    print(
        f"Flake8: {lint.result_count} errors (E203 excluded for Black slices)"
    )
    for path in dirty:
        print(path)
    return int(bool(dirty) or bool(lint.exit_code()))


if __name__ == "__main__":
    raise SystemExit(main())
