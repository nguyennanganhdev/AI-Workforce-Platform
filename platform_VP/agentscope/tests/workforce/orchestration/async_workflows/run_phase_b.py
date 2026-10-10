# -*- coding: utf-8 -*-
"""Run real PHH workflow logic against deterministic test-only dependencies."""

import argparse
from contextlib import redirect_stdout
import io
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tests/workforce/orchestration/phase_a"))
from run_phase_a import isolate_service_initializers  # noqa: E402


def test_cases(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from test_cases(item)
        else:
            yield item


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dependency-path", type=Path)
    parser.add_argument("--isolated-imports", action="store_true")
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / "src"))
    if args.dependency_path:
        sys.path.insert(0, str(args.dependency_path.resolve()))
    if args.isolated_imports:
        with redirect_stdout(io.StringIO()):
            isolate_service_initializers()
        print(
            "UNIT TESTS: real PHH/shared modules; application startup skipped."
        )
    suite = unittest.defaultTestLoader.discover(
        str(Path(__file__).parent), pattern="test_phase_b*.py"
    )
    cases = list(test_cases(suite))
    matches = [re.match(r"test_(B\d{3})_", t._testMethodName) for t in cases]
    if any(match is None for match in matches):
        parser.error("Every backend scenario needs a unique Bnnn ID")
    ids = [match[1] for match in matches]
    if len(ids) != len(set(ids)):
        parser.error("Duplicate Phase B test IDs")
    if len(cases) < 50:
        parser.error(
            "Phase B requires at least 50 independently discovered scenarios"
        )
    print(
        f"PHH-B-LOCAL: {len(cases)} independent backend scenarios", flush=True
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return int(not result.wasSuccessful() or bool(result.skipped))


if __name__ == "__main__":
    raise SystemExit(main())
