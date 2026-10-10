"""Run real PHH workflow logic against deterministic test-only dependencies."""

import argparse
from contextlib import redirect_stdout
import io
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tests/workforce/orchestration/phase_a"))
from run_phase_a import isolate_service_initializers  # noqa: E402


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
    if suite.countTestCases() < 50:
        parser.error(
            "Phase B requires at least 50 independently discovered scenarios"
        )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return int(not result.wasSuccessful() or bool(result.skipped))


if __name__ == "__main__":
    raise SystemExit(main())
