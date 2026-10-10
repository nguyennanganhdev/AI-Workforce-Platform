# -*- coding: utf-8 -*-
"""Read-only checks of the Registry/Foundation interfaces used by PHH."""

import argparse
import importlib.util
from pathlib import Path
import sys
import types
import unittest


ROOT = Path(__file__).resolve().parents[4]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--suite", choices=("registry", "foundation"), required=True
    )
    parser.add_argument("--dependency-path", type=Path)
    args = parser.parse_args()
    if args.dependency_path:
        sys.path.insert(0, str(args.dependency_path.resolve()))
    sys.path.insert(0, str(ROOT / "tests/workforce/orchestration/phase_a"))
    from run_phase_a import isolate_service_initializers

    isolate_service_initializers()
    relative = (
        "tests/workforce/registry/event_protocols"
        if args.suite == "registry"
        else "tests/workforce/foundation/async_api"
    )
    directory = ROOT / relative
    package = types.ModuleType("phh_dependency_tests")
    package.__path__ = [str(directory)]
    sys.modules[package.__name__] = package
    sys.path.insert(0, str(directory))
    suite = unittest.TestSuite()
    for path in sorted(directory.glob("test*.py")):
        spec = importlib.util.spec_from_file_location(
            f"{package.__name__}.{path.stem}", path
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
    if not suite.countTestCases():
        parser.error("Dependency suite unexpectedly empty")
    print(f"Read-only dependency suite: {args.suite}", flush=True)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return int(not result.wasSuccessful() or bool(result.skipped))


if __name__ == "__main__":
    raise SystemExit(main())
