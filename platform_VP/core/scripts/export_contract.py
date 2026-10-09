"""Export the implemented partner API without starting services or reading credentials."""
import json
from pathlib import Path

from awp.app import build_app
from awp.config import Settings

schema = build_app(Settings()).openapi()
schema["info"] = {"title": "Workforce Partner API", "version": "1+minio-images-v1"}
schema["paths"] = {path: value for path, value in schema["paths"].items()
                   if path.startswith(("/workforce/v1/partner/", "/workforce/v1/provider/"))}
definitions = schema["components"]["schemas"]
used = set()
def visit(value):
    if isinstance(value, list):
        for item in value:
            visit(item)
    if isinstance(value, dict):
        ref = value.get("$ref", "").removeprefix("#/components/schemas/")
        if ref in definitions and ref not in used:
            used.add(ref)
            visit(definitions[ref])
        for item in value.values():
            visit(item)
visit(schema["paths"])
schema["components"] = {"schemas": {key: definitions[key] for key in sorted(used)},
    "securitySchemes": {"PartnerKey": {"type": "apiKey", "in": "header", "name": "Authorization",
        "description": "ApiKey dp_<client_id>.<secret>. Customer/provider credentials have separate purposes and grants."}}}
schema["security"] = [{"PartnerKey": []}]
schema["x-capabilities"] = ["minio-images-v1", "durable-provider-inbox", "explicit-tracking-close"]
for path, methods in schema["paths"].items():
    if path.endswith("/provider/job-events"):
        methods["post"]["parameters"] = [{"name": name, "in": "header", "required": True,
            "schema": {"type": "string"}} for name in ("X-Partner-Timestamp", "X-Partner-Key-Id", "X-Partner-Signature")]
target = Path(__file__).resolve().parents[3] / "docs" / "workforce-v1.openapi.json"
target.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("Exported partner OpenAPI; lifecycle rules and error envelopes are in WORKFORCE_V1_CONTRACT_ADDENDUM.md")
