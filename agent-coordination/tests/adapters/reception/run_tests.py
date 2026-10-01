"""DEV-3 runner: pin source namespaces before test packages enter sys.path."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "agent-coordination/src"))
import adapters.backend  # noqa: E402,F401
import adapters.reception  # noqa: E402,F401
import adapters.tools.tool_client  # noqa: E402,F401

if __name__ == "__main__":
    suite = unittest.defaultTestLoader.discover(str(Path(__file__).resolve().parents[1]))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
