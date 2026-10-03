"""Offline, digest-pinned JSON Schemas supplied by their owners.

jsonschema/referencing are optional runtime dependencies to be installed by the
composition owner. No schema is generated or accepted from a request body.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping

from .errors import ValidationError
from .messages import snapshot


@dataclass(frozen=True)
class SchemaPin:
    path: Path
    sha256: str


class PinnedContractValidator:
    def __init__(self, pins: Mapping[str, SchemaPin], *, required: set[str]) -> None:
        from jsonschema import FormatChecker
        from jsonschema.validators import validator_for
        from referencing import Registry, Resource

        if not required or not required <= pins.keys():
            raise ValueError("missing required contract schemas")
        schemas = {}
        resources = {}
        formats = FormatChecker()

        @formats.checks("date-time", raises=(ValueError, TypeError))
        def date_time(value):
            if not isinstance(value, str):
                return True  # schema type, not format, rejects non-strings
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})", value):
                return False
            parsed = datetime.fromisoformat(value.upper().replace("Z", "+00:00"))
            return parsed.tzinfo is not None

        def check_formats(node):
            if isinstance(node, dict):
                if "format" in node and node["format"] not in formats.checkers:
                    raise ValueError("unsupported schema format")
                for key, child in node.items():
                    if key in {"properties", "patternProperties", "$defs", "definitions", "dependentSchemas"}:
                        for subschema in child.values():
                            check_formats(subschema)
                    elif key in {"allOf", "anyOf", "oneOf", "prefixItems", "items", "contains",
                                 "not", "if", "then", "else", "additionalProperties", "additionalItems",
                                 "unevaluatedProperties", "unevaluatedItems", "propertyNames", "contentSchema"}:
                        check_formats(child)
            elif isinstance(node, list):
                for child in node:
                    check_formats(child)
        for kind, pin in pins.items():
            raw = Path(pin.path).read_bytes()
            if hashlib.sha256(raw).hexdigest() != pin.sha256:
                raise ValueError("contract digest mismatch")
            schema = json.loads(raw)
            if not isinstance(schema, dict) or "$schema" not in schema:
                raise ValueError("explicit schema dialect required")
            implementation = validator_for(schema, default=None)
            if implementation is None:
                raise ValueError("unsupported schema dialect")
            implementation.check_schema(schema)
            check_formats(schema)
            schemas[kind] = schema
            if "$id" in schema:
                if schema["$id"] in resources:
                    raise ValueError("duplicate schema identity")
                resources[schema["$id"]] = Resource.from_contents(schema)
        # Registry's default retrieval refuses external network/filesystem refs.
        registry = Registry().with_resources(resources.items())
        self._validators = {
            kind: validator_for(schema)(schema, registry=registry, format_checker=formats)
            for kind, schema in schemas.items()
        }
        self.supported_kinds = frozenset(self._validators)

    def validate(self, kind: str, value: Mapping) -> None:
        try:
            self._validators[kind].validate(snapshot(value))
        except Exception:
            raise ValidationError() from None
