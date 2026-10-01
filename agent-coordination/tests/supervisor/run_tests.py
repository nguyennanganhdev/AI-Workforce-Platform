"""Scoped runner: load source namespace before pytest adds tests/adapters to path.

Existing tests/adapters/backend is a regular package that otherwise shadows the
source namespace. No shared runner or owner files are changed by this workaround.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'agent-coordination/src'))
import adapters.backend  # noqa: E402,F401
import adapters.reception  # noqa: E402,F401
import adapters.tools  # noqa: E402,F401
import pytest  # noqa: E402

if __name__ == '__main__':
    raise SystemExit(pytest.main(['-c', str(ROOT / 'agent-coordination/pytest.ini'),
                                  *sys.argv[1:]]))
