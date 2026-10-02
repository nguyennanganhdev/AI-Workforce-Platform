"""Shared Python import paths for Reception tests."""

import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parent
PACKAGE = TESTS.parent
for path in (PACKAGE, TESTS / "graph"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
