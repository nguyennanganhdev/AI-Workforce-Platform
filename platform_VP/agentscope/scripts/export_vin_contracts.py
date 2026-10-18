"""Export safe DTO schemas and the Vin authority router without starting services."""

import inspect
import json
from pathlib import Path

from fastapi import FastAPI
from pydantic.json_schema import models_json_schema
from agentscope.app.vin_platform import _contracts
from agentscope.app.vin_platform._router import router


def export():
    output = Path(__file__).resolve().parents[3] / "docs" / "vin-platform"
    output.mkdir(parents=True, exist_ok=True)
    schemas = {name: value.model_json_schema() for name, value in vars(_contracts).items()
        if inspect.isclass(value) and issubclass(value, _contracts.Contract) and value is not _contracts.Contract}
    app = FastAPI(title="Vin Platform authority", version=_contracts.CONTRACT_VERSION)
    app.include_router(router)
    openapi = app.openapi()
    # Internal consumer contracts also belong in the shared schema, even when
    # they are nested in the deliberately extensible Domain projection.
    models = [_contracts.CustomerPlan, _contracts.PlanDecisionPayload]
    _, definitions = models_json_schema([(model, "validation") for model in models],
        ref_template="#/components/schemas/{model}")
    openapi.setdefault("components", {}).setdefault("schemas", {}).update(definitions["$defs"])
    documents = {"contracts-v1.schema.json": {"contract_version": _contracts.CONTRACT_VERSION, "schemas": schemas},
        "openapi-v1.json": openapi}
    for name, content in documents.items():
        (output / name).write_text(json.dumps(content, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    export()
