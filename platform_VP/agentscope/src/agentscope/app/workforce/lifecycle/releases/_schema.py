"""Local D4 data handoff; no shared DTO promotion."""

from typing import Any, Dict

from ._models import PublishedVersion, ReleaseContext, ReleaseSelection


def phase_d_schema_bundle() -> Dict[str, Any]:
    models = (PublishedVersion, ReleaseSelection, ReleaseContext)
    return {
        "schema_version": "pta-release-1",
        "schemas": {model.__name__: model.model_json_schema() for model in models},
    }
