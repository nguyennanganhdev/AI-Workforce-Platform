"""The shared consumer fixture stays aligned with the actual Domain input DTO."""

import json
from pathlib import Path

from vinhomes_api.resident_contract import CreateRequest


def test_exported_customer_request_schema_and_example_are_current():
    path = Path(__file__).resolve().parents[4] / "docs/vin-platform/vinhomes-create-request-v1.schema.json"
    fixture = json.loads(path.read_text(encoding="utf-8"))
    assert fixture["contract_version"] == "vin-platform-1" and fixture["domain"] == "vinhomes"
    assert fixture["schema"] == CreateRequest.model_json_schema()
    request = CreateRequest.model_validate(fixture["example"])
    assert request.photoIds == []
