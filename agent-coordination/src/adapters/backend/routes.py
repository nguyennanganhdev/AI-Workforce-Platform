"""Load approved operation paths without shipping invented production URLs."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit


def operation_routes(value: Mapping[str, str], *, required: set[str]) -> dict[str, str]:
    if not required or not required <= value.keys():
        raise ValueError("missing required operations")
    result = dict(value)
    for name, path in result.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(path, str):
            raise ValueError("invalid operation mapping")
        parsed = urlsplit(path)
        if (not path.startswith("/") or path.startswith("//") or parsed.scheme
                or parsed.netloc or parsed.query or parsed.fragment or "\\" in path
                or any(ord(c) < 33 for c in path)
                or any(part in {".", ".."} for part in path.split("/"))):
            raise ValueError("invalid operation path")
    return result


def load_operation_routes(path: Path, *, required: set[str]) -> dict[str, str]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("operation mapping must be an object")
    return operation_routes(value, required=required)
