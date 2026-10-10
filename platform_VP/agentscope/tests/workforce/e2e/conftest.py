"""Owner-local fixture imports; no shared test configuration is modified."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fixtures"))
