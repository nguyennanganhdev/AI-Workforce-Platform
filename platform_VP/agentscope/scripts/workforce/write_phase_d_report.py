"""Aggregate JUnit evidence into the D7 release-candidate report."""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path


def _suite_totals(path: Path) -> tuple[int, int, int, int, float]:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    values = [0, 0, 0, 0]
    duration = 0.0
    for suite in suites:
        values[0] += int(suite.attrib.get("tests", 0))
        values[1] += int(suite.attrib.get("failures", 0))
        values[2] += int(suite.attrib.get("errors", 0))
        values[3] += int(suite.attrib.get("skipped", 0))
        duration += float(suite.attrib.get("time", 0.0))
    return *values, duration


def build_report(
    junit_dir: Path,
    *,
    commit: str,
    sandbox_evidence: str | None,
    required_reports: Sequence[str] = (),
) -> tuple[str, bool]:
    reports = sorted(junit_dir.glob("*.xml"))
    if not reports:
        raise ValueError(f"no JUnit reports found in {junit_dir}")
    report_names = {report.name for report in reports}
    missing = sorted(set(required_reports) - report_names)
    if missing:
        raise ValueError(f"missing required JUnit reports: {', '.join(missing)}")
    rows = []
    totals = [0, 0, 0, 0]
    total_time = 0.0
    empty_reports: list[str] = []
    for report in reports:
        tests, failures, errors, skipped, duration = _suite_totals(report)
        if tests == 0:
            empty_reports.append(report.name)
        rows.append(
            f"| `{report.name}` | {tests} | {failures} | {errors} | "
            f"{skipped} | {duration:.2f}s |"
        )
        totals[0] += tests
        totals[1] += failures
        totals[2] += errors
        totals[3] += skipped
        total_time += duration
    passed = totals[0] > 0 and not empty_reports and not any(totals[1:])
    status = "PASS" if passed else "FAIL"
    sandbox = (
        sandbox_evidence.strip()
        if sandbox_evidence and sandbox_evidence.strip()
        else "NOT_VERIFIED — chưa được cấp endpoint/credential/kịch bản sandbox."
    )
    generated = datetime.now(UTC).isoformat()
    body = "\n".join(
        [
            "# Phase D — D7 Release Candidate Evidence",
            "",
            f"- Commit: `{commit}`",
            f"- Generated at: `{generated}`",
            f"- Automated gate: **{status}**",
            f"- Sandbox: **{sandbox}**",
            (
                "- Empty JUnit reports: **none**"
                if not empty_reports
                else "- Empty JUnit reports: **"
                + ", ".join(f"`{name}`" for name in empty_reports)
                + "**"
            ),
            "",
            "| JUnit report | Tests | Failures | Errors | Skipped | Time |",
            "|---|---:|---:|---:|---:|---:|",
            *rows,
            (
                f"| **Total** | **{totals[0]}** | **{totals[1]}** | "
                f"**{totals[2]}** | **{totals[3]}** | **{total_time:.2f}s** |"
            ),
            "",
            (
                "Một test bị skip làm D7 fail. Sandbox có thể chưa được xác minh, "
                "nhưng phải được ghi rõ như trên và không được gọi là production pass."
            ),
            "",
        ]
    )
    return body, passed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--junit-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--sandbox-evidence")
    parser.add_argument(
        "--require",
        action="append",
        default=[],
        metavar="REPORT.xml",
        help="Require this JUnit filename; may be supplied more than once.",
    )
    args = parser.parse_args(argv)
    try:
        report, passed = build_report(
            args.junit_dir,
            commit=args.commit,
            sandbox_evidence=args.sandbox_evidence,
            required_reports=args.require,
        )
    except (OSError, ET.ParseError, ValueError) as error:
        print(f"phase-D report error: {error}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(
        f"wrote {args.output} (automated gate: "
        f"{'PASS' if passed else 'FAIL'})"
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
