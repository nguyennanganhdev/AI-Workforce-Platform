"""Run no-key acceptance from a fixed copy while the shared worktree is edited."""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .run import ROOT, source_manifest


def freeze(destination: Path) -> Path:
    destination = destination.resolve()
    if destination.exists() or destination == ROOT or ROOT in destination.parents:
        raise ValueError("Use a new snapshot directory outside the source checkout")
    before = source_manifest()
    package = destination / "platform_VP/agentscope"
    package.mkdir(parents=True)
    for relative in before["files"]:
        target = package / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    declaration = Path("vinhome_Recident/deploy/platform/vinhomes-declaration.json")
    target = destination / declaration
    target.parent.mkdir(parents=True)
    shutil.copy2(ROOT.parent.parent / declaration, target)
    after = source_manifest()
    if after["source_sha256"] != before["source_sha256"] or after["declaration_sha256"] != before["declaration_sha256"]:
        raise RuntimeError("Source changed while copying; keep this incomplete copy and retry in a new directory")
    (package / ".acceptance-origin.json").write_text(json.dumps({
        "source_root": str(ROOT), "commit": before["commit"], "branch": before["branch"],
        "copied_source_sha256": before["source_sha256"],
    }, indent=2), encoding="utf-8")
    return package


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--business-threshold", required=True, type=float)
    parser.add_argument("--repetitions", type=int, default=3)
    args = parser.parse_args()
    package = freeze(args.snapshot)
    env = {**os.environ, "PYTHONPATH": str(package / "src"), "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run([sys.executable, "-m", "scripts.workforce.acceptance.run",
        "--business-threshold", str(args.business_threshold), "--repetitions", str(args.repetitions),
        "--output", str(args.output.resolve())], cwd=package, env=env, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
