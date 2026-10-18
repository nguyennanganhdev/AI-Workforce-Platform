"""Offline C07 fixture for consumers; no Domain/model connection required."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from agentscope.app.vin_platform._contracts import CustomerPlan, PlanDecisionPayload, SourceIntent


def test_shared_plan_fixture_preserves_distinct_case_and_plan_versions():
    path = Path(__file__).resolve().parents[3] / "docs/vin-platform/fixtures/c07-plan-decision-v1.json"
    fixture = json.loads(path.read_text(encoding="utf-8"))
    plan = CustomerPlan.model_validate(fixture["plans"][0])
    intent = SourceIntent.model_validate(fixture["intent"])
    choice = PlanDecisionPayload.model_validate(intent.payload)
    assert plan.canDecide and plan.status == "resident_pending"
    assert intent.expected_version == fixture["canonical_version"]
    assert choice.expectedVersion == plan.version != intent.expected_version
    assert choice.plan_id == plan.id and choice.decision == "approve"
    with pytest.raises(ValidationError):
        PlanDecisionPayload.model_validate({**intent.payload, "expectedVersion": "3"})
    with pytest.raises(ValidationError):
        PlanDecisionPayload.model_validate({**intent.payload, "note": "   "})


def test_shared_plan_schemas_are_in_openapi_components():
    path = Path(__file__).resolve().parents[3] / "docs/vin-platform/openapi-v1.json"
    schemas = json.loads(path.read_text(encoding="utf-8"))["components"]["schemas"]
    for model in (CustomerPlan, PlanDecisionPayload):
        assert schemas[model.__name__] == model.model_json_schema(ref_template="#/components/schemas/{model}")
