import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
repo = Path(os.environ.get("REPORT_SOURCE_REPO", Path(__file__).resolve().parents[4]))
sys.path.insert(0, str(repo / "services/vinhomes-api/src"))
