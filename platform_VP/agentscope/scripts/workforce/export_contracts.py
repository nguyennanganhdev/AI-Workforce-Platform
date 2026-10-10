"""Export the versioned Workforce JSON Schema bundle.

Run from any directory with the repository's Python interpreter:
    python scripts/workforce/export_contracts.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
DEFAULT_OUTPUT = (
    REPOSITORY_ROOT
    / "docs"
    / "workforce"
    / "contracts"
    / "generated"
    / "workforce-v1.schema.json"
)


def main() -> None:
    sys.path.insert(0, str(SOURCE_ROOT))
    from agentscope.app.workforce.contracts import contract_schema_bundle

    DEFAULT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_OUTPUT.write_text(
        json.dumps(
            contract_schema_bundle(),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(DEFAULT_OUTPUT.relative_to(REPOSITORY_ROOT))


if __name__ == "__main__":
    main()
