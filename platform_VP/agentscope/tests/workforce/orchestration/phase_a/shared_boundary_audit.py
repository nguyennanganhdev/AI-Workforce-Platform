# -*- coding: utf-8 -*-
"""Report shared-owner validation gaps without editing canonical contracts."""

from copy import deepcopy
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError

from agentscope.app.workforce.contracts import (
    ConversationEvent,
    WorkflowRecord,
)
from fixtures import phase_a_samples


def audit_shared_boundaries() -> list[dict[str, Any]]:
    report = []
    for model, field, value in (
        (WorkflowRecord, "revision", True),
        (ConversationEvent, "occurred_at", "2026-10-10T09:00:00"),
    ):
        sample = deepcopy(phase_a_samples()["models"][model.__name__])
        sample[field] = value
        try:
            model.model_validate(sample)
            accepted = True
        except ValidationError:
            accepted = False
        schema_accepts = Draft202012Validator(
            model.model_json_schema(), format_checker=FormatChecker()
        ).is_valid(sample)
        report.append(
            dict(
                model=model.__name__,
                field=field,
                input=value,
                pydantic_accepts=accepted,
                json_schema_accepts=schema_accepts,
                status="OPEN" if accepted != schema_accepts else "ALIGNED",
                owner="NCH; canonical shared contracts unchanged by PHH",
            )
        )
    return report
