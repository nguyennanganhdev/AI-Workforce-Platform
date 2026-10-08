"""Import the owned graph from its Python namespace without changing runtime files."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
