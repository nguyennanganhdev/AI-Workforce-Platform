"""Compatibility entrypoint using the standard package pytest configuration."""
import subprocess
import sys
from pathlib import Path
package = next(parent for parent in Path(__file__).resolve().parents if parent.name == "agent-coordination")
raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", "-q", str(Path(__file__).resolve().parent)], cwd=package.parent))
